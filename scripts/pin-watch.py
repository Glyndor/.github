#!/usr/bin/env python3
"""Read every pinned tool version in this repository from its workflow file
and report any that have drifted from their upstream release.

Pins are READ FROM the workflow files at runtime, never hardcoded. Where a
pin appears in more than one file (rust toolchain, actionlint, shellcheck),
the first file in PIN_SOURCES below is the canonical source — every other
file is asserted equal to it by tests/test_workflow_pins.py, so this script
reads one and trusts the test to enforce the rest. Hardcoding the pin in
the watcher would mean the watcher can disagree with reality, which is the
bug the watcher exists to prevent.

A held pin (the four entries in HOLDS below) is reported ONLY when the
pinned value stops matching its hold version — meaning somebody changed
the pin and the hold note is now stale. While the pin still matches the
hold, the watcher is silent about it. Reporting the upstream delta every
Tuesday would train the reader to ignore the issue, which is the failure
mode the hold list exists to prevent.

Upstream sources:

- crates.io   https://crates.io/api/v1/crates/<name>  -> .crate.max_stable_version
- PyPI        https://pypi.org/pypi/<name>/json       -> .info.version
- GitHub      gh release list --repo <r> --limit 1 --json tagName --jq '.[0].tagName'
- rust        https://static.rust-lang.org/dist/channel-rust-stable.toml,
              the version under [pkg.rust]; compared only at MAJOR.MINOR
- python      https://endoflife.date/api/python.json  -> [0].cycle
- PSScriptAnalyzer — endpoint returns Atom XML; awkward to parse reliably,
              so pssa-version is read but its upstream is not queried.

Reporting: collect all drifts, open ONE issue titled exactly "Pinned tool
versions have drifted", skip if an issue with that exact title is already
open. Labels: type:ci, prio:P2, status:ready, area:ci, effort:S.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORKFLOWS_DIR = Path(".github/workflows")

# Held pins: silent while the pinned value matches the hold version
# recorded here. The only time a held pin shows up in the report is when
# somebody changed the pin and forgot to update this list — the hold note
# is then stale and the next person needs to know. Do not "fix" the
# silence by deleting the entry; that trains the reader to ignore the
# report and is the failure mode the hold list exists to prevent.
HOLDS: dict[str, tuple[str, str]] = {
    "ruff": (
        "0.12.0",
        "0.16.4 reports 15 findings that are code changes in five files; PLW1510 needs check=False, not check=True",
    ),
    "bun": (
        "1.3.14",
        "consumers epistle-panel and specio cannot be exercised from here",
    ),
    "gosec": ("v2.27.1", "consumer authcore cannot be exercised from here"),
    "cargo-llvm-cov": (
        "0.8.7",
        "five consumers; a coverage tool's bump can move numbers into a threshold",
    ),
}

# The single canonical source for each pin. Where a name appears in more
# than one file, tests/test_workflow_pins.py already asserts equality, so
# the FIRST file in the list is the one this watcher reads. Adding a new
# file to a list should be paired with a pin-agreement test, or two
# workflows will silently drift.
#
# kind=env reads a literal `KEY: value` line in a job's env:
# kind=input reads an on.workflow_call.inputs.<name>.default.
# kind=requirements reads a `name==version` line in requirements.txt, which
#   python-ci installs when the file exists. It is a hand-typed pin like the
#   others, so it is watched like the others — a watcher that skips the pin its
#   own repository added is the failure this file exists to prevent.
PIN_SOURCES: list[tuple[str, str, str, str]] = [
    ("actionlint", "actionlint.yml", "env", "ACTIONLINT_VERSION"),
    ("pyyaml-test-dep", "requirements.txt", "requirements", "pyyaml"),
    ("shellcheck", "actionlint.yml", "env", "SHELLCHECK_VERSION"),
    ("PyYAML", "docs-current.yml", "env", "PYYAML_VERSION"),
    ("bun", "bun-ci.yml", "input", "bun-version"),
    ("govulncheck", "go-audit.yml", "input", "govulncheck-version"),
    ("gosec", "go-audit.yml", "input", "gosec-version"),
    ("pssa-version", "powershell-ci.yml", "input", "pssa-version"),
    ("python", "python-ci.yml", "input", "python-version"),
    ("ruff", "python-ci.yml", "input", "ruff-version"),
    ("pytest", "python-ci.yml", "input", "pytest-version"),
    ("rust", "rust-ci.yml", "input", "toolchain"),
    ("cargo-audit", "rust-audit.yml", "input", "cargo-audit-version"),
    ("cargo-deny", "rust-audit.yml", "input", "cargo-deny-version"),
    ("cargo-llvm-cov", "rust-ci.yml", "input", "llvm-cov-version"),
    ("cargo-semver-checks", "rust-ci.yml", "input", "semver-checks-version"),
    ("cargo-fuzz", "rust-fuzz.yml", "input", "cargo-fuzz-version"),
    ("cargo-cyclonedx", "rust-supply-chain.yml", "input", "cyclonedx-version"),
    ("cargo-about", "rust-supply-chain.yml", "input", "cargo-about-version"),
]

# Read the pin, but do not query upstream. See the module docstring for
# why PSScriptAnalyzer is on this list.
SKIP_UPSTREAM: set[str] = {"pssa-version"}


def _read_env_value(text: str, env_key: str) -> str | None:
    """Read the literal `KEY: value` env entry from a workflow file.

    Accepts both bare (`KEY: v0.11.0`) and quoted (`KEY: "v0.11.0"`) forms.
    Returns the value, or None if no such line is found. The regex matches
    one line at a time; the alternative captures let it accept either
    quoting style without dragging in a YAML parser.
    """
    pat = re.compile(
        r"^\s*" + re.escape(env_key) + r":\s*"
        r"(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'{][^\s\"']*))"
        r"\s*(?:#.*)?$",
        re.MULTILINE,
    )
    for m in pat.finditer(text):
        v = (
            m.group(1)
            if m.group(1) is not None
            else (m.group(2) if m.group(2) is not None else m.group(3))
        )
        if v is not None:
            return v
    return None


def _read_input_default(text: str, input_name: str) -> str | None:
    """Read the `default:` value of a named input from a workflow file.

    The input block is `input_name:` followed by an indented series of
    keys. The `default:` value can be bare (`default: 1.2.3`) or quoted
    (`default: "1.2.3"`); both are accepted. Returns the value, or None
    if not found.

    This walks the file line-by-line rather than YAML-parsing the whole
    document, so the watcher does not depend on having a particular
    PyYAML version installed — the pin PyYAML would itself need to be
    read first, and that is a bootstrap problem the workflow does not
    need.
    """
    lines = text.splitlines()
    in_block = False
    block_indent: int | None = None
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        if not in_block:
            if stripped == f"{input_name}:" or stripped.startswith(f"{input_name}:"):
                # `with:` blocks also use `<name>:` at column zero;
                # distinguish by checking that the following real line is
                # MORE indented (a block) rather than less-or-equal (a
                # scalar or end of an outer block).
                idx = lines.index(line)
                nxt = next(
                    (
                        nxt_line
                        for nxt_line in lines[idx + 1 :]
                        if nxt_line.strip() and not nxt_line.lstrip().startswith("#")
                    ),
                    None,
                )
                if nxt is None:
                    return None
                if (len(nxt) - len(nxt.lstrip())) <= indent:
                    return None
                in_block = True
                block_indent = indent
            else:
                continue
        else:
            assert block_indent is not None
            if indent <= block_indent:
                return None
            if stripped.startswith("default:"):
                value_part = stripped[len("default:") :].strip()
                if (value_part.startswith('"') and value_part.endswith('"')) or (
                    value_part.startswith("'") and value_part.endswith("'")
                ):
                    value_part = value_part[1:-1]
                return value_part
    return None


def _read_requirement_pin(text: str, name: str) -> str | None:
    """Read `name==version` out of a requirements file.

    Only the `==` form is accepted. A range or a bare name is not a pin, and
    reporting drift against something unpinned would be noise.
    """
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        left, sep, right = line.partition("==")
        if sep and left.strip().lower() == name.lower():
            return right.strip()
    return None


def read_pins() -> dict[str, tuple[str, str]]:
    """Read every pinned value from its workflow file.

    Returns {pin_name: (source_file, value)}. Fails the run if a pin
    cannot be read — the watcher must not silently skip a pin it was
    asked to read.
    """
    cache: dict[str, str] = {}
    pins: dict[str, tuple[str, str]] = {}
    for pin_name, source_file, kind, key in PIN_SOURCES:
        if source_file not in cache:
            # Most pins live under .github/workflows/; requirements.txt is at the
            # repository root, so resolve relative to the root when the name is
            # not a workflow.
            path = (
                Path(source_file)
                if not source_file.endswith((".yml", ".yaml"))
                else WORKFLOWS_DIR / source_file
            )
            cache[source_file] = path.read_text()
        text = cache[source_file]
        if kind == "env":
            v = _read_env_value(text, key)
        elif kind == "input":
            v = _read_input_default(text, key)
        elif kind == "requirements":
            v = _read_requirement_pin(text, key)
        else:
            raise AssertionError(f"unknown kind: {kind!r}")
        if v is None:
            print(
                f"::error file={source_file}::could not read "
                f"{kind} {key} (pin: {pin_name})",
                file=sys.stderr,
            )
            sys.exit(1)
        pins[pin_name] = (source_file, v)
    return pins


# --- Upstream fetchers ---------------------------------------------------

UA = "glyndor-pin-watch/1.0 (+https://github.com/Glyndor/.github)"


def _http_get_json(url: str) -> object:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def upstream_crates_io(crate: str) -> str:
    body = _http_get_json(f"https://crates.io/api/v1/crates/{crate}")
    v = body.get("crate", {}).get("max_stable_version")  # type: ignore[union-attr]
    if not v:
        raise RuntimeError(f"no max_stable_version for {crate}")
    return v


def upstream_pypi(project: str) -> str:
    body = _http_get_json(f"https://pypi.org/pypi/{project}/json")
    v = body.get("info", {}).get("version")  # type: ignore[union-attr]
    if not v:
        raise RuntimeError(f"no info.version for {project}")
    return v


def upstream_gh_release(repo: str) -> str:
    out = subprocess.check_output(
        [
            "gh",
            "release",
            "list",
            "--repo",
            repo,
            "--limit",
            "1",
            "--json",
            "tagName",
            "--jq",
            ".[0].tagName",
        ],
        text=True,
    ).strip()
    if not out:
        raise RuntimeError(f"no releases found for {repo}")
    return out


def upstream_rust_stable() -> str:
    body = _http_get_text(
        "https://static.rust-lang.org/dist/channel-rust-stable.toml",
    )
    # Locate the [pkg.rust] section; the version= line immediately after
    # it is the current stable. Everything else in the file is per-target
    # metadata and not relevant here.
    m = re.search(
        r"^\[pkg\.rust\]\s*$(.*?)(?=^\[|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        raise RuntimeError("no [pkg.rust] section in channel-rust-stable.toml")
    # The version= line has the shape `version = "1.98.0 (88d9e12ae 2026-08-18)"`
    # — the MAJOR.MINOR.PATCH is the first whitespace-separated token
    # inside the quotes, the rest is the channel's git describe metadata.
    # Match just the first token; the strict MAJOR.MINOR.PATCH regex
    # below rejects anything else, so a future change to the file's
    # shape surfaces as a hard error rather than a silent miscompare.
    v_m = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)', m.group(1))
    if not v_m:
        raise RuntimeError("no version= under [pkg.rust]")
    return v_m.group(1)


def upstream_python_eol() -> str:
    body = _http_get_json("https://endoflife.date/api/python.json")
    cycle = body[0].get("cycle")  # type: ignore[index]
    if not cycle:
        raise RuntimeError("no cycle[0] in endoflife.date response")
    return cycle


FETCHERS: dict = {
    "cargo-audit": lambda: upstream_crates_io("cargo-audit"),
    "cargo-deny": lambda: upstream_crates_io("cargo-deny"),
    "cargo-llvm-cov": lambda: upstream_crates_io("cargo-llvm-cov"),
    "cargo-semver-checks": lambda: upstream_crates_io("cargo-semver-checks"),
    "cargo-fuzz": lambda: upstream_crates_io("cargo-fuzz"),
    "cargo-cyclonedx": lambda: upstream_crates_io("cargo-cyclonedx"),
    "cargo-about": lambda: upstream_crates_io("cargo-about"),
    "PyYAML": lambda: upstream_pypi("PyYAML"),
    "pyyaml-test-dep": lambda: upstream_pypi("PyYAML"),
    "ruff": lambda: upstream_pypi("ruff"),
    "pytest": lambda: upstream_pypi("pytest"),
    "actionlint": lambda: upstream_gh_release("rhysd/actionlint"),
    "shellcheck": lambda: upstream_gh_release("koalaman/shellcheck"),
    "bun": lambda: upstream_gh_release("oven-sh/bun"),
    "gosec": lambda: upstream_gh_release("securego/gosec"),
    "govulncheck": lambda: upstream_gh_release("golang/vuln"),
    "rust": upstream_rust_stable,
    "python": upstream_python_eol,
}


def fetch_upstream(pin_name: str) -> str:
    fetcher = FETCHERS.get(pin_name)
    if fetcher is None:
        raise RuntimeError(f"no fetcher for {pin_name}")
    return fetcher()


# --- Reporting -----------------------------------------------------------

ISSUE_TITLE = "Pinned tool versions have drifted"
ISSUE_LABELS = ("type:ci", "prio:P2", "status:ready", "area:ci", "effort:S")


def compare(pin_name: str, pin_value: str, upstream: str) -> bool:
    """Return True if pin and upstream are equal for this pin's contract.

    Most pins compare as exact strings. The Rust toolchain pin is
    MAJOR.MINOR (e.g. "1.98"); upstream reports MAJOR.MINOR.PATCH (e.g.
    "1.98.0"). Compare only the two-component prefix — the third
    component is a patch that the pin's contract deliberately does not
    name.
    """
    if pin_name == "rust":
        pin_mm = ".".join(pin_value.split(".")[:2])
        up_mm = ".".join(upstream.split(".")[:2])
        return pin_mm == up_mm
    return pin_value == upstream


def render_body(
    drift: list[tuple[str, str, str, str]],
    held_stale: list[tuple[str, str, str, str, str]],
    skipped: list[tuple[str, str, str, str]],
) -> str:
    lines: list[str] = []
    lines.append(
        "The following tool versions pinned in this repository "
        "have drifted from their upstream releases."
    )
    lines.append("")
    lines.append("| Pin | File | Pinned | Upstream |")
    lines.append("|---|---|---|---|")
    for name, src, pin, up in drift:
        lines.append(f"| `{name}` | `{src}` | `{pin}` | `{up}` |")
    lines.append("")
    if held_stale:
        lines.append("## Hold notes needing update")
        lines.append("")
        lines.append(
            "The following pins are deliberately held below upstream, but "
            "the pinned value no longer matches the hold version listed "
            "in `.github/workflows/pin-watch.yml`'s `HOLDS` table — "
            "somebody changed the pin and the hold note is now stale. "
            "Update `HOLDS` to match the new pin (or restore the "
            "original pin if the change was unintentional)."
        )
        lines.append("")
        lines.append("| Pin | File | Pinned (now) | Hold says | Reason |")
        lines.append("|---|---|---|---|---|")
        for name, src, pin, hold, reason in held_stale:
            lines.append(f"| `{name}` | `{src}` | `{pin}` | `{hold}` | {reason} |")
        lines.append("")
    if skipped:
        lines.append("## Upstream check skipped")
        lines.append("")
        lines.append(
            "The following pins were read but their upstream was not "
            "queried this run (transient or by design). They are NOT in "
            "the drift table above and are listed here only for "
            "visibility."
        )
        lines.append("")
        lines.append("| Pin | File | Pinned | Reason |")
        lines.append("|---|---|---|---|")
        for name, src, pin, reason in skipped:
            lines.append(f"| `{name}` | `{src}` | `{pin}` | {reason} |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_Opened by the `pin-watch` self-CI workflow. Closing this "
        "issue without acting is the wrong response — bump the pinned "
        "versions in the named workflow files (or update the hold note "
        "in `.github/workflows/pin-watch.yml`), then close the issue "
        "once the next scheduled run reports nothing._"
    )
    return "\n".join(lines) + "\n"


def issue_already_open(title: str) -> bool:
    """Return True if an open issue with this exact title exists."""
    out = subprocess.check_output(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--search",
            f"in:title {title}",
            "--json",
            "title",
            "--jq",
            ".[] | .title",
        ],
        text=True,
    )
    titles = [line.strip() for line in out.splitlines() if line.strip()]
    return title in titles


def open_issue(title: str, body: str) -> str:
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    for label in ISSUE_LABELS:
        cmd.extend(["--label", label])
    out = subprocess.check_output(cmd, text=True).strip()
    return out


# --- Main flow -----------------------------------------------------------


def main() -> int:
    pins = read_pins()
    print("Pins read from workflow files:")
    for name in sorted(pins):
        src, v = pins[name]
        print(f"  {name:22s} {v!r:18s} ({src})")
    print()

    drift: list[tuple[str, str, str, str]] = []
    held_stale: list[tuple[str, str, str, str, str]] = []
    fetch_errors: list[tuple[str, str, str, str]] = []
    skipped: list[tuple[str, str, str, str]] = []

    for name, (src, pin) in pins.items():
        if name in SKIP_UPSTREAM:
            skipped.append(
                (
                    name,
                    src,
                    pin,
                    "upstream endpoint not wired (see SKIP_UPSTREAM in pin-watch.yml)",
                )
            )
            continue
        if name in HOLDS:
            hold_v, hold_reason = HOLDS[name]
            if pin != hold_v:
                held_stale.append((name, src, pin, hold_v, hold_reason))
            continue
        try:
            upstream = fetch_upstream(name)
        except (
            subprocess.CalledProcessError,
            RuntimeError,
            urllib.error.URLError,
            json.JSONDecodeError,
            OSError,
        ) as e:
            fetch_errors.append((name, src, pin, str(e)))
            continue
        if not compare(name, pin, upstream):
            drift.append((name, src, pin, upstream))

    print("Upstream results (non-held, non-skipped pins):")
    for name in sorted(pins):
        if name in SKIP_UPSTREAM or name in HOLDS:
            continue
        src, pin = pins[name]
        if any(d[0] == name for d in drift):
            up = next(d[3] for d in drift if d[0] == name)
            print(f"  {name:22s} pin={pin!r:18s} upstream={up!r:18s} DRIFT")
        elif any(e[0] == name for e in fetch_errors):
            err = next(e[3] for e in fetch_errors if e[0] == name)
            print(f"  {name:22s} pin={pin!r:18s} upstream=<error: {err}>")
        else:
            print(f"  {name:22s} pin={pin!r:18s} upstream=<match>")
    print()

    print("Held pins (silent while pin matches hold):")
    for name in sorted(HOLDS):
        if name not in pins:
            continue
        src, pin = pins[name]
        hold_v, _ = HOLDS[name]
        if pin == hold_v:
            print(
                f"  {name:22s} pin={pin!r:14s} hold={hold_v!r:14s} "
                "SILENT (pin matches hold)"
            )
        else:
            print(
                f"  {name:22s} pin={pin!r:14s} hold={hold_v!r:14s} "
                "STALE HOLD (expected to be reported)"
            )
    print()

    if fetch_errors:
        print("Upstream fetch errors:")
        for name, src, pin, err in fetch_errors:
            print(f"  {name}: {err}")
        print()

    if not drift and not held_stale:
        print("No drift detected. pin-watch is current.")
        return 0

    body = render_body(drift, held_stale, skipped)
    print("---")
    print("Issue body:")
    print(body)
    print("---")

    if issue_already_open(ISSUE_TITLE):
        print(f"Issue {ISSUE_TITLE!r} is already open — not creating a duplicate.")
        return 0

    url = open_issue(ISSUE_TITLE, body)
    print(f"Opened: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
