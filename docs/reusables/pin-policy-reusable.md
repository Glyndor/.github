# pin-policy-reusable

Fail when a reusable pin in this repository points at a SHA whose surface differs from the latest released tag. The pin policy in standards/ci is "bump only when the tag's surface differs from the current pin" — a tighter rule than "always-latest", which would burn the open-pull-requests-limit on no-op bumps. The policy was justified by a one-line tag log per repo, with the implicit promise that someone (a script, a CI job) would keep the log honest. The log is not maintained and the bytes are; this job is the question, not the ledger. The reusable is the consumer-side form of the previous cross-repo guard (pin-policy.yml on .github's own schedule/push). The cross-repo form read every consumer's workflows with .github's GITHUB_TOKEN, which could not reach a private consumer (run 31658807184, 2026-08-13, skipped template-repository after a 404 and reported `OK: 15  DIFF: 0`). Each consumer running this reusable uses its own token, which always covers its own files; private consumers are no longer an exception. Default shell is pinned to bash: the inner run block does not work on PowerShell, and a future Windows caller would otherwise get empty strings where it expects exit codes. `concurrency:` cancels an in-flight run when a newer one starts. The group key uses `github.workflow` so an unrelated caller triggering the same reusable does not collide, and `github.ref` to distinguish per-ref runs.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/pin-policy-reusable.yml@<sha> # vX.Y.Z
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
| `example / pin policy` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `workdir` | string | `.` | no | Path to the checked-out caller repository, relative to the reusable's `actions/checkout`. Defaults to the workspace root, which is right for the usual caller that checks out its own repository there. |

---

Generated from `.github/workflows/pin-policy-reusable.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
