# dco

Enforce the Developer Certificate of Origin: every commit on a pull request must carry a `Signed-off-by:` trailer. Machine-checked attestation gate rather than a convention, which government and enterprise audits expect.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/dco.yml@<sha> # vX.Y.Z
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
| `example / Signed-off-by present on every commit` | always |

## Inputs

None.

---

Generated from `.github/workflows/dco.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
