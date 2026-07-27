# go-fuzz

Scheduled fuzzing for Go modules: runs `go test -fuzz` against each declared target for a short, bounded time to surface parser panics and edge cases on a fixed tree. Callers wire the schedule (e.g. weekly cron) and pass the target list in their own workflow. This is a smoke run, not a corpus-building soak.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/go-fuzz.yml@<sha> # vX.Y.Z
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
| `example / go test -fuzz (smoke)` (one per matrix entry) | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the Go module |
| `targets` | string | — | yes | JSON array of {"package","func"} objects to fuzz, e.g. [{"package":"./auth/email","func":"FuzzValidateAndNormalize"}] |
| `fuzztime` | string | `60s` | no | How long to fuzz each target (go test -fuzztime) |

---

Generated from `.github/workflows/go-fuzz.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
