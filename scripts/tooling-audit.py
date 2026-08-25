#!/usr/bin/env python3
"""Audit the dependency trees the Rust tooling CI installs at run time.

The reusables under `.github/workflows/` (rust-audit, rust-ci, rust-fuzz,
rust-supply-chain) install seven third-party tools via
`cargo install --locked`. `workflow-lint`'s `tooling-isolation` rule
already keeps those installs out of any job holding a secret — that is
the containment half of Glyndor/apt#121. The auditing half is this
script.

The method: `cargo install --locked <tool>` does NOT resolve a new tree.
It builds the tool from the tool's OWN bundled `Cargo.lock`, which
crates.io packs inside the `.crate` archive next to `Cargo.toml`. So
the lockfile that needs auditing is the one inside the `.crate` of the
pinned tool version — not this repository's `Cargo.lock` (which has
nothing to do with the runner's install) and not the tool's git HEAD
(which may have moved on since the pin).

For each pinned tool, this script downloads the `.crate` from
`https://static.crates.io/crates/<name>/<name>-<version>.crate`,
extracts it, runs `cargo audit --file <lockfile> --json --deny warnings`
on the bundled `Cargo.lock`, and reports the advisories and yanked
crates the audit surfaces.

Why a finding here is upstream's advisory and not a defect in these
workflows: `cargo install --locked` is pinned to a specific release of
the tool, but the transitive dependency tree inside that release is
fixed at the time of the release and can grow new advisories after the
fact. The advisories are properties of the upstream tree, not of the
workflow file that calls `cargo install`. The right response to a
finding is to bump the pin (and let the next run re-audit the new
release), not to panic — and the tooling-isolation rule means none of
these tools runs in a job holding a secret, so an upstream advisory
cannot exfiltrate one.

If a `.crate` has no bundled `Cargo.lock`, this script reports that
tool as NOT AUDITED. A crate without a lockfile is valid (it is what
plain `cargo package` produces when the project does not commit one),
and the honest answer is that the dependency tree cannot be pinned
down from here — we will not invent a tree by resolving one ourselves,
because resolving requires transitive network access and produces a
tree that may differ from what `cargo install --locked` would actually
build.

Pin sources: same files as scripts/pin-watch.py. The two scripts read
the same input-default values (via the helper imported below), so a
bump in one place cannot leave this script auditing a version nobody
installs. If a future pin lives in a workflow pin-watch.py does not
cover, add it there too — the alternative is two drift detectors that
quietly disagree.

Reporting: collect vulnerabilities and yanked crates per tool, open
ONE issue titled exactly `Advisories in the tooling CI installs`,
skip if an issue with that exact title is already open. Labels:
type:security, prio:P2, status:ready, area:ci, effort:M.

Exit codes: 0 on a successful run, including one that finds
advisories. An upstream advisory must not block every pull request in
the organisation by failing this self-CI; the issue it opens is how
that finding reaches the maintainer. Exit non-zero ONLY when the
script itself failed — a download that did not come back, an
unparseable `cargo audit` output, a pin it could not read, a tool it
could not audit for a reason that was not "no bundled Cargo.lock".

The advisory-not-blocking-PR rule does NOT extend to a repository
that has deliberately closed its issue tracker. When findings exist
AND `gh` reports "the '... repository' has disabled issues", the
report is written to `$GITHUB_STEP_SUMMARY` instead and the run
exits non-zero. These workflows do not run on pull requests (they
are scheduled only), so failing one blocks nothing, and GitHub
notifies on a failed scheduled run on the default branch. A silent
success would read as "nothing found", which is the worst outcome
when the report cannot be delivered through its normal channel.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# Reuse the input-default reader from pin-watch.py rather than
# duplicating the regex. The two scripts must read the same pins, so a
# bump in one place cannot leave this script auditing a version nobody
# installs — the imported helper is what enforces that. Adding a new
# pin to this script therefore needs a matching entry in pin-watch.py's
# PIN_SOURCES (or vice versa); otherwise this script silently fails to
# read the pin (the helper returns None and main exits non-zero).
#
# pin-watch.py uses a hyphen in its filename and so cannot be imported
# with a plain `import` statement (Python module names cannot contain
# hyphens). importlib.util loads the file by path under a synthetic
# name; that is the only reason this dance exists, not a separate
# reason to re-pin the reader here.
_PIN_WATCH_PATH = Path(__file__).resolve().parent / "pin-watch.py"
_pin_watch_spec = importlib.util.spec_from_file_location(
    "pin_watch_for_tooling_audit", _PIN_WATCH_PATH
)
assert _pin_watch_spec is not None, "pin-watch.py spec could not be built"
assert _pin_watch_spec.loader is not None, "pin-watch.py has no loader"
pin_watch = importlib.util.module_from_spec(_pin_watch_spec)
_pin_watch_spec.loader.exec_module(pin_watch)

WORKFLOWS_DIR = Path(".github/workflows")

# The seven tools this script audits, the workflow each pin lives in,
# and the input name that holds the version. The workflow + input name
# is the same shape pin-watch.py's PIN_SOURCES uses, which is the point
# of importing pin-watch.py's reader above: the two scripts read the
# same pin, so a bump on one side cannot leave the other auditing a
# version nobody installs. `kind` is always "input" here — every pin
# this script needs is a `workflow_call.inputs.<name>.default`, not a
# literal env value.
TOOLS: list[tuple[str, str, str]] = [
    ("cargo-audit", "rust-audit.yml", "cargo-audit-version"),
    ("cargo-deny", "rust-audit.yml", "cargo-deny-version"),
    ("cargo-llvm-cov", "rust-ci.yml", "llvm-cov-version"),
    ("cargo-semver-checks", "rust-ci.yml", "semver-checks-version"),
    ("cargo-fuzz", "rust-fuzz.yml", "cargo-fuzz-version"),
    ("cargo-cyclonedx", "rust-supply-chain.yml", "cyclonedx-version"),
    ("cargo-about", "rust-supply-chain.yml", "cargo-about-version"),
]

UA = "glyndor-tooling-audit/1.0 (+https://github.com/Glyndor/.github)"

ISSUE_TITLE = "Advisories in the tooling CI installs"
ISSUE_LABELS = ("type:security", "prio:P2", "status:ready", "area:ci", "effort:M")


def _http_get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def read_pins() -> dict[str, tuple[str, str]]:
    """Read every pin from its workflow file via the shared helper.

    Mirrors pin-watch.py's read_pins() in shape, but for THIS script's
    tool list rather than pin-watch.py's full pin list. Returns
    {tool_name: (source_file, version)}. Fails the run if a pin
    cannot be read — the auditor must not silently skip a tool it was
    asked to audit.
    """
    cache: dict[str, str] = {}
    pins: dict[str, tuple[str, str]] = {}
    for tool, source_file, input_name in TOOLS:
        if source_file not in cache:
            cache[source_file] = (WORKFLOWS_DIR / source_file).read_text()
        text = cache[source_file]
        v = pin_watch._read_input_default(text, input_name)
        if v is None:
            print(
                f"::error file={source_file}::could not read input "
                f"default for {input_name} (tool: {tool})",
                file=sys.stderr,
            )
            sys.exit(1)
        pins[tool] = (source_file, v)
    return pins


def fetch_lockfile(tool: str, version: str) -> Path:
    """Download the `.crate`, extract it, return the path to its Cargo.lock.

    The download goes to a NamedTemporaryFile so the file lives long
    enough to be opened by tarfile, then a fresh TemporaryDirectory
    holds the extracted contents. Returns the Path to Cargo.lock.

    Raises RuntimeError on any failure. Callers convert that into a
    "NOT AUDITED" entry — the only exception is "no bundled
    Cargo.lock", which is reported separately and is a normal case.
    """
    url = f"https://static.crates.io/crates/{tool}/{tool}-{version}.crate"
    try:
        crate_bytes = _http_get_bytes(url)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"download HTTP {e.code}: {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"download failed: {e.reason}: {url}") from e

    try:
        with tempfile.TemporaryDirectory(prefix="tooling-audit-") as tmp:
            tmp_path = Path(tmp)
            crate_path = tmp_path / f"{tool}-{version}.crate"
            crate_path.write_bytes(crate_bytes)
            try:
                with tarfile.open(crate_path, "r:gz") as tf:
                    tf.extractall(tmp_path, filter="data")
            except (tarfile.TarError, OSError) as e:
                raise RuntimeError(f"extract failed for {tool} {version}: {e}") from e

            root = tmp_path / f"{tool}-{version}"
            lockfile = root / "Cargo.lock"
            if not lockfile.is_file():
                # Move the extracted crate outside the tempdir before
                # we lose it, so a debug invocation can still poke at
                # the contents. The caller catches FileNotFoundError
                # and reports the tool as NOT AUDITED.
                persistent = (
                    Path(tempfile.gettempdir())
                    / f"tooling-audit-{tool}-{version}.crate"
                )
                if not persistent.exists():
                    persistent.write_bytes(crate_bytes)
                raise FileNotFoundError(f"{lockfile} not present in crate")
            # Copy to a stable path that survives the tempdir's
            # cleanup. cargo audit only needs to read the file.
            stable = (
                Path(tempfile.gettempdir()) / f"tooling-audit-{tool}-{version}.lock"
            )
            stable.write_bytes(lockfile.read_bytes())
            return stable
    except FileNotFoundError:
        raise
    except Exception as e:
        raise RuntimeError(f"unexpected error processing {tool} {version}: {e}") from e


def run_cargo_audit(lockfile: Path) -> dict:
    """Run `cargo audit --file <lockfile> --json --quiet --deny warnings`.

    Parses the JSON output. Returns the parsed dict on success.
    Raises RuntimeError when cargo audit exits non-zero with output
    we cannot make sense of, OR when the JSON is not parseable.

    Note: --deny warnings does NOT change the JSON output, only the
    exit code, and we deliberately IGNORE the exit code here — a
    non-zero exit means "advisories exist", which is a finding for
    the report, not a failure of this script. Exit-code-as-finding
    would force the script to fail closed on every advisory, which is
    exactly what the module docstring says we must not do.
    """
    proc = subprocess.run(
        [
            "cargo",
            "audit",
            "--file",
            str(lockfile),
            "--json",
            "--quiet",
            "--deny",
            "warnings",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError(
            f"cargo audit produced no JSON for {lockfile}: stderr={proc.stderr!r}"
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"cargo audit JSON unparseable for {lockfile}: {e}; first 200 chars: {stdout[:200]!r}"
        ) from e


# --- Per-tool audit result -----------------------------------------------


# A finding for one tool. `vulnerabilities` is a list of dicts with
# keys (advisory, package, version, cvss, patched); `yanked` is a list
# of dicts with keys (package, version); `reason` is set only when the
# tool was NOT AUDITED (no Cargo.lock in the .crate, or download
# failed) — the tool ran but produced no usable lockfile. Exactly one
# of `vulnerabilities`/`yanked`/`reason` is populated per AuditResult.
AuditResult = dict


def audit_one(tool: str, version: str) -> AuditResult:
    """Audit the pinned version of one tool. Returns a finding dict.

    Never raises. Returns a finding with `reason` set on every
    failure mode — a network error, an unparseable audit, a missing
    lockfile. main() decides which reasons warrant exit non-zero.
    """
    try:
        lockfile = fetch_lockfile(tool, version)
    except FileNotFoundError:
        # The .crate extracted cleanly but had no Cargo.lock. This is
        # the "crate without a lockfile" case the docstring calls out:
        # not an audit failure, just an honest "we cannot pin down the
        # tree from here".
        return {
            "tool": tool,
            "version": version,
            "vulnerabilities": [],
            "yanked": [],
            "reason": "no bundled Cargo.lock in .crate",
        }
    except RuntimeError as e:
        # Network / extraction failure. Caller will exit non-zero.
        return {
            "tool": tool,
            "version": version,
            "vulnerabilities": [],
            "yanked": [],
            "reason": f"{e}",
        }

    try:
        data = run_cargo_audit(lockfile)
    except RuntimeError as e:
        return {
            "tool": tool,
            "version": version,
            "vulnerabilities": [],
            "yanked": [],
            "reason": f"{e}",
        }

    vulns: list[dict] = []
    for v in data.get("vulnerabilities", {}).get("list", []):
        advisory = v.get("advisory", {})
        package = v.get("package", {})
        versions = v.get("versions", {})
        patched = versions.get("patched") or []
        vulns.append(
            {
                "advisory": advisory.get("id", "?"),
                "package": advisory.get("package") or package.get("name", "?"),
                "version": package.get("version", "?"),
                "cvss": advisory.get("cvss"),
                "patched": ", ".join(patched) if patched else "(none — no fix)",
            }
        )

    yanked: list[dict] = []
    for item in data.get("warnings", {}).get("yanked", []):
        pkg = item.get("package", {})
        yanked.append(
            {
                "package": pkg.get("name", "?"),
                "version": pkg.get("version", "?"),
            }
        )

    return {
        "tool": tool,
        "version": version,
        "vulnerabilities": vulns,
        "yanked": yanked,
        "reason": None,
    }


# --- Reporting -----------------------------------------------------------


def render_body(results: list[AuditResult]) -> str:
    """Render the issue body. Caller has already decided there is something to report."""
    lines: list[str] = []

    lines.append("## Vulnerabilities")
    lines.append("")
    lines.append("| Tool | Tool version | Advisory | Package | Severity | Fixed in |")
    lines.append("|---|---|---|---|---|---|")
    any_vuln = False
    for r in results:
        for v in r["vulnerabilities"]:
            any_vuln = True
            cvss = v["cvss"] if v["cvss"] else "(no CVSS recorded)"
            lines.append(
                f"| `{r['tool']}` | `{r['version']}` | `{v['advisory']}` | "
                f"`{v['package']}` `{v['version']}` | {cvss} | {v['patched']} |"
            )
    if not any_vuln:
        lines.append("| _none_ |  |  |  |  |  |")
    lines.append("")

    lines.append("## Yanked crates")
    lines.append("")
    lines.append(
        "`cargo install --locked` does no resolution, so a yanked crate "
        'is installed even after the maintainer marks it "do not use" '
        "— `cargo audit` reports these as warnings rather than "
        "vulnerabilities, but the maintainer's intent is the same."
    )
    lines.append("")
    lines.append("| Tool | Package | Version |")
    lines.append("|---|---|---|")
    any_yanked = False
    for r in results:
        for y in r["yanked"]:
            any_yanked = True
            lines.append(f"| `{r['tool']}` | `{y['package']}` | `{y['version']}` |")
    if not any_yanked:
        lines.append("| _none_ |  |  |")
    lines.append("")

    lines.append("## Not audited")
    lines.append("")
    lines.append(
        "These tools could not be audited this run. A crate without a "
        "bundled `Cargo.lock` is valid (the project's release process "
        "just does not commit one); the dependency tree cannot be "
        "pinned down from here, and we will not invent one. Download "
        "failures are reproducible as the tool's own bundle, so the "
        "audit can be re-run when the network is healthy."
    )
    lines.append("")
    lines.append("| Tool | Tool version | Reason |")
    lines.append("|---|---|---|")
    any_na = False
    for r in results:
        if r["reason"]:
            any_na = True
            lines.append(f"| `{r['tool']}` | `{r['version']}` | {r['reason']} |")
    if not any_na:
        lines.append("| _none_ |  |  |")
    lines.append("")

    lines.append(
        "These are advisories in upstream dependency trees rather than "
        "defects in these workflows; the tooling-isolation rule means "
        "none of these tools runs in a job holding a secret, so the "
        "question each finding asks is whether to bump the tool, not "
        "whether to panic."
    )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Opened by the `tooling-audit` self-CI workflow. Closing this "
        "issue without acting is the wrong response — bump the pinned "
        "tool version in the named workflow file, then close the "
        "issue once the next scheduled run reports nothing._"
    )
    return "\n".join(lines) + "\n"


def issue_already_open(title: str) -> bool:
    """Return True if an open issue with this exact title exists.

    On a `gh` failure that says the repository has disabled issues,
    returns False so the caller proceeds to `open_issue` (which fails
    the same way and triggers the step-summary fallback). For any
    OTHER `gh` failure, the function re-raises — a token without
    permission or a network error is not the same as a repository
    that deliberately has no issue tracker, and collapsing them
    would hide a real break.
    """
    proc = _run_gh(
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
        ]
    )
    if proc.returncode != 0:
        if _gh_says_issues_disabled(proc):
            return False
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr
        )
    titles = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return title in titles


def open_issue(title: str, body: str) -> str:
    """Open the issue. If gh reports issues are disabled, write the
    body to $GITHUB_STEP_SUMMARY and raise `_IssuesDisabledError` so
    `main()` exits non-zero with a clear message — the run failure
    is the notification when the issue channel is closed. Any OTHER
    gh failure propagates as `subprocess.CalledProcessError`; the
    step-summary fallback is for the disabled-issues case only.
    """
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    for label in ISSUE_LABELS:
        cmd.extend(["--label", label])
    proc = _run_gh(cmd)
    if proc.returncode != 0:
        if _gh_says_issues_disabled(proc):
            _write_to_step_summary(body)
            raise _IssuesDisabledError(title)
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr
        )
    return proc.stdout.strip()


def _run_gh(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a gh command with stdout+stderr captured. Never raises.

    Callers inspect the return code and the combined output themselves,
    so the "has disabled issues" fallback can match on the stderr
    before propagating any other error.
    """
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _gh_says_issues_disabled(proc: subprocess.CompletedProcess) -> bool:
    """True iff gh's output indicates the repository has disabled issues.

    Matches on the literal phrase `has disabled issues` rather than on
    exit code, because `gh` reuses a small set of non-zero exit codes
    (4 for auth, 1 for "not found") across many distinct failure modes —
    collapsing them all into "issues disabled" would hide a real break.
    The phrase is what `gh issue list` and `gh issue create` print when
    the repository has deliberately closed the issue channel.
    """
    if proc.returncode == 0:
        return False
    combined = (proc.stdout or "") + (proc.stderr or "")
    return "has disabled issues" in combined


