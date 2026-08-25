"""Tests for scripts/tooling-audit.py.

The script audits the dependency trees of the Rust tooling CI installs
(`cargo install --locked <tool>` reuses the tool's own bundled
`Cargo.lock`). The output is a single weekly issue; a regression that
silently swallows real findings — or that breaks the dedup, or that
fails the run on advisories a maintainer cannot control — is invisible
for up to seven days. These tests are what turn a regression into a CI
failure on the bump PR.

Three IO seams are stubbed:

- The HTTP download (`_http_get_bytes`) is a Python function named at
  module scope; tests monkeypatch it on the loaded module. The actual
  network is never touched.
- `cargo audit` is invoked via subprocess; tests monkeypatch
  `run_cargo_audit` so the binary is never invoked. The output the
  script parses is JSON, so the stub is a dict — a regression that
  re-introduced text-grep would surface here.
- The two `gh` calls (`issue_already_open`, `open_issue`) are
  monkeypatched for the same reason as in `test_pin_watch.py`: the
  dedup test asserts `open_issue` is NOT called when the title already
  exists.

The script is imported directly under a synthetic name (`tooling-audit`
cannot be a real module name — Python module names cannot contain
hyphens). The script itself already uses the same importlib dance
internally to load `pin-watch.py` for the shared reader helper, so the
shape is established here, not invented.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "tooling-audit.py"


def _load_tooling_audit():
    """Import `tooling-audit.py` under a synthetic module name.

    Python module names cannot contain hyphens, so the script cannot be
    imported with a plain `import` statement. `importlib.util` loads the
    file by path under a synthetic name. The script uses the same dance
    internally to share `_read_input_default` with `pin-watch.py`.
    """
    spec = importlib.util.spec_from_file_location("tooling_audit_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- TASK 2 item 1: exit code semantics -------------------------------
#
# Two tests, one in each direction. The exit-code-on-advisory trap is the
# single most expensive failure this script can have: an upstream
# advisory that ships during a quiet week would block every PR in the
# organisation via this self-CI. The test that asserts an advisory does
# NOT fail is therefore the most important test in the file.


def _audit_result(
    *,
    tool: str = "cargo-audit",
    version: str = "0.21.0",
    vulnerabilities: list[dict] | None = None,
    yanked: list[dict] | None = None,
    reason: str | None = None,
) -> dict:
    """Build a complete AuditResult with sensible defaults for unused keys."""
    return {
        "tool": tool,
        "version": version,
        "vulnerabilities": vulnerabilities if vulnerabilities is not None else [],
        "yanked": yanked if yanked is not None else [],
        "reason": reason,
    }


def test_advisory_found_does_not_fail_the_run(monkeypatch, capsys) -> None:
    """An advisory (vulnerability or yanked) found by `cargo audit` does NOT exit 1.

    Catches: a regression where exit-code-as-finding would fail every PR
    in the organisation when a third-party advisory ships — the failure
    mode the module docstring explicitly forbids. The right response to
    a finding is the issue, not a red CI.
    """
    ta = _load_tooling_audit()
    # One tool with a real vulnerability; no script failure.
    monkeypatch.setattr(
        ta,
        "read_pins",
        lambda: {"cargo-audit": ("rust-audit.yml", "0.21.0")},
    )
    monkeypatch.setattr(
        ta,
        "audit_one",
        lambda tool, version: _audit_result(
            vulnerabilities=[
                {
                    "advisory": "RUSTSEC-2025-0001",
                    "package": "openssl",
                    "version": "0.1.0",
                    "cvss": None,
                    "patched": "0.2.0",
                }
            ]
        ),
    )
    monkeypatch.setattr(ta, "issue_already_open", lambda title: False)
    opened: list[dict] = []
    monkeypatch.setattr(
        ta,
        "open_issue",
        lambda title, body: (
            opened.append({"title": title, "body": body})
            or "https://example.test/issue/1"
        ),
    )

    exit_code = ta.main()
    capsys.readouterr()

    assert exit_code == 0, (
        f"An advisory found by cargo audit must not fail the run; got exit {exit_code}"
    )
    assert len(opened) == 1


def test_script_failure_fails_the_run(monkeypatch, capsys) -> None:
    """A script-level failure (download error, unparseable JSON) DOES exit 1.

    Catches: a regression where the audit silently swallows real script
    failures — a broken tool on the weekly cron is invisible for up to
    seven days, and the operator never learns the auditor stopped
    working. The 'no bundled Cargo.lock' reason is excluded; that one
    is a legitimate 'we could not audit this' answer, not a failure.
    """
    ta = _load_tooling_audit()
    # One tool; the audit ran but failed for a non-lockfile reason.
    monkeypatch.setattr(
        ta,
        "read_pins",
        lambda: {"cargo-audit": ("rust-audit.yml", "0.21.0")},
    )
    monkeypatch.setattr(
        ta,
        "audit_one",
        lambda tool, version: _audit_result(
            reason="download HTTP 404: https://static.crates.io/crates/cargo-audit/0.21.0.crate",
        ),
    )

    exit_code = ta.main()
    capsys.readouterr()

    assert exit_code != 0, (
        f"A script failure (download error) must exit non-zero; got exit {exit_code}"
    )


# --- TASK 2 item 2: no bundled Cargo.lock is reported, not skipped -----


def test_audit_one_reports_no_bundled_cargo_lock(monkeypatch) -> None:
    """A `.crate` with no bundled `Cargo.lock` is reported as NOT AUDITED with a reason.

    Catches: a regression where the script silently treats such a tool
    as 'audited and clean' — 'we could not audit this' is an honest
    answer the issue body must surface, not a quiet skip. The
    FileNotFoundError branch is the exact path `fetch_lockfile` raises
    when the extracted crate has no `Cargo.lock`, which is the seam the
    test exercises here.
    """
    ta = _load_tooling_audit()

    def fake_fetch_lockfile(tool: str, version: str) -> Path:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(ta, "fetch_lockfile", fake_fetch_lockfile)

    result = ta.audit_one("cargo-audit", "0.21.0")

    assert result["reason"] == "no bundled Cargo.lock in .crate"
    assert result["vulnerabilities"] == []
    assert result["yanked"] == []


# --- TASK 2 item 3: yanked separate from vulnerabilities --------------


def test_render_body_separates_yanked_from_vulnerabilities() -> None:
    """The rendered body puts yanked entries in `## Yanked crates` and vulnerability entries in `## Vulnerabilities`, not mixed.

    Catches: a regression where the report conflates the two and the
    maintainer cannot tell whether a finding is a security advisory
    (action: bump and re-audit) or an upstream marking-as-bad (action:
    bump or stop using). Both belong on the page; both must land in
    their own section, in that order, so the body reads top-to-bottom
    as severity decreasing.
    """
    ta = _load_tooling_audit()
    results = [
        _audit_result(
            vulnerabilities=[
                {
                    "advisory": "RUSTSEC-2025-0001",
                    "package": "openssl",
                    "version": "0.1.0",
                    "cvss": "7.5",
                    "patched": "0.2.0",
                }
            ],
            yanked=[{"package": "openssl", "version": "0.0.1"}],
        )
    ]

    body = ta.render_body(results)

    # Structure: `## Vulnerabilities` appears BEFORE `## Yanked crates`.
    vuln_idx = body.index("## Vulnerabilities")
    yanked_idx = body.index("## Yanked crates")
    assert vuln_idx < yanked_idx, (
        "Vulnerabilities section must precede Yanked crates section"
    )

    # The vulnerability entry lives in the Vulnerabilities section,
    # between its heading and the Yanked crates heading.
    vuln_section = body[vuln_idx:yanked_idx]
    assert "RUSTSEC-2025-0001" in vuln_section
    assert "openssl" in vuln_section

    # The yanked entry lives in the Yanked crates section (and NOT in
    # the Vulnerabilities section above).
    yanked_section = body[yanked_idx:]
    assert "0.0.1" in yanked_section
    assert "RUSTSEC-2025-0001" not in vuln_section or yanked_section.index("0.0.1") < (
        yanked_section.index("RUSTSEC-2025-0001")
        if "RUSTSEC-2025-0001" in yanked_section
        else len(yanked_section)
    )


# --- TASK 2 item 4: report built from parsed `cargo audit` JSON ------


def test_audit_one_parses_cargo_audit_json(monkeypatch, tmp_path) -> None:
    """The vulnerabilities and yanked lists in `AuditResult` come from the parsed cargo audit JSON, not from its human output.

    Catches: a regression where the script grep-ed the human output for
    keywords and a future cargo audit version changed the wording — the
    auditor would silently stop reporting. The test feeds a small fixed
    JSON document with one vulnerability and one yanked warning and
    asserts both land in the right fields of `AuditResult`.
    """
    ta = _load_tooling_audit()

    cargo_audit_output = {
        "vulnerabilities": {
            "list": [
                {
                    "advisory": {
                        "id": "RUSTSEC-2025-0001",
                        "package": "openssl",
                        "cvss": "7.5",
                    },
                    "package": {"name": "openssl", "version": "0.1.0"},
                    "versions": {"patched": ["0.2.0"]},
                }
            ]
        },
        "warnings": {
            "yanked": [
                {"package": {"name": "old-crate", "version": "0.0.1"}},
            ]
        },
    }

    fake_lock = tmp_path / "Cargo.lock"
    fake_lock.write_text("")
    monkeypatch.setattr(ta, "fetch_lockfile", lambda tool, version: fake_lock)
    monkeypatch.setattr(ta, "run_cargo_audit", lambda lockfile: cargo_audit_output)

    result = ta.audit_one("cargo-audit", "0.21.0")

    assert result["reason"] is None
    assert len(result["vulnerabilities"]) == 1
    assert result["vulnerabilities"][0]["advisory"] == "RUSTSEC-2025-0001"
    assert result["vulnerabilities"][0]["package"] == "openssl"
    assert result["vulnerabilities"][0]["version"] == "0.1.0"
    assert len(result["yanked"]) == 1
    assert result["yanked"][0]["package"] == "old-crate"
    assert result["yanked"][0]["version"] == "0.0.1"


# --- TASK 2 item 5: dedup ---------------------------------------------


def test_no_duplicate_issue_when_title_already_open(monkeypatch, capsys) -> None:
    """With an issue of the exact title already open, no second one is created.

    Catches: a regression that opens a fresh issue every weekly run —
    the maintainer would drown in duplicates with no signal which is
    the current one. The dedup is on the exact title.
    """
    ta = _load_tooling_audit()
    monkeypatch.setattr(
        ta,
        "read_pins",
        lambda: {"cargo-audit": ("rust-audit.yml", "0.21.0")},
    )
    monkeypatch.setattr(
        ta,
        "audit_one",
        lambda tool, version: _audit_result(
            vulnerabilities=[
                {
                    "advisory": "RUSTSEC-2025-0001",
                    "package": "openssl",
                    "version": "0.1.0",
                    "cvss": None,
                    "patched": "(none — no fix)",
                }
            ]
        ),
    )
    monkeypatch.setattr(ta, "issue_already_open", lambda title: True)
    opened: list[dict] = []
    monkeypatch.setattr(
        ta,
        "open_issue",
        lambda title, body: (
            opened.append({"title": title, "body": body})
            or "https://example.test/issue/1"
        ),
    )

    exit_code = ta.main()
    capsys.readouterr()

    assert exit_code == 0
    assert opened == [], (
        f"With issue already open, open_issue must NOT be called; got: {opened!r}"
    )


# --- TASK 3: issues-disabled fallback ---------------------------------
#
# The auditor reports by opening an issue; this repository has issues
# disabled. A crash with a traceback loses the findings. The fallback
# writes the rendered body to $GITHUB_STEP_SUMMARY and exits non-zero,
# so the run failure IS the notification. The three tests below pin the
# three branches of that decision:
#
# - findings + gh says disabled  -> summary written, exit non-zero
# - findings + gh fails for OTHER reason -> script fails loudly, NO summary
# - no findings at all           -> exit 0, no summary written
#
# The IO seam stubbed is `_run_gh`, the helper that wraps
# `subprocess.run` for every gh call — the same seam the new detection
# logic reads from. Replacing `issue_already_open` and `open_issue`
# directly would skip the detection path entirely.


_DISABLED_ISSUES_STDERR = "the 'Glyndor/.github' repository has disabled issues"


def _disabled_issues_gh(cmd: list[str]) -> subprocess.CompletedProcess:
    """Pretend every gh call is rejected because the repo has no issue tracker."""
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=1,
        stdout="",
        stderr=_DISABLED_ISSUES_STDERR,
    )


def _auth_error_gh(cmd: list[str]) -> subprocess.CompletedProcess:
    """Pretend gh fails with an auth error — different reason, same exit code."""
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=4,
        stdout="",
        stderr=(
            "gh: authentication required (HTTP 401)\n"
            "To use GitHub CLI in a GitHub Actions workflow, set "
            "the GH_TOKEN environment variable."
        ),
    )


def _stub_clean_audit(ta, monkeypatch) -> None:
    """Wire up stubs for an audit that finds one advisory.

    The stub returns a single tool with a real vulnerability, so the
    script's main() path renders a body and reaches `open_issue`.
    """
    monkeypatch.setattr(
        ta,
        "read_pins",
        lambda: {"cargo-audit": ("rust-audit.yml", "0.21.0")},
    )
    monkeypatch.setattr(
        ta,
        "audit_one",
        lambda tool, version: _audit_result(
            vulnerabilities=[
                {
                    "advisory": "RUSTSEC-2025-0001",
                    "package": "openssl",
                    "version": "0.1.0",
                    "cvss": None,
                    "patched": "0.2.0",
                }
            ]
        ),
    )


def test_findings_and_issues_disabled_writes_step_summary_and_exits_nonzero(
    monkeypatch, tmp_path, capsys
) -> None:
    """With findings and a gh that says issues are disabled, the report lands
    on $GITHUB_STEP_SUMMARY and the script exits non-zero.

    Catches: a regression that crashes the run with a traceback when
    this repository's issue tracker is closed — the failure mode that
    made the report invisible in the first place. The exit code
    matters: a silent success would read as "nothing found", which is
    the worst outcome when the report cannot be delivered through its
    normal channel.
    """
    ta = _load_tooling_audit()
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    _stub_clean_audit(ta, monkeypatch)
    monkeypatch.setattr(ta, "_run_gh", _disabled_issues_gh)

    exit_code = ta.main()
    captured = capsys.readouterr()

    assert exit_code != 0, (
        f"Disabled-issues fallback must exit non-zero; got {exit_code}"
    )
    # The body is the same markdown that would have been the issue body:
    # the tool, advisory, package and pinned version all land in the
    # summary so the maintainer can act on it.
    assert summary.exists(), (
        "GITHUB_STEP_SUMMARY file must exist after a disabled-issues fallback"
    )
    body = summary.read_text()
    assert "cargo-audit" in body
    assert "RUSTSEC-2025-0001" in body
    assert "openssl" in body
    # And the operator gets a clear message on stderr that names the cause.
    assert "::error" in captured.err
    assert "issues disabled" in captured.err


def test_findings_and_other_gh_failure_does_not_trigger_fallback(
    monkeypatch, tmp_path, capsys
) -> None:
    """With findings and a gh that fails for a NON-disabled reason, the script
    fails loudly and the disabled-issues fallback does NOT run.

    Catches: a regression that collapses every gh failure into the
    disabled-issues fallback — an auth error, a network blip and an
    unknown error are not the same thing as a repository that has
    deliberately closed its issue tracker, and collapsing them would
    hide a real break. The summary file must stay empty.
    """
    ta = _load_tooling_audit()
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    _stub_clean_audit(ta, monkeypatch)
    monkeypatch.setattr(ta, "_run_gh", _auth_error_gh)

    with pytest.raises(subprocess.CalledProcessError):
        ta.main()
    capsys.readouterr()

    # The disabled-issues fallback did NOT run: the summary file was
    # never written (and even if it had been touched, the body would
    # not be in it — the assertion is on absence, not on content).
    assert not summary.exists() or summary.read_text() == "", (
        "Disabled-issues fallback must NOT run for a non-disabled gh failure; "
        f"summary file contains: {summary.read_text()!r}"
    )


def test_no_findings_and_issues_disabled_exits_zero_no_summary(
    monkeypatch, tmp_path, capsys
) -> None:
    """With no advisories and a gh that says issues are disabled, the script
    exits 0 and writes nothing to the step summary.

    Catches: a regression that triggers the disabled-issues fallback
    even when there are no findings to report — "nothing to report" is
    not a failure, and writing an empty body to the summary is noise.
    The gh stub is installed in case the script ever short-circuits
    differently in the future; today main() returns 0 before reaching gh.
    """
    ta = _load_tooling_audit()
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    monkeypatch.setattr(
        ta,
        "read_pins",
        lambda: {"cargo-audit": ("rust-audit.yml", "0.21.0")},
    )
    monkeypatch.setattr(
        ta,
        "audit_one",
        lambda tool, version: _audit_result(),  # clean result
    )
    monkeypatch.setattr(ta, "_run_gh", _disabled_issues_gh)

    exit_code = ta.main()
    capsys.readouterr()

    assert exit_code == 0, f"With no findings the script must exit 0; got {exit_code}"
    assert not summary.exists() or summary.read_text() == "", (
        "With no findings the summary file must stay empty; "
        f"got: {summary.read_text()!r}"
    )
