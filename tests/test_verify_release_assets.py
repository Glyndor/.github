"""Tests for scripts/verify-release-assets.py.

The script exists because the gate it replaces was unpassable by construction,
so the tests that matter are the ones that would have caught that: a release
staged correctly must pass, and every shape of missing file must fail. The
second case is the point — the old clause looked only for `SHA256SUMS` among a
workflow's declared matrix assets, so it could see neither a missing manifest
(the manifest is never a matrix asset) nor a missing `SHA256SUMS.sig` (it never
looked at the signature at all, though `install.sh` aborts without it).

Exercised as a subprocess against the real script, following the shape
`tests/test_pin_policy.py` established and `standards/testing/index.md`
recommends over mocking. No network, no fixtures beyond a temp directory: the
script's only inputs are two text files and a directory listing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify-release-assets.py"

# Trimmed to the lines the script reads: the artifact template, the OS/ARCH
# arms, and the ${BASE_URL} fetches. Shaped after podup's real install.sh.
INSTALL_SH = """\
#!/usr/bin/env bash
set -euo pipefail

case "$(uname -s)" in
	Linux) OS="linux" ;;
	Darwin) OS="darwin" ;;
esac
case "$(uname -m)" in
	x86_64) ARCH="x86_64" ;;
	aarch64 | arm64) ARCH="arm64" ;;
esac

ARTIFACT="widget-${OS}-${ARCH}"

download "${BASE_URL}/${ARTIFACT}" "${TMP_DIR}/${ARTIFACT}"
download "${BASE_URL}/SHA256SUMS" "${TMP_DIR}/SHA256SUMS"
download "${BASE_URL}/SHA256SUMS.sig" "${TMP_DIR}/SHA256SUMS.sig"
"""

INSTALL_PS1 = """\
$Arch = 'x86_64'
if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $Arch = 'arm64' }
$Artifact = "widget-windows-$Arch.exe"
$sumsPath = Get-ReleaseFile 'SHA256SUMS'
"""

# What a complete release stages: the four unix artifacts install.sh can ask
# for, the two windows ones install.ps1 can, and the manifest with its
# signature.
COMPLETE = [
    "widget-linux-x86_64",
    "widget-linux-arm64",
    "widget-darwin-x86_64",
    "widget-darwin-arm64",
    "widget-windows-x86_64.exe",
    "widget-windows-arm64.exe",
    "SHA256SUMS",
    "SHA256SUMS.sig",
]


@pytest.fixture
def release(tmp_path: Path) -> Path:
    """A directory holding install.sh, install.ps1 and a complete staging dir."""
    (tmp_path / "install.sh").write_text(INSTALL_SH)
    (tmp_path / "install.ps1").write_text(INSTALL_PS1)
    staged = tmp_path / "staged"
    staged.mkdir()
    for name in COMPLETE:
        (staged / name).write_bytes(b"")
    return tmp_path


def run(root: Path, *, ps1: bool = True) -> subprocess.CompletedProcess:
    cmd = [
        "python3",
        str(SCRIPT),
        "--workdir",
        str(root / "staged"),
        "--install-script",
        str(root / "install.sh"),
    ]
    if ps1:
        cmd += ["--install-ps1", str(root / "install.ps1")]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_complete_release_passes(release: Path) -> None:
    result = run(release)
    assert result.returncode == 0, result.stderr
    assert "all 8 files" in result.stdout


def test_missing_manifest_signature_fails(release: Path) -> None:
    """The regression the replaced clause could not see.

    install.sh downloads SHA256SUMS.sig and aborts without it, but the old
    check looked only for the string "SHA256SUMS" among the workflow's declared
    matrix assets — so a release that produced the manifest and dropped its
    signature was indistinguishable from a good one.
    """
    (release / "staged" / "SHA256SUMS.sig").unlink()
    result = run(release)
    assert result.returncode == 1
    assert "SHA256SUMS.sig" in result.stderr


def test_missing_manifest_fails(release: Path) -> None:
    (release / "staged" / "SHA256SUMS").unlink()
    (release / "staged" / "SHA256SUMS.sig").unlink()
    result = run(release)
    assert result.returncode == 1
    assert "SHA256SUMS" in result.stderr


def test_missing_artifact_fails(release: Path) -> None:
    (release / "staged" / "widget-darwin-arm64").unlink()
    result = run(release)
    assert result.returncode == 1
    assert "widget-darwin-arm64" in result.stderr


def test_windows_artifact_required_only_with_ps1(release: Path) -> None:
    """install.ps1 contributes the windows names and nothing else.

    Without it the same staging dir must still pass, which is what makes the
    check usable by a product that ships no Windows installer.
    """
    (release / "staged" / "widget-windows-arm64.exe").unlink()
    assert run(release).returncode == 1
    assert run(release, ps1=False).returncode == 0


def test_absent_ps1_is_skipped_not_fatal(release: Path) -> None:
    (release / "install.ps1").unlink()
    result = run(release)
    assert result.returncode == 0, result.stderr
    assert "not found, skipped" in result.stdout


def test_installer_that_fetches_nothing_fails_closed(release: Path) -> None:
    """An installer the script cannot read is not evidence of a good release."""
    (release / "install.sh").write_text(
        'ARTIFACT="widget-${OS}-${ARCH}"\nOS="linux"\nARCH="arm64"\n'
    )
    result = run(release)
    assert result.returncode == 1
    assert "fetches nothing from the release" in result.stderr


def test_unparsable_artifact_template_fails_closed(release: Path) -> None:
    (release / "install.sh").write_text(
        INSTALL_SH.replace('ARTIFACT="widget-${OS}-${ARCH}"', 'ARTIFACT="widget"')
    )
    result = run(release)
    assert result.returncode == 1
    assert "ARTIFACT template" in result.stderr


def test_missing_workdir_fails_closed(release: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workdir",
            str(tmp_path / "nonexistent"),
            "--install-script",
            str(release / "install.sh"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