def _write_to_step_summary(body: str) -> None:
    """Append body to $GITHUB_STEP_SUMMARY when that env var is set.

    The step summary file is the run's summary page on GitHub Actions;
    when the repository has no issue tracker, the summary is the only
    place the report can land. Always prints the body to stdout so it
    is in the local log when the script is run outside CI.
    """
    print(body)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(body)
            if not body.endswith("\n"):
                f.write("\n")
    except OSError as e:
        print(
            f"::warning::could not write to GITHUB_STEP_SUMMARY ({summary_path}): {e}",
            file=sys.stderr,
        )


class _IssuesDisabledError(Exception):
    """Internal sentinel raised by `open_issue` when gh reports issues
    are disabled on this repository.

    The body has already been written to $GITHUB_STEP_SUMMARY by the
    time this is raised. `main()` catches it to exit 1 with a clear
    message — the run failure is the notification when the issue
    channel is closed.
    """


# --- Main flow -----------------------------------------------------------


def main() -> int:
    pins = read_pins()
    print("Pins read from workflow files:")
    for tool in sorted(pins):
        src, v = pins[tool]
        print(f"  {tool:22s} {v!r:14s} ({src})")
    print()

    results: list[AuditResult] = []
    for tool, (src, version) in sorted(pins.items()):
        print(f"Auditing {tool} {version} (from {src})...")
        r = audit_one(tool, version)
        results.append(r)
        if r["reason"]:
            print(f"  NOT AUDITED: {r['reason']}")
        else:
            print(
                f"  {len(r['vulnerabilities'])} vulnerabilities, "
                f"{len(r['yanked'])} yanked"
            )
    print()

    print("Per-tool results:")
    for r in sorted(results, key=lambda x: x["tool"]):
        if r["reason"]:
            print(f"  {r['tool']:22s} {r['version']!r:14s} NOT AUDITED: {r['reason']}")
        else:
            vuln_n = len(r["vulnerabilities"])
            yanked_n = len(r["yanked"])
            print(
                f"  {r['tool']:22s} {r['version']!r:14s} vulns={vuln_n} yanked={yanked_n}"
            )
    print()

    # Decide whether to open an issue AND whether to exit non-zero.
    # An advisory is a finding, NOT a failure of the script. The
    # exit-code-as-finding trap is exactly what this script exists to
    # avoid — see the module docstring.
    has_vulns = any(r["vulnerabilities"] for r in results)
    has_yanked = any(r["yanked"] for r in results)
    not_audited = [r for r in results if r["reason"]]
    # A script-level failure is a tool we could not audit for a reason
    # OTHER than "no bundled Cargo.lock". The "no lockfile" case is a
    # honest answer (the docstring calls it out), not a failure.
    script_failures = [
        r for r in not_audited if not r["reason"].startswith("no bundled Cargo.lock")
    ]

    if not has_vulns and not has_yanked and not not_audited:
        print("No advisories or yanked crates found. tooling-audit is current.")
        return 0

    body = render_body(results)
    print("---")
    print("Issue body:")
    print(body)
    print("---")

    if has_vulns or has_yanked:
        if issue_already_open(ISSUE_TITLE):
            print(f"Issue {ISSUE_TITLE!r} is already open — not creating a duplicate.")
        else:
            try:
                url = open_issue(ISSUE_TITLE, body)
            except _IssuesDisabledError:
                # Findings exist, the issue channel is closed, and the
                # body has already been written to $GITHUB_STEP_SUMMARY.
                # Exiting non-zero is the notification — a silent
                # success would read as "nothing found", which is the
                # worst outcome when the report cannot be delivered
                # through its normal channel.
                print(
                    f"::error::{ISSUE_TITLE}: this repository has issues "
                    f"disabled; the audit has been written to "
                    f"GITHUB_STEP_SUMMARY instead — the run failure is "
                    f"the notification.",
                    file=sys.stderr,
                )
                return 1
            except subprocess.CalledProcessError as e:
                # The audit data is already on stdout; the operator
                # can see what was found. But the issue was not
                # delivered, which means the maintainer was not
                # notified — that is a script failure, not a finding.
                print(
                    f"::error::gh issue create failed (exit {e.returncode}); "
                    f"audit data above was not delivered as an issue",
                    file=sys.stderr,
                )
                return 1
            print(f"Opened: {url}")

    # Exit non-zero ONLY when the script itself failed. A network
    # error fetching a .crate, an unparseable cargo audit JSON, a pin
    # that could not be read — those are script failures, and the
    # next run should retry. An advisory is not.
    if script_failures:
        print(f"Script failed for {len(script_failures)} tool(s); exiting non-zero.")
        for r in script_failures:
            print(f"  {r['tool']}: {r['reason']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
