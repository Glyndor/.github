# go-ci

Build, vet and test a Go module, with an optional coverage gate.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/go-ci.yml@<sha> # vX.Y.Z
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
| `working-directory` | string | `.` | no | Directory containing the Go module |
| `coverage-threshold` | number | `0` | no | Minimum coverage percentage across the module (0 disables the gate) |
| `per-package-coverage-threshold` | number | `0` | no | Minimum coverage percentage for every individual package (0 disables the gate). An aggregate threshold on a module whose packages differ in risk rewards covering the easy ones — a fully covered helper package pays for a thin one that parses untrusted input. This asserts the floor holds everywhere rather than on average. |

---

Generated from `.github/workflows/go-ci.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
