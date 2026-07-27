# shell-ci

Lint every shell script in the repository: bash -n catches syntax errors, shellcheck catches quoting, unset-variable and other correctness bugs. Optionally runs the repository's shell test suite (`test-command`).

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/shell-ci.yml@<sha> # vX.Y.Z
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
| `example / shellcheck` | always |
| `example / test` | `inputs.test-command != ''` |

1 of these 2 are conditional: they do not run,
and therefore emit no check, unless the input in the right-hand column says
so. Requiring one in a ruleset without setting its input is how a phantom
check is created.

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory to scan for shell scripts |
| `severity` | string | `style` | no | Minimum shellcheck severity to report (style\|info\|warning\|error) |
| `shellcheck-version` | string | `v0.11.0` | no | Exact shellcheck release tag to install from koalaman/shellcheck; bumped via .github releases |
| `test-command` | string | — | no | Command running the repository's shell test suite (skipped when empty) |
| `apt-packages` | string | — | no | Space-separated apt packages the test suite needs |

---

Generated from `.github/workflows/shell-ci.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
