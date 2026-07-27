# powershell-ci

PSScriptAnalyzer lint for repositories shipping .ps1 scripts (podup's install.ps1 today; unitpm and klyradb are expected to gain their own PowerShell installers later). Replaces podup's inline .github/workflows/lint-powershell.yml with one reviewed implementation — the swap itself is Phase 4.2, not part of this change. Runner is windows-latest and `defaults: run: shell: pwsh` is deliberate, not an oversight: the CI standard's rule that a reusable job must default to bash on a non-Linux runner exists because `$VAR` under PowerShell reads a PowerShell variable, not the environment, so env-passed values silently become empty strings. That trap only bites a job whose *content* is meant to be POSIX shell running on Windows. This job's content IS PowerShell, so pwsh is the correct shell, not the thing being guarded against — and every input below is still read via `$env:VAR` (pwsh's real environment-variable syntax) rather than a bare `$VAR`, for the same reason the standard calls out. pssa-version's default was checked against the live PowerShell Gallery (podup's own lint-powershell.yml has no pin at all — floats on whatever `Install-Module PSScriptAnalyzer -Force` resolves to that day); 1.25.0 was the current non-prerelease release at the time this default was set. `paths` is a "<dir>/**/<pattern>"-shaped glob (default "**/*.ps1"), but the **-segment is stripped rather than handed to Get-ChildItem: its own docs warn against combining -Path with -Recurse for wildcard matching and confirm there is no "**" arbitrary-depth token at all — the documented way to match a pattern at every depth is -LiteralPath (a plain directory) + -Recurse + -Include, which is what the step below builds from this input.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/powershell-ci.yml@<sha> # vX.Y.Z
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
| `example / pssa` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `pssa-version` | string | `1.25.0` | no | Exact PSScriptAnalyzer version to install from the PowerShell Gallery; bumped via .github releases |
| `paths` | string | `**/*.ps1` | no | "<dir>/**/<pattern>"-shaped glob (relative to the repository root) matching the PowerShell scripts to analyze at any depth under <dir>; default scans the whole repository for *.ps1 files |
| `exclude-rules` | string | — | no | Comma-separated PSScriptAnalyzer rule names to exclude from the gate (passed to -ExcludeRule), for rules a script violates on purpose — e.g. PSAvoidUsingWriteHost in an installer that talks to a human over stdout. Empty excludes nothing. |

---

Generated from `.github/workflows/powershell-ci.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
