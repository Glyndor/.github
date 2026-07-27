# rust-audit

Scheduled supply-chain audit for Rust crates: cargo-audit flags RUSTSEC advisories, cargo-deny enforces the license/ban/source policy in deny.toml. Callers wire the schedule (e.g. weekly cron) in their own workflow.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/rust-audit.yml@<sha> # vX.Y.Z
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
| `example / cargo audit` | always |
| `example / cargo deny` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the Cargo workspace |
| `toolchain` | string | `1.97` | no | Rust toolchain to pin the audit and deny jobs to |
| `cargo-audit-version` | string | `0.22.2` | no | Exact version of cargo-audit to install; bumped via .github releases |
| `cargo-deny-version` | string | `0.20.2` | no | Exact version of cargo-deny to install; bumped via .github releases |

---

Generated from `.github/workflows/rust-audit.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
