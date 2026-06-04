# Contributing to Glyndor

Thank you for your interest. Please read this before doing anything else.

## Contribution model

Glyndor projects manage sensitive server infrastructure (SSH, firewall, ports,
mail). Because of that, **write access is invitation-only**: maintainers invite
contributors they trust to the project teams.

If you are not (yet) an invited contributor you can still help:

- **Report bugs** through the issue templates.
- **Report security issues** privately — see [SECURITY.md](SECURITY.md). Never
  open a public issue for a vulnerability.
- **Propose features** through the feature request template. Discussion happens
  in the issue before any code is written.

Unsolicited pull requests from outside collaborators may be closed. Open an
issue first.

## Branch flow

```
topic branch ──PR──▶ develop ──PR──▶ main
```

- `main` is always stable. Only `develop` is merged into it.
- `develop` is the integration branch.
- Every change gets its own topic branch off `develop`, named
  `<type>/<short-description>`, e.g. `feat/wireguard-peer-list`,
  `fix/ssh-key-validation`.
- All merges happen through pull requests. Direct pushes to `main` and
  `develop` are blocked by repository rules — no exceptions, including
  maintainers.

## Commits

- Write commits in **English**, using
  [Conventional Commits](https://www.conventionalcommits.org/):
  `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`,
  `ci: ...`, `chore: ...`.
- Keep the subject under 50 characters; explain the *why* in the body when it
  is not obvious.
- Sign your commits (SSH or GPG signing).

## Pull requests

- Target `develop`, never `main` (release PRs from `develop` to `main` are
  opened by maintainers).
- CI must pass. Resolve every review thread before merge.
- Keep PRs focused — one topic per PR.

## Code style

Each repository's CI enforces formatting and linting (rustfmt + clippy, gofmt +
vet, ESLint/Prettier, ruff). Run the linters locally before pushing; the CI
configuration is the source of truth.

## Language

All public artifacts — code, comments, commits, issues, PRs, docs — are written
in **English**.
