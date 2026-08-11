# empty-diff

Fail a pull request when its diff against the base branch is empty. Eight no-op PRs landed on Glyndor/homebrew-tap and Glyndor/scoop-bucket before this gate existed: the work was already in main via squash-merge, the branch was recreated as `-v2`, and the second merge landed as a commit with zero files changed. CI is happy with that — a commit with no diff is valid git and a green GitHub Actions run, and only `git show --stat` flags it. Add this as an advisory caller in every repository that opens PRs against `main`, then promote it to a required status check once the emitted check name has stayed stable across a few weeks of green. Promoting it before the name has settled is how a phantom required check is created (see the `dco` and `line-limit` reusable docs for the by-name matching detail).

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/empty-diff.yml@<sha> # vX.Y.Z
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
| `example / empty diff` | always |

## Inputs

None.

---

Generated from `.github/workflows/empty-diff.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
