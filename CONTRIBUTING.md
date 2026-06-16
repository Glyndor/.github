# Contributing to Glyndor

Thank you for your interest. Please read this before doing anything else.

## Contribution model

Glyndor projects manage sensitive server infrastructure (SSH, firewall, ports,
containers, mail). Because of that, **write access is invitation-only**:
maintainers invite contributors they trust to the project teams.

If you are not (yet) an invited contributor you can still help:

- **Report bugs** through the issue templates.
- **Report security issues** privately — see [SECURITY.md](SECURITY.md). Never
  open a public issue for a vulnerability.
- **Propose features** through the feature request template. Discussion happens
  in the issue before any code is written.

Pull request creation is restricted to collaborators — if you are not one,
open an issue instead.

## Before you start

- Search existing issues and PRs before opening new ones
- For large changes, open an issue first to discuss the approach
- Check the repository's README for project-specific setup, scope and
  constraints — some projects explicitly list what they will not accept
- All contributions are in **English** — code, comments, commits, issues, PRs

## Branch flow

```
topic branch ──PR──▶ develop ──PR──▶ main
```

- `main` is always stable. Only `develop` is merged into it.
- `develop` is the integration branch.
- Every change gets its own topic branch off `develop`, named
  `<type>/<short-description>`, e.g. `feat/wireguard-peer-list`,
  `fix/ssh-key-validation`.
- All merges happen through pull requests — direct pushes to `main` and
  `develop` are blocked by repository rules, no exceptions, including
  maintainers.

## Commits

- [Conventional Commits](https://www.conventionalcommits.org/):

  ```
  feat(dashboard): add PSK rotation without tunnel restart
  fix(agent): correct nonce cleanup interval
  chore(ci): update ubuntu runner to 24.04
  ```

- Subject ≤ 50 characters. Body only when the "why" isn't obvious from the code.
- One commit per logical change on your topic branch — they are reviewed
  individually in the PR, then squashed on merge.
- Sign off every commit (`git commit -s`, DCO). Commits on `develop` and `main`
  are cryptographically signed by GitHub automatically through the merge flow.

## Pull requests

- Target `develop`, never `main` (release PRs from `develop` to `main` are
  opened by maintainers).
- Squash merge into `develop` — one commit per PR, titled with the PR title
  (Conventional Commits). Release PRs (`develop` → `main`) use a merge commit.
- CI must pass. Resolve every review thread before merge.
- Keep PRs focused — one concern per PR. Fill out the PR template completely.

## Code style

CI enforces formatting and linting; run it locally before pushing. Org-wide
conventions:

**Rust:**
- `cargo fmt` and `cargo clippy -- -D warnings` must pass
- No `unwrap()` in production paths — use proper error handling
- UTC everywhere — no local timestamps
- UUID v7 for all table IDs
- Queries via `sqlx` with bound parameters only — no string interpolation in SQL
- Shell commands via `std::process::Command::arg()` — never `sh -c "...{input}..."`

**Go:**
- `gofmt` and `go vet` must pass; table-driven tests preferred

**Next.js / TypeScript:**
- `bun` is the package manager — commit `bun.lock`; CI runs `bun install --frozen-lockfile`
- `biome format` + `biome lint` must pass
- Server Components by default — `"use client"` only when required
- All user-visible text in i18n files — never hardcoded strings
- Zod schemas for all input validation

**Python:**
- `ruff check` and `ruff format` must pass

**Shell scripts:**
- `shellcheck` must pass
- Header block required (description, usage, requirements)

## Testing changes that touch system integration

Some behavior cannot be tested in CI (nftables, WireGuard, Podman, systemd,
installers). Changes in those areas require testing on local VMs or a real
VPS — note in your PR which scenarios you ran. Repositories document their
specific VM test matrix in their README when applicable.
