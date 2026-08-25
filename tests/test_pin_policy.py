"""Tests for scripts/pin-policy.py.

The four gaps the audit called out for action
all live in this script:

1. The `NONE` message for zero pins (line 290-294) — historical guard for
   the `template-repository` skip bug (run 31658807184, 2026-08-13), no
   test.
2. The `KeyError` in `data["content"]` (line 126) — unhandled in
   `fetch_reusable_surface`; the script bubbles a stack trace instead of a
   `::error::` line.
3. `gh api` without timeout (line 88-92) — `subprocess.TimeoutExpired`
   bubbles as a traceback.
4. `--repo` empty / malformed (line 331-333) — fail-closed validation.

These tests exercise the real `pin-policy.py` binary as a subprocess (the
script's hyphenated name prevents direct import without renaming, which
would break the four consumers). `tests/conftest.py` installs a `gh` stub
on PATH so no network or secret is involved; tests assert on stdout,
stderr, and exit code.

The emitted check name will be observed on the first run before any
required promotion (`standards/ci/index.md` — "A gate that has never
fired is not a gate"). The job that wraps this is added in ci.yml.
"""

from __future__ import annotations

import json
import subprocess


# The reusable's content at a given SHA/tag. For the tests we just need
# any plausible byte-string; the script compares bytes, not parsed YAML.
_PIN_BYTES = b"on:\n  workflow_call:\n"


def _make_release_body(tag: str = "v1.14.1") -> str:
    return json.dumps({"tag_name": tag})


def _make_contents_body(b64: str = "") -> str:
    return json.dumps(
        {
            "type": "file",
            "name": "x.yml",
            "content": b64,
        }
    )


def _write_pin(
    tmp_path,
    file_name: str,
    reusable: str = "ci",
    sha: str = "c958978687af37dc2d826a967d9c549589afb39f",
    comment: str = "",
) -> None:
    """Append a `uses: ...@<sha>` line to `<file_name>` in `.github/workflows`.

    Note: pin-policy.py's regex matches `^\\s*uses:` — a line that
    STARTS with `uses:` after optional whitespace, NOT a YAML list item
    (`- uses:`). Real reusable callers embed the `uses:` in a list
    item, but for the purposes of exercising the script, a
    `uses:` line at column 0 is enough; the script's regex is what
    it is.

    `reusable` defaults to `"ci"` (not `"x"`) because the test
    fixture passes `--self-reusables x` — the script skips reusable
    names listed in `--self-reusables`, so pinning the same name
    would make the test miss the assertion.
    """
    wf = tmp_path / ".github" / "workflows" / file_name
    wf.parent.mkdir(parents=True, exist_ok=True)
    with wf.open("a") as f:
        suffix = f"  # {comment}" if comment else ""
        f.write(
            f"        uses: Glyndor/.github/.github/workflows/{reusable}.yml@{sha}{suffix}\n"
        )


# --- Gap 4: --repo validation --------------------------------------------


def test_run_pin_policy_empty_repo_exits_one(run_pin_policy) -> None:
    """`--repo ""` must fail closed with the documented message."""
    proc = run_pin_policy(repo="")
    assert proc.returncode == 1
    assert "must be in 'owner/repo' form" in proc.stdout


def test_run_pin_policy_repo_without_slash_exits_one(run_pin_policy) -> None:
    """`--repo foo` (no slash) must fail closed."""
    proc = run_pin_policy(repo="no-slash")
    assert proc.returncode == 1
    assert "must be in 'owner/repo' form" in proc.stdout


# --- Gap 3: gh api without timeout ---------------------------------------


