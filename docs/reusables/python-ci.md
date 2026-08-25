# python-ci

Lint with a pinned ruff and test with a pinned pytest.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/python-ci.yml@<sha> # vX.Y.Z
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
| `example / Lint & test` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the Python project |
| `python-version` | string | `3.13` | no | Python version |
| `ruff-version` | string | `0.12.0` | no | ruff version to pin |
| `pytest-version` | string | `9.1.1` | no | pytest version to pin |
| `coverage-threshold` | number | `0` | no | Minimum coverage percentage (0 disables the gate; uses pytest-cov) |

---

Generated from `.github/workflows/python-ci.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
