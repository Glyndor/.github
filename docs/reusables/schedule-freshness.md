# schedule-freshness

Fails when a scheduled workflow has not succeeded recently enough. Every other guard in this organisation is an assertion that fails loudly. A cron that stops firing is the exception: it emits nothing at all, and "no alert" is indistinguishable from "all clear". On 2026-06-29 every scheduled workflow in the org stopped. podup and apt recovered on 07-15 because they happened to get activity and a disable/enable cycle; authcore, epistle, unitpm and glyndor.net stayed dark for four more weeks, all of them reporting `active` the whole time. It cost a real finding — authcore's GO-2026-5856 was caught by a hand-run of govulncheck, not by the weekly audit that exists for exactly that. Call this from a workflow that already runs often (normal CI) so the absence of a scheduled run becomes a red check on ordinary work. It is the same idea as apt's `ValidFor: 14d`, which expires the archive rather than letting it serve a frozen snapshot when the pipeline stalls. Add the check only once the schedule has fired successfully at least once — with no successful run on record there is nothing to measure and the job reports that as a failure, which for an established workflow is exactly right.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/schedule-freshness.yml@<sha> # vX.Y.Z
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
| `example / schedule freshness` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `workflow` | string | — | yes | File name of the scheduled workflow to check, e.g. "audit.yml". |
| `max-age-days` | number | — | yes | Fail when the newest successful scheduled run is older than this. Allow about two periods, so a weekly job tolerates one miss: 15 for a weekly schedule, 3 for a daily one. |

---

Generated from `.github/workflows/schedule-freshness.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
