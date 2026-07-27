# rust-debian

Build a .deb with dpkg-buildpackage, and (optionally) prove an air-gapped build works from vendored crates with no crates.io access. Optionally upload the produced package as an artifact for a release pipeline to consume.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/rust-debian.yml@<sha> # vX.Y.Z
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
| `example / dpkg-buildpackage` | always |
| `example / build (vendored / offline)` | `${{ inputs.check-vendored }}` |

1 of these 2 are conditional: they do not run,
and therefore emit no check, unless the input in the right-hand column says
so. Requiring one in a ruleset without setting its input is how a phantom
check is created.

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `package-name` | string | — | yes | Debian package name (the .deb is <package-name>_*.deb) |
| `runner` | string | `ubuntu-latest` | no | Runner to build on |
| `debian-image` | string | `debian:trixie@sha256:fac46bff2e02f51425b6e33b0e1169f55dfb053d83511ca28aa50c09fd5ed7a4` | no | Container image to build in (a stable suite is reproducible) |
| `arch` | string | — | no | Architecture to verify/stage (empty matches any) |
| `upload-artifact` | boolean | `false` | no | Upload the produced .deb as an artifact |
| `artifact-name` | string | — | no | Artifact name when upload-artifact is true |
| `check-vendored` | boolean | `false` | no | Also run an offline build from vendored crates |
| `offline-cargo-args` | string | — | no | Extra cargo args for the offline build (e.g. feature flags) |

---

Generated from `.github/workflows/rust-debian.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
