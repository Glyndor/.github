# workflow-lint

Lint the CALLING repository's own workflow YAML with actionlint — the release workflows and other per-repo callers that live outside this repository and are today validated by nobody. This is where the phantom-required-check naming mismatches and the PowerShell $VAR-under-pwsh trap have actually shipped, because nothing caught them before a consumer's CI ran for real. Contrast with actionlint.yml in this repository: that one is this repo's own self-CI over ITS reusables; this one runs actionlint over the CALLER's checkout, wherever the calling job invokes it from. actionlint's embedded shellcheck pass otherwise falls back to whatever shellcheck the runner image ships, which floats independently of the org's pinned version (shell-ci.yml). Installing the same pinned shellcheck here and pointing actionlint at it with -shellcheck keeps that pass reproducible too.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/workflow-lint.yml@<sha> # vX.Y.Z
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
| `example / workflow-lint` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `shellcheck-version` | string | `v0.11.0` | no | Exact shellcheck release tag to install from koalaman/shellcheck for actionlint's embedded shellcheck pass; bumped via .github releases |

---

Generated from `.github/workflows/workflow-lint.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
