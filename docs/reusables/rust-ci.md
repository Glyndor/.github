# rust-ci

Format, lint, test and optionally cover, cross-test, MSRV-check, package-check, semver-check and doc-check a Rust crate.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/rust-ci.yml@<sha> # vX.Y.Z
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
| `example / Format & lint` | always |
| `example / Test` | always |
| `example / Test (${{ matrix.os }})` (one per matrix entry) | `inputs.extra-test-os != '[]'` |
| `example / Coverage` | `inputs.coverage-threshold > 0` |
| `example / MSRV (${{ inputs.msrv }})` | `inputs.msrv != ''` |
| `example / Package check` | `inputs.package-check` |
| `example / Semver checks` | `inputs.semver-check` |
| `example / Doc warnings` | `inputs.doc-warnings` |

6 of these 8 are conditional: they do not run,
and therefore emit no check, unless the input in the right-hand column says
so. Requiring one in a ruleset without setting its input is how a phantom
check is created.

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the Cargo workspace |
| `toolchain` | string | `1.98` | no | Rust toolchain to pin the build, lint and test jobs to |
| `coverage-threshold` | number | `0` | no | Minimum line coverage percentage (0 disables the gate) |
| `coverage-ignore-regex` | string | — | no | Regex of file paths to exclude from coverage (e.g. code covered only by a separate DB integration job) |
| `llvm-cov-version` | string | `0.8.7` | no | Exact version of the tool; bumped via .github releases |
| `extra-test-os` | string | `[]` | no | JSON array of extra runner images to also run tests on (e.g. '["macos-latest"]') |
| `podman` | boolean | `false` | no | Start rootless Podman socket before running the coverage job (ubuntu-latest only) |
| `msrv` | string | — | no | Minimum supported Rust version to verify a --locked build against (empty disables the check) |
| `package-check` | boolean | `false` | no | Run cargo publish --dry-run on PRs to catch packaging breakage before tagging |
| `semver-check` | boolean | `false` | no | Run cargo-semver-checks to flag public API breaks against the last published release |
| `semver-checks-version` | string | `0.50.0` | no | Exact version of the tool; bumped via .github releases |
| `doc-warnings` | boolean | `false` | no | Build the docs with -D warnings so broken doc links fail the build |

---

Generated from `.github/workflows/rust-ci.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
