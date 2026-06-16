# .github

Org-wide defaults inherited by every Glyndor repository that doesn't define its
own: community health files (SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, SUPPORT,
FUNDING), issue/PR templates, the org profile, and reusable CI workflows.

## Reusable CI workflows

```yaml
# .github/workflows/ci.yml in any Glyndor repository
name: CI
on:
  pull_request:
    branches: [develop, main]

jobs:
  rust:
    uses: Glyndor/.github/.github/workflows/rust-ci.yml@<sha> # v1.0.0
    with:
      coverage-threshold: 70
```

Available:

- CI: `rust-ci.yml`, `bun-ci.yml`, `go-ci.yml`, `python-ci.yml`, `shell-ci.yml`
- Rust supply chain: `rust-audit.yml`, `rust-supply-chain.yml`, `rust-debian.yml`
- Release contracts: `installer-contract.yml`
- Policy gates: `dco.yml`, `main-guard.yml`, `line-limit.yml`

## Versioning

Releases are tagged with semver (`vX.Y.Z`). Consumers pin a reusable to the
release **commit SHA** with the version in a comment (the org requires
SHA-pinning):

```yaml
uses: Glyndor/.github/.github/workflows/rust-ci.yml@<sha> # v1.0.0
```

Because the release tag exists, Dependabot in the consuming repo bumps the SHA
and the comment when a newer release ships — no manual pin chasing.

Cutting a release: after changes merge to `main`, publish a new tag —
`gh release create vX.Y.Z --target <main-sha> --generate-notes`. Bump the
**major** for a breaking change to a reusable's inputs or behavior, the
**minor** for additive changes, the **patch** for fixes.

> Actions must be SHA-pinned. Allowed sources: `actions/*`, `Glyndor/*` and
> `oven-sh/setup-bun` (the only third-party exception, needed by `bun-ci.yml`).
