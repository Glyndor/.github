# installer-contract

Assert install.sh and the release workflow agree on release asset names. Releases are immutable: once a tag ships, its asset names can never change. install.sh downloads `<name>-${OS}-${ARCH}` for the platform it runs on, and the release workflow publishes a fixed list of assets. If the two drift, the installer breaks for users. This catches the drift on the PR, before any tag. Also asserts the release workflow produces a `SHA256SUMS` manifest — the same manifest the install scripts verify downloaded binaries against. A release without one cannot be verified at install time, and a release workflow that stops producing one is a silent breaking change.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/installer-contract.yml@<sha> # vX.Y.Z
```

Pin to a release commit SHA with the version in a comment. Never track a
branch: the SHA pin is what stops a change here reaching a repository
before that repository's own CI has passed on it.

## Status checks it emits

The name a consumer sees is `<caller job id> / <job name>`, where `example` is
the caller's job id from the snippet above — a repository that names its job
`rust` sees `rust / …` instead. **These are the strings a ruleset matches**, and
a required check whose name nothing emits blocks every pull request.

| Check | Emitted when |
|---|---|
| `example / install.sh ↔ release asset names` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `install-script` | string | `install.sh` | no | Path to the install script |
| `release-workflow` | string | `.github/workflows/release.yml` | no | Path to the release workflow that publishes assets |
| `install-ps1-path` | string | `install.ps1` | no | Path to the PowerShell install script (skipped if absent) |

---

Generated from `.github/workflows/installer-contract.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
