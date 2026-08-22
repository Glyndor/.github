# rust-toolchain-watch

Notifies (opens an issue) when upstream Rust ships a stable release strictly newer than the toolchain the caller has pinned. The standard forbids tracking `stable` and records why: an unpinned toolchain upgraded itself on 2026-07-07, widened a clippy lint, and turned every open pull request in podup red on a change nobody made. The producing half of that rule — the pin — lives in this repo's reusables; the consuming half — a deliberate bump through a new `.github` release — has had nothing proposing it, so Rust sat three days stale (1.98.0 released 2026-08-18 against a `1.97` pin) with nobody told. The shape mirrors podup's podman-version-watch: daily cron (the caller's schedule), query upstream, dedupe against open issues, open a labelled tracking issue when there is a newer release. A watcher that goes red would interrupt unrelated work for something nobody chose to do today — the open-issue shape is what makes it quiet when current and loud only when an upgrade is owed. Where it lives: `.github` cannot open issues in itself (issues are disabled here), and a central cron on `.github`'s own `GITHUB_TOKEN` cannot see the caller's issue list — same shape as the cross-repo pin-policy guard retired in #119. So this is a reusable the consumer calls from its own scheduled workflow, and the issue it opens lands in the consumer's repository. Upstream source: `static.rust-lang.org/dist/channel-rust-stable.toml`. That is the same manifest `rustup` reads when it installs a toolchain, served by the Rust project itself — no third-party service, no auth, no rate limit. The CI standard allowlists exactly one third-party service (repology.org, for podup's Podman watch) and adding another needs its own justification; the channel file is first-party Rust infrastructure and needs none. The version extracted from the file is validated against a strict SemVer regex before any other use, exactly the way podman-version-watch handles its third-party-supplied version. Add as advisory — not required — until it has been seen opening an issue for the right reason, and the emitted name has been read off a real run. The standard's "a gate that has never fired is not a gate" rule applies in full; a check whose only state is green has proven nothing. `concurrency:` cancels an in-flight run when a newer one starts. The group key uses `github.workflow` so an unrelated caller triggering the same reusable does not collide, and `github.ref` to distinguish per-ref runs. Default shell is pinned to bash: the version comparison uses `printf | sort -V`, GNU sort semantics, and a future Windows caller would otherwise silently mis-compare and fail closed on an empty string.

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/rust-toolchain-watch.yml@<sha> # vX.Y.Z
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
| `example / rust toolchain watch` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `toolchain` | string | — | yes | The Rust toolchain this consumer is currently pinning (e.g. "1.97"). The watcher opens an issue when upstream stable is strictly newer than this. |

---

Generated from `.github/workflows/rust-toolchain-watch.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
