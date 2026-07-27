# rust-fuzz

Scheduled fuzzing for Rust crates: runs `cargo fuzz run` (cargo-fuzz + libfuzzer, nightly) against each declared target for a short, bounded time to surface parser panics and edge cases on a fixed tree. Callers wire the schedule (e.g. nightly cron) and pass the target list in their own workflow. This is a smoke run, not a corpus-building soak.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/rust-fuzz.yml@<sha> # vX.Y.Z
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
| `example / cargo fuzz` (one per matrix entry) | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `working-directory` | string | `.` | no | Directory containing the crate (the one holding the fuzz/ dir) |
| `targets` | string | — | yes | JSON array of cargo-fuzz target names, e.g. ["smtp_command","smtp_line","smtp_address"] |
| `max-total-time` | string | `60` | no | Seconds to fuzz each target (libfuzzer -max_total_time) |
| `timeout` | string | `10` | no | Per-input timeout in seconds (libfuzzer -timeout) |
| `toolchain` | string | `nightly-2026-07-16` | no | Rust toolchain to use (cargo-fuzz requires nightly) |
| `cargo-fuzz-version` | string | `0.13.2` | no | Exact version of the tool; bumped via .github releases |
| `rss-limit-mb` | string | — | no | libfuzzer -rss_limit_mb value in MiB; empty (the default) omits the flag entirely, leaving libfuzzer's own default in effect |

---

Generated from `.github/workflows/rust-fuzz.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
