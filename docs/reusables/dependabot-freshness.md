# dependabot-freshness

Fails when Dependabot has not opened a pull request recently enough in the calling repository. The companion guard `schedule-freshness.yml` fails when a *workflow* stops firing. Dependabot is not a workflow — it is an integration with its own schedule, and a silent Dependabot emits nothing. "All up to date" and "Dependabot is dead" produce the same signal: silence. This job converts that silence into a red check on ordinary work, by treating the newest dependabot-authored PR as the last time Dependabot spoke. Two differences from `schedule-freshness.yml`, both forced by Dependabot: 1. The signal is a pull request, not a workflow run. We cannot ask for the newest *scheduled* run of a Dependabot job because there is no such job; Dependabot runs as a GitHub integration. We list recent PRs across all states and pick the newest whose author is Dependabot. 2. The age threshold is higher than the schedule-freshness default. The "2× the period" rule is for workflows that fire on schedule; Dependabot only opens a PR when there is an upstream update, so a healthy but idle Dependabot is expected to be silent for stretches. 15 days is well above one missed run for a daily Dependabot, but still inside the window that catches a dead Dependabot (template-repository went the lifetime of the repo without one before this gate landed). The caller is responsible for granting `contents: read`; a called workflow cannot elevate beyond the permissions of the workflow that calls it, and reading public PR history through the API needs that scope. Add the check only once Dependabot has opened at least one PR in the repo — with nothing on record the job reports that as a failure, which for a live Dependabot is exactly right (it means we cannot even prove Dependabot is alive here). Default shell is pinned to bash: `date -u -d "$latest" +%s` is GNU-date syntax, and a future Windows caller would otherwise silently mis-parse the date and fail the arithmetic on an empty string. `concurrency:` cancels an in-flight run when a newer one starts. The group key uses `github.workflow` so an unrelated caller triggering the same reusable does not collide, and `github.ref` to distinguish per-ref runs.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/dependabot-freshness.yml@<sha> # vX.Y.Z
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
| `example / dependabot freshness` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `max-age-days` | number | — | yes | Fail when the newest Dependabot pull request is older than this. Allow well above one missed run, since Dependabot only opens a PR when there is an upstream update; 15 covers daily cadence. |

---

Generated from `.github/workflows/dependabot-freshness.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
