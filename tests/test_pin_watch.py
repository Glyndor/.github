"""Tests for scripts/pin-watch.py.

The watcher runs on a weekly cron, not on a pull request — a regression in
the read path, the held-pin decision, or the issue-create path is invisible
for up to seven days. The failure mode is silent: a broken watcher does not
shout, it just stops reporting. These tests are what turn a regression in
the watcher into a CI failure on the bump PR.

Three IO seams are stubbed:

- The HTTP fetchers (`upstream_crates_io`, `upstream_pypi`, etc.) are
  Python functions named at module scope; tests monkeypatch them via
  `monkeypatch.setattr` on the loaded module. The actual network is never
  touched.
- `upstream_gh_release` calls `gh release list` via subprocess. Tests
  monkeypatch the dispatcher (`fetch_upstream`) so the binary path is
  never reached. `tests/conftest.py`'s `gh_stub` fixture is shaped for
  `gh api` calls — adding a second stub shape here would invent a third
  style for what is fundamentally the same seam (Python function in the
  script).
- `issue_already_open` and `open_issue` are also monkeypatched — the
  dedup test asserts `open_issue` is NOT called when the title already
  exists, and asserting on a call requires controlling it.

The script is imported directly under a synthetic name (`pin_watch`
cannot be a real module name — Python module names cannot contain
hyphens). The importlib dance is the same one `scripts/tooling-audit.py`
already uses internally to load `pin-watch.py` for the shared reader
helper, so it is the established shape for this repository rather than
an invention here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "pin-watch.py"


def _load_pin_watch():
    """Import `pin-watch.py` under a synthetic module name.

    Python module names cannot contain hyphens, so the script cannot be
    imported with a plain `import` statement. `importlib.util` loads the
    file by path under a synthetic name. The same dance
    `scripts/tooling-audit.py` uses internally to share `_read_input_default`
    with this script.
    """
    spec = importlib.util.spec_from_file_location("pin_watch_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- TASK 1 item 1: reading from each source kind ---------------------


def test_read_env_value_parses_bare_value_and_returns_none_for_absent_key() -> None:
    """A bare `KEY: 0.11.0` line is read; an absent key returns None (not '').

    Catches: a regression where the regex would silently return '' for an
    absent key — a later equality check against '' would report a
    spurious drift for every pin the watcher could not read, and the
    weekly issue would list pins that are perfectly fine.
    """
    pin_watch = _load_pin_watch()
    assert pin_watch._read_env_value("KEY: 0.11.0\n", "KEY") == "0.11.0"
    assert pin_watch._read_env_value("OTHER: 0.11.0\n", "KEY") is None


def test_read_input_default_parses_nested_default_and_returns_none_for_absent_input() -> (
    None
):
    """An `inputs.<name>.default:` block yields the value; absent input returns None.

    Catches: a regression where the walker stops one level short of
    `default:`, leaving the watcher reading nothing from every input —
    the weekly issue would report zero drift while pins silently move
    upstream.
    """
    pin_watch = _load_pin_watch()
    text = (
        "on:\n"
        "  workflow_call:\n"
        "    inputs:\n"
        "      foo:\n"
        "        description: x\n"
        "        default: '1.2.3'\n"
    )
    assert pin_watch._read_input_default(text, "foo") == "1.2.3"
    assert pin_watch._read_input_default(text, "missing") is None


def test_read_requirement_pin_parses_eq_pin_and_returns_none_for_absent_name() -> None:
    """A `name==version` line is read; absent name returns None (not empty string).

    Catches: a regression where the parser would return '' for an absent
    name and the watcher would later compare '' against an upstream
    version, producing a permanent drift report for every pin it could
    not read.
    """
    pin_watch = _load_pin_watch()
    assert pin_watch._read_requirement_pin("pyyaml==6.0.1\n", "pyyaml") == "6.0.1"
    assert pin_watch._read_requirement_pin("pyyaml==6.0.1\n", "other") is None


# --- TASK 1 item 2: only == is accepted in requirements ----------------


def test_read_requirement_pin_accepts_only_eq_operator() -> None:
    """A `>=` line, a bare name, and a commented-out pin all return None.

    Catches: a regression where the parser would accept any operator and
    the watcher would report drift against something unpinned — drift
    reports for unpinned deps are noise, and the docstring states the
    'only ==' contract that this test pins.
    """
    pin_watch = _load_pin_watch()
    # `>=` is a range, not a pin.
    assert pin_watch._read_requirement_pin("pyyaml>=6.0\n", "pyyaml") is None
    # A bare name has no version and cannot drift.
    assert pin_watch._read_requirement_pin("requests\n", "requests") is None
    # A commented-out pin is not a pin (and is not a range either).
    assert pin_watch._read_requirement_pin("# pyyaml==6.0.1\n", "pyyaml") is None
    # And the unpinned lines above do not pollute parsing of the actual
    # pinned entry below.
    text = "pyyaml>=6.0\nrequests\n# pyyaml==6.0.1\npyyaml==6.0.1\n"
    assert pin_watch._read_requirement_pin(text, "pyyaml") == "6.0.1"


# --- TASK 1 items 3, 4, 5: end-to-end via main() ----------------------
#
# These three tests share the same harness: stub read_pins, stub
# fetch_upstream, stub the two `gh` calls, run main(), observe. The
# _stub_main helper below wires it all up so each test reads as the one
# assertion that distinguishes it from the others.


def _stub_main(
    pin_watch,
    monkeypatch,
    *,
    pins: dict[str, tuple[str, str]],
    upstream_for: dict[str, str],
    issue_already_open: bool = False,
) -> list[dict]:
    """Wire up the stubs `main()` needs for a controlled end-to-end run.

    Returns the list `open_issue` will append to when invoked. Each test
    asserts on whether the list is empty (no issue opened) and on the
    captured stdout. Every IO seam `main()` reaches is replaced: pin
    reading (so the test controls inputs without touching the real
    workflow files), the upstream fetch dispatcher (so no network or
    `gh` binary is involved), and the two `gh` calls (so the dedup
    decision is observable from inside the test).
    """
    monkeypatch.setattr(pin_watch, "read_pins", lambda: dict(pins))

    def fake_fetch(name: str) -> str:
        try:
            return upstream_for[name]
        except KeyError as e:
            raise RuntimeError(f"unexpected pin in test: {name}") from e

    monkeypatch.setattr(pin_watch, "fetch_upstream", fake_fetch)
    monkeypatch.setattr(
        pin_watch, "issue_already_open", lambda title: issue_already_open
    )

    opened: list[dict] = []

    def fake_open(title: str, body: str) -> str:
        opened.append({"title": title, "body": body})
        return "https://example.test/issue/1"

    monkeypatch.setattr(pin_watch, "open_issue", fake_open)
    return opened


def test_held_pin_stays_silent_when_pin_matches_hold(monkeypatch, capsys) -> None:
    """A held pin whose value still matches its hold stays silent — no issue opened.

    Catches: a regression that breaks a held pin out of 'silent' state
    and trains the reader to ignore the weekly issue — the failure mode
    the hold list exists to prevent (per the module docstring, the held
    pins are the ones deliberately below upstream).
    """
    pin_watch = _load_pin_watch()
    # `ruff` is in HOLDS as "0.12.0"; matching the hold is the silent case.
    opened = _stub_main(
        pin_watch,
        monkeypatch,
        pins={"ruff": ("python-ci.yml", "0.12.0")},
        upstream_for={},  # held pins never reach fetch_upstream
    )

    exit_code = pin_watch.main()
    capsys.readouterr()

    assert exit_code == 0
    assert opened == [], (
        f"Held pin matching its hold must stay silent; got issue(s): {opened!r}"
    )


def test_held_pin_reported_stale_when_pin_no_longer_matches_hold(
    monkeypatch, capsys
) -> None:
    """A held pin whose value no longer matches its hold is reported as stale.

    Catches: a regression where a pin bump without updating `HOLDS` does
    not surface — 'silent' means 'pin matches hold', not 'pin differs
    but we forgot to look'. The only place the hold decision lives is
    in main(); a wrong branch here is the most expensive failure mode
    the watcher can have, because the whole point of a hold is to mute
    one pin and the only signal of a stale mute is this issue.
    """
    pin_watch = _load_pin_watch()
    opened = _stub_main(
        pin_watch,
        monkeypatch,
        pins={"ruff": ("python-ci.yml", "0.99.0")},  # does NOT match HOLDS["ruff"]
        upstream_for={},
    )

    exit_code = pin_watch.main()
    capsys.readouterr()

    assert exit_code == 0
    assert len(opened) == 1
    body = opened[0]["body"]
    # Structure check: the pin name, its new pinned value, and the hold
    # version all appear in the body — the held_stale table is populated
    # with the actual data, not just a heading.
    assert "ruff" in body
    assert "0.99.0" in body
    assert "0.12.0" in body


def test_no_drift_reported_when_pin_matches_upstream(monkeypatch, capsys) -> None:
    """A non-held pin whose upstream matches the pin stays silent.

    Catches: a regression where the watcher reports a drift for a
    matched pin and trains the reader to ignore the weekly issue — the
    mirror of the held-silent failure mode, both of which the docstring
    calls out as the reason the script exists.
    """
    pin_watch = _load_pin_watch()
    opened = _stub_main(
        pin_watch,
        monkeypatch,
        pins={"pytest": ("python-ci.yml", "8.0.0")},
        upstream_for={"pytest": "8.0.0"},
    )

    exit_code = pin_watch.main()
    capsys.readouterr()

    assert exit_code == 0
    assert opened == [], (
        f"Pin matching upstream must stay silent; got issue(s): {opened!r}"
    )


def test_drift_reported_when_pin_differs_from_upstream(monkeypatch, capsys) -> None:
    """A non-held pin whose upstream differs from the pin is reported as drift.

    Catches: a regression where the comparison silently swallows the
    drift and the bump goes unannounced — the only reason the watcher
    runs at all.
    """
    pin_watch = _load_pin_watch()
    opened = _stub_main(
        pin_watch,
        monkeypatch,
        pins={"pytest": ("python-ci.yml", "8.0.0")},
        upstream_for={"pytest": "8.1.0"},  # upstream is one ahead
    )

    exit_code = pin_watch.main()
    capsys.readouterr()

    assert exit_code == 0
    assert len(opened) == 1
    body = opened[0]["body"]
    # Structure check: the pin name and BOTH values (pinned + upstream)
    # appear in the body — the drift table is populated with the actual
    # data, not just a heading.
    assert "pytest" in body
    assert "8.0.0" in body
    assert "8.1.0" in body


def test_no_duplicate_issue_when_title_already_open(monkeypatch, capsys) -> None:
    """A drift with the exact issue title already open does not create a second one.

    Catches: a regression that opens a fresh issue every weekly run —
    the maintainer would drown in duplicates with no signal which is the
    current one. The dedup is on the exact title; a title that drifts
    even one character would still create a duplicate, and the
    regression that loses the dedup check entirely would do so silently.
    """
    pin_watch = _load_pin_watch()
    opened = _stub_main(
        pin_watch,
        monkeypatch,
        pins={"pytest": ("python-ci.yml", "8.0.0")},
        upstream_for={"pytest": "8.1.0"},
        issue_already_open=True,  # pretend the issue exists
    )

    exit_code = pin_watch.main()
    capsys.readouterr()

    assert exit_code == 0
    assert opened == [], (
        f"With issue already open, open_issue must NOT be called; got: {opened!r}"
    )


# --- TASK 1 item 6: unreadable pin fails the run ----------------------


def test_read_pins_fails_when_pin_cannot_be_read(monkeypatch, tmp_path, capsys) -> None:
    """A pin the script could not read fails the run with `::error::` and exit 1.

    Catches: a regression where the watcher silently skips a pin it was
    asked to read and reports the rest — silent skip is the failure
    mode that produced the missing coverage in the first place (the
    weekly cron would still report zero drift, masking the unreadable
    pin for up to seven days).

    Sets up a temp `.github/workflows/fake.yml` whose `inputs` block
    does NOT contain the named input, points PIN_SOURCES at it, and
    asserts the script exits 1 with a `::error file=<source>::` line
    naming the missing input. The CI workflow's run summary reads those
    `::error::` lines; absent this, the failure is invisible.
    """
    pin_watch = _load_pin_watch()
    # Replace PIN_SOURCES with a single entry that points at a workflow
    # file where the named input is missing. This exercises the
    # 'input default not found' branch of read_pins without requiring
    # all 19 real workflow files to be present.
    monkeypatch.setattr(
        pin_watch,
        "PIN_SOURCES",
        [("fake-pin", "fake.yml", "input", "missing-input")],
    )

    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "fake.yml").write_text(
        "on:\n"
        "  workflow_call:\n"
        "    inputs:\n"
        "      other-input:\n"
        "        default: '1.0.0'\n"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        pin_watch.read_pins()
    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "::error" in captured.err
    assert "missing-input" in captured.err
