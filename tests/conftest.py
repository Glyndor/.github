"""Shared fixtures for pin-policy.py tests.

The script under test is `scripts/pin-policy.py` — pure Python but invoked
as a CLI with a hyphen in the name, so it cannot be imported as a module
without renaming. Tests therefore exercise it as a subprocess (the
"black-box over the real binary" shape that `standards/testing/index.md`
recommends over mocking).

The script's only side-effecting call is `subprocess.run(["gh", "api", ...])`
on the upstream reusable. We install a stub `gh` on PATH ahead of every
test that captures args+stdin and replies from a fixture map, so no
network is involved and every code path of `pin-policy.py` is reachable
without secrets.
"""

from __future__ import annotations

import pytest
import os
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "pin-policy.py"


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    """Return a temp workdir already populated with one trivial workflow.

    Tests add or replace files inside it as needed; pin-policy.py reads
    `.github/workflows/*.yml` from the workdir it is passed.
    """
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        textwrap.dedent(
            """\
            name: CI
            on: [push, pull_request]
            jobs:
              build:
                runs-on: ubuntu-latest
                steps:
                  - run: echo hi
            """
        )
    )
    return tmp_path


GH_STUB_TEMPLATE = """\
#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" > "$STUB_LOG_DIR/args"
cat > "$STUB_LOG_DIR/stdin"
# Args: $0=gh (script name), $1=api, $2=<path>,
# $3=--jq (may be absent), $4=<filter> (only when $3 is --jq).
path="$2"
body=$(case "$path" in
{case_lines}\
    *) echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
esac)
# Apply the jq filter if --jq was passed. We use the `${var-}` form so
# that `set -u` does not trip on an unset $3 when the script calls us
# without `--jq`.
if [ "${3-}" = "--jq" ]; then
    printf '%s' "$body" | jq -r "${4-}"
else
    printf '%s' "$body"
fi
"""


@pytest.fixture
def gh_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install a `gh` stub on PATH; return a `set_response` helper.

    The stub logs its call to `$STUB_LOG_DIR/{args,stdin}` and emits a
    response body from the configured map. The map is keyed by the
    request path; an unknown path causes a `gh: Not Found (HTTP 404)`
    so tests fail-closed on unexpected network shape.
    """
    log_dir = tmp_path / "gh-log"
    log_dir.mkdir()

    responses: dict[str, str] = {}

    def set_response(path: str, body: str) -> None:
        """Register a response body for a `gh api <path>` request."""
        responses[path] = body

    stub_dir = tmp_path / "gh-bin"
    stub_dir.mkdir()

    def _install() -> Path:
        case_lines: list[str] = []
        for path, body in responses.items():
            # Escape backslashes and single quotes for embedding inside a
            # bash single-quoted string. The body itself is emitted by
            # printf '%s' on a single line; newlines in the response are
            # encoded as literal "\\n" in the captured stream.
            esc = body.replace("\\", "\\\\").replace("'", "'\\''")
            case_lines.append(f"    {path}) printf '%s' '{esc}' ;;")
        # Use string replacement, not .format(), because the template
        # contains `${var-}` (bash default-value syntax) which collides
        # with .format()'s `{name}` substitution.
        stub_text = GH_STUB_TEMPLATE.replace(
            "{case_lines}",
            "\n".join(case_lines) + ("\n" if case_lines else ""),
        )
        stub = stub_dir / "gh"
        stub.write_text(stub_text)
        stub.chmod(0o755)
        return log_dir

    log_dir_path = _install()

    def add_response(path: str, body: str) -> None:
        set_response(path, body)
        _install()

    monkeypatch.setenv("STUB_LOG_DIR", str(log_dir_path))
    monkeypatch.setenv("PATH", f"{stub_dir}{os.pathsep}{os.environ['PATH']}")
    return add_response


@pytest.fixture
def run_pin_policy(workdir: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a callable that runs `pin-policy.py` against `workdir`.

    Captures stdout/stderr/exit. The stub `gh` is installed by the
    `gh_stub` fixture (callers should request it).
    """
    # Default repo: a sensible non-empty slug, so the script passes its
    # `--repo` validation when the test does not override. Tests that
    # want to exercise the validation explicitly pass `repo=""` and the
    # fixture below forwards it as `--repo ""` (literal).
    monkeypatch.setenv("GITHUB_REPOSITORY", "Glyndor/test-consumer")

    def _run(
        *,
        repo: str | None = None,
        self_reusables: str = "",
        workdir_path: Path | None = None,
    ) -> subprocess.CompletedProcess:
        cmd = [
            "python3",
            str(SCRIPT),
            "--workdir",
            str(workdir_path or workdir),
            "--self-reusables",
            self_reusables,
        ]
        if repo is not None:
            # Forward even empty strings — argparse distinguishes
            # `--repo ""` (explicit empty) from omitting `--repo`
            # (default from env). The `if repo:` check above would
            # silently drop the test's intent.
            cmd += ["--repo", repo]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

    return _run
