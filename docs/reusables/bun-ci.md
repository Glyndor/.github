# bun-ci

Install, lint, typecheck, test and build a Bun project, with an optional coverage gate.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/bun-ci.yml@<sha> # vX.Y.Z
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
| `example / Lint, build & test` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing package.json |
| `bun-version` | string | `1.3.14` | no | Exact Bun version to install; bumped via .github releases |
| `coverage-threshold` | number | `0` | no | Minimum line coverage percentage (0 disables the gate; uses bun test --coverage) |

---

Generated from `.github/workflows/bun-ci.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
