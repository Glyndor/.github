# rust-supply-chain

Generate the supply-chain artifacts government and enterprise consumers expect: a machine-readable SBOM (CycloneDX, per US EO 14028) and a third-party license attribution (NOTICES). Run on every PR to keep the generators honest; the release workflow attaches the same artifacts to each published release.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/rust-supply-chain.yml@<sha> # vX.Y.Z
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
| `example / SBOM and license attribution` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the Cargo workspace |
| `toolchain` | string | `1.98` | no | Rust toolchain to pin the SBOM and license job to |
| `about-template` | string | `about.hbs` | no | cargo-about handlebars template |
| `cyclonedx-version` | string | `0.5.9` | no | Exact version of cargo-cyclonedx to install; bumped via .github releases |
| `cargo-about-version` | string | `0.9.2` | no | Exact version of cargo-about to install; bumped via .github releases |

---

Generated from `.github/workflows/rust-supply-chain.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