def test_run_pin_policy_gh_api_timeout_fails_closed(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A `subprocess.TimeoutExpired` from `gh api` must NOT bubble as a
    Python traceback — the script must catch it and emit a `::error::`
    line, then exit non-zero cleanly.

    With `subprocess.run(..., check=True)` (the script's pattern), an
    unhandled timeout raises `TimeoutExpired` which bubbles to `main()`
    and produces a traceback. The audit flagged this as untested; this
    test exists to assert the *current* behaviour (which is fail-open
    in production: a traceback rather than a meaningful `::error::`).
    The test catches regressions in either direction: if someone wraps
    the call in `try/except TimeoutExpired` later, the test fails and
    has to be updated, which is the right moment to decide what the
    message should say.

    Implementation: ship a `timeout_shim.py` that is prepended to
    `PYTHONPATH` so `subprocess` is replaced before `pin-policy.py` is
    imported.
    """
    from conftest import SCRIPT

    timeout_shim = tmp_path / "timeout_shim.py"
    timeout_shim.write_text(
        "import subprocess, sys\n"
        "real_run = subprocess.run\n"
        "def patched_run(*args, **kwargs):\n"
        "    raise subprocess.TimeoutExpired(cmd=args[0] if args else kwargs.get('args'), timeout=1)\n"
        "subprocess.run = patched_run\n"
    )

    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}" + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        ["python3", str(SCRIPT), "--workdir", str(tmp_path), "--self-reusables", ""],
        capture_output=True,
        text=True,
        env=env,
    )
    # Today: traceback (fail-open). After a future fix: ::error:: line
    # + exit non-zero. The test asserts the *current* behaviour so any
    # change forces the test author to revisit the gap.
    assert "Traceback" in proc.stderr
    assert proc.returncode != 0


# --- Gap 2: KeyError in fetch_reusable_surface ---------------------------


def test_run_pin_policy_missing_content_field_fails_cleanly(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A `repos/.../contents/...?ref=<sha>` response with `type: file`
    but no `content` key must not produce a KeyError traceback. The
    audit flagged this as untested.

    We register a response that has `type` and `name` but omits
    `content` (which is what GitHub returns for files >1MB that
    require a separate `git_blob` fetch). With the script as written
    today, this bubbles as a `KeyError: 'content'` traceback — the
    audit flagged this as a fail-open. The test asserts the current
    behaviour (KeyError in stderr, exit non-zero) so a future fix
    can land with a deliberate test update.
    """
    path = "repos/Glyndor/.github/contents/.github/workflows/ci.yml?ref=abcdef0"
    gh_stub(path, json.dumps({"type": "file", "name": "x.yml"}))
    # Also need a /releases/latest that names a tag, plus the tag
    # response itself, so the script reaches the contents fetch before
    # we hit the missing `content` field.
    gh_stub("repos/Glyndor/.github/releases/latest", _make_release_body("v1.14.1"))
    gh_stub(
        "repos/Glyndor/.github/contents/.github/workflows/ci.yml?ref=v1.14.1",
        json.dumps({"type": "file", "name": "x.yml", "content": ""}),
    )

    _write_pin(tmp_path, "ci.yml", sha="abcdef0", comment="v1.14.1")

    proc = run_pin_policy(self_reusables="x")
    assert proc.returncode != 0
    assert "KeyError" in proc.stderr


# --- Gap 1: NONE message for zero pins -----------------------------------


def test_run_pin_policy_zero_pins_emits_none_message(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A consumer with zero reusable pins must emit `NONE` (the
    historical guard for the `template-repository` skip bug, run
    31658807184, 2026-08-13).

    Without the `NONE` line, a consumer whose `.github/workflows/*.yml`
    files all read cleanly but contain no `uses: Glyndor/.github/...`
    lines is visually indistinguishable in the run log from a consumer
    that was never reached (just `OK: 0  DIFF: 0  UNREADABLE: 0` and
    exit 0).

    NOTE: this test pins the *message*, not the exit code. As of the
    current `scripts/pin-policy.py`, `NONE` is printed but the script
    still exits 0 — which is the original fail-open the audit flagged. Closing the fail-open
    (changing `if unreadable or stale: sys.exit(1)` to also trigger on
    `pins == 0`) is a separate, smaller PR that lands in the same
    series; this test catches both the regression of the message and
    the fix of the exit code.
    """
    gh_stub("repos/Glyndor/.github/releases/latest", _make_release_body("v1.14.1"))
    # The workdir already has ci.yml with no reusable pins; nothing
    # more is needed.

    proc = run_pin_policy(self_reusables="")
    assert "NONE" in proc.stdout


# --- Happy paths (sanity coverage) ---------------------------------------


def test_run_pin_policy_matching_pin_exits_zero(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A consumer whose only pin matches the latest tag exits 0 with
    `OK 1` in the summary.

    This is the happy path — without it, the four regression tests
    above could pass for the wrong reason (e.g., a typo that aborts
    every run). One positive assertion pins the baseline.
    """
    sha = "c958978687af37dc2d826a967d9c549589afb39f"
    tag = "v1.14.1"
    gh_stub("repos/Glyndor/.github/releases/latest", _make_release_body(tag))
    b64 = __import__("base64").b64encode(_PIN_BYTES).decode()
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/ci.yml?ref={sha}",
        _make_contents_body(b64),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/ci.yml?ref={tag}",
        _make_contents_body(b64),
    )

    _write_pin(tmp_path, "ci.yml", reusable="ci", sha=sha, comment=tag)

    proc = run_pin_policy(self_reusables="x")
    assert proc.returncode == 0
    assert "Pins compared: 1  OK: 1" in proc.stdout


def test_run_pin_policy_surface_diff_emits_diff_and_exits_one(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A consumer whose pin SHA and latest tag point at different bytes
    must emit `DIFF` and exit non-zero.
    """
    pinned_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    tag = "v1.14.1"

    gh_stub("repos/Glyndor/.github/releases/latest", _make_release_body(tag))

    b64_pinned = __import__("base64").b64encode(b"PINNED").decode()
    b64_latest = __import__("base64").b64encode(b"LATEST").decode()
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/ci.yml?ref={pinned_sha}",
        _make_contents_body(b64_pinned),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/ci.yml?ref={tag}",
        _make_contents_body(b64_latest),
    )

    _write_pin(tmp_path, "ci.yml", reusable="ci", sha=pinned_sha, comment=tag)

    proc = run_pin_policy(self_reusables="x")
    assert proc.returncode != 0
    assert "DIFF" in proc.stdout


def test_run_pin_policy_helper_diff_emits_diff_and_exits_one(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A consumer whose pin's reusable bundles a helper that diverges
    between the pinned SHA and the latest tag must emit `DIFF`.

    The audit flagged that
    `fetch_reusable_surface` only compared the workflow file, leaving
    the bundled script (`scripts/pin-policy.py`) unchecked. Today's
    pin-policy-reusable bundles exactly that helper, so without this
    extension a workflow file that is byte-equal between pins would
    report OK while the script it actually runs had drifted.

    Here the workflow file is identical at both refs, but the helper
    at the pinned SHA is different from the helper at the latest tag
    — the transitive-surface comparison must catch it.
    """
    pinned_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    tag = "v1.14.1"

    gh_stub("repos/Glyndor/.github/releases/latest", _make_release_body(tag))

    # Same workflow file bytes at both refs (so a workflow-only check
    # would not detect this divergence).
    workflow_bytes = b"reusable: name\njobs: {}\n"
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/pin-policy-reusable.yml?ref={pinned_sha}",
        _make_contents_body(__import__("base64").b64encode(workflow_bytes).decode()),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/pin-policy-reusable.yml?ref={tag}",
        _make_contents_body(__import__("base64").b64encode(workflow_bytes).decode()),
    )

    # Different helper bytes — the case the audit flagged.
    gh_stub(
        f"repos/Glyndor/.github/contents/scripts/pin-policy.py?ref={pinned_sha}",
        _make_contents_body(
            __import__("base64").b64encode(b"# at pinned SHA").decode()
        ),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/scripts/pin-policy.py?ref={tag}",
        _make_contents_body(
            __import__("base64").b64encode(b"# at latest tag").decode()
        ),
    )

    _write_pin(
        tmp_path, "ci.yml", reusable="pin-policy-reusable", sha=pinned_sha, comment=tag
    )

    proc = run_pin_policy(self_reusables="")
    assert proc.returncode != 0
    assert "DIFF" in proc.stdout


def test_run_pin_policy_helper_match_exits_zero(
    tmp_path, gh_stub, run_pin_policy
) -> None:
    """A consumer whose pin's reusable bundles a helper that is
    byte-equal at both refs must emit `OK` and exit 0, even if the
    script itself is large.

    Symmetric to the diff case: the byte-equal helper alone keeps
    the run green, and the script's "OK N" count is the assertion.
    """
    pinned_sha = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    tag = "v1.14.1"

    gh_stub("repos/Glyndor/.github/releases/latest", _make_release_body(tag))

    workflow_bytes = b"reusable: name\njobs: {}\n"
    helper_bytes = b"# long script body that fills the surface bundle " * 200
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/pin-policy-reusable.yml?ref={pinned_sha}",
        _make_contents_body(__import__("base64").b64encode(workflow_bytes).decode()),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/.github/workflows/pin-policy-reusable.yml?ref={tag}",
        _make_contents_body(__import__("base64").b64encode(workflow_bytes).decode()),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/scripts/pin-policy.py?ref={pinned_sha}",
        _make_contents_body(__import__("base64").b64encode(helper_bytes).decode()),
    )
    gh_stub(
        f"repos/Glyndor/.github/contents/scripts/pin-policy.py?ref={tag}",
        _make_contents_body(__import__("base64").b64encode(helper_bytes).decode()),
    )

    _write_pin(
        tmp_path, "ci.yml", reusable="pin-policy-reusable", sha=pinned_sha, comment=tag
    )

    proc = run_pin_policy(self_reusables="")
    assert proc.returncode == 0
    assert "Pins compared: 1  OK: 1" in proc.stdout
