# .github

Org-wide defaults for all Glyndor repositories.

## What lives here

| Path | Purpose |
|---|---|
| `profile/README.md` | Organization profile page |
| `SECURITY.md` | Default security policy (private vulnerability reporting) |
| `CONTRIBUTING.md` | Contribution model, branch flow, commit conventions |
| `.github/ISSUE_TEMPLATE/` | Default issue forms |
| `.github/PULL_REQUEST_TEMPLATE.md` | Default PR template |
| `.github/workflows/*-ci.yml` | Reusable CI workflows (Rust, Go, Node, Python) |

Repositories without their own community health files inherit the ones in this
repo automatically.

## Using the reusable workflows

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

Same pattern for `go-ci.yml`, `node-ci.yml` and `python-ci.yml`.

> Note: the organization requires actions to be SHA-pinned. Third-party actions
> are not allowed — only `actions/*` and `Glyndor/*`.
