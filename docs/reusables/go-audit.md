# go-audit

Scheduled security audit for Go modules: govulncheck flags known vulnerabilities from the Go vulnerability database, gosec runs static security analysis. Callers wire the schedule (e.g. weekly cron) in their own workflow.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/go-audit.yml@<sha> # vX.Y.Z
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
| `example / govulncheck` | always |
| `example / gosec` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the Go module |
| `govulncheck-version` | string | `v1.1.4` | no | govulncheck version |
| `gosec-version` | string | `v2.27.1` | no | gosec version |
| `gosec-exclude` | string | — | no | Comma-separated gosec rule IDs to exclude (e.g. G104,G115) |

---

Generated from `.github/workflows/go-audit.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
