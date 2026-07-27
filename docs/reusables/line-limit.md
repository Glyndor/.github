# line-limit

Enforce the file-size standard: warn past the soft limit, fail past the hard limit. Language-agnostic — scans tracked source files by extension. Counts CODE lines only: blank lines and comment-only lines (including the required doc comments) do not count, so documenting a public API never pushes a file over the limit. The comment detection is a pragmatic heuristic (lines whose first non-space character starts a line/block/doc/template comment).

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/line-limit.yml@<sha> # vX.Y.Z
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
| `example / line limit` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `hard-limit` | number | `500` | no | Files with more lines than this fail the build |
| `soft-limit` | number | `300` | no | Files with more lines than this emit a warning |
| `extensions` | string | `rs go ts tsx js jsx mjs cjs py sh astro vue svelte` | no | Space-separated source file extensions to check |
| `exclude-pattern` | string | — | no | Optional extended regex; matching paths are skipped |

---

Generated from `.github/workflows/line-limit.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
