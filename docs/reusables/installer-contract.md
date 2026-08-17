# installer-contract

Assert install.sh and the release workflow agree on release asset names. Releases are immutable: once a tag ships, its asset names can never change. install.sh downloads `<name>-${OS}-${ARCH}` for the platform it runs on, and the release workflow publishes a fixed list of assets. If the two drift, the installer breaks for users. This catches the drift on the PR, before any tag. Scope — this gate reads declarations, and only declarations. It compares two files and answers "do install.sh and release.yml agree on the asset names?". That is a cross-reference between two statements of intent, and parsing YAML is the right way to answer it. It deliberately does NOT answer "does the release produce these files". Until 2026-08-17 it tried to, with a third check that required `SHA256SUMS` to appear among the parsed `asset:` keys. Those keys are the build matrix, and the manifest is computed FROM the matrix outputs in a later step, so it can never be one of them: the check was unpassable by construction, and the only way to satisfy it was to declare a matrix entry that produced nothing — the exact defect it existed to catch. It had never run green in any repository. Existence is answered where it can be answered honestly, against the staged files at release time, by `scripts/verify-release-assets.py`.

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
