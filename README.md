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
    uses: Glyndor/.github/.github/workflows/rust-ci.yml@main
    with:
      coverage-threshold: 70
```

Available:

- CI: `rust-ci.yml`, `bun-ci.yml`, `go-ci.yml`, `python-ci.yml`, `shell-ci.yml`
- Rust supply chain: `rust-audit.yml`, `rust-supply-chain.yml`
- Policy gates: `dco.yml`, `main-guard.yml`, `line-limit.yml`

> Actions must be SHA-pinned. Allowed sources: `actions/*`, `Glyndor/*` and
> `oven-sh/setup-bun` (the only third-party exception, needed by `bun-ci.yml`).
