# release-verify

Extracts the org's most dangerous copy-pasted logic: the release-workflow verify job every product's release.yml has hand-rolled. This is the 1.9.0 lesson — podup shipped a .deb labelled 1.8.0 because debian/changelog disagreed with Cargo.toml, and the same release rotated the signing key, so apt (the one path left for already-installed users) was the one that broke. A human comparing version strings by eye is not a control; the release only runs once, at tag time, and by then the mistake is immutable. Every gate below is one reviewed implementation instead of N hand-copies drifting apart. Checkout is pinned to `ref: inputs.tag`, not left to the run's default ref. That's what lets a workflow_dispatch re-verify an arbitrary past tag, and it's also why the reachability gate below resolves the commit with `git rev-parse HEAD` after that checkout rather than reading `$GITHUB_SHA` — GITHUB_SHA reflects the event that triggered the run (for a workflow_dispatch fired from the default branch, that is NOT the tag's commit), so it would silently check the wrong commit's ancestry on exactly the re-run path this input exists for. extra-version-files patterns are grep -E (extended regex), not a literal string match — unescaped parens are a grouping metacharacter, not literal characters. "^podup (VERSION)" silently fails to match debian/changelog's real "podup (1.10.1) unstable; ..." line (grep -qE returns no-match, which is fail-closed, but confusing); the correct pattern escapes them: "^podup \(VERSION\)". Callers must escape their own metacharacters. extra-version-files' flat path:pattern form matches anywhere in the file, not just the project's own entry — "Cargo.lock:version = \"VERSION\"" matches ANY dependency at that version. podup's own Cargo.lock has httparse and hyper both at 1.10.1, so that flat pattern still passes even when podup's own entry is the stale one. Anything not already scoped by a unique prefix (debian/changelog's "^podup (" is; a lockfile's bare "version = " line is not) needs the anchored path:anchor::pattern form instead: pattern must match within the 3 lines following a line matching anchor, and a missing anchor is its own distinct error, not a silent pass. Tags are mutable and this job re-resolves the tag name to a commit at checkout time, so a later job in the same run has no way to guarantee it builds the commit that was actually verified unless it's told which one that was — hence the verified-sha output below (git rev-parse HEAD right after checkout). Any job that builds or publishes after this one should check out needs.verify.outputs.verified-sha (or assert it equals its own HEAD), so a tag force-moved mid-run can't cause the build to diverge from what verify attested. Callers should resolve their own tag input the same way regardless of trigger: tag: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref_name }}

## Calling it

```yaml
# .github/workflows/ci.yml in the consuming repository
jobs:
  example:
    uses: Glyndor/.github/.github/workflows/release-verify.yml@<sha> # vX.Y.Z
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
| `example / verify` | always |

## Inputs

| Input | Type | Default | Required | Description |
|---|---|---|---|---|
| `manifest-file` | string | — | yes | Path to the manifest file whose version is authoritative (e.g. Cargo.toml, package.json); ignored when manifest-kind is go |
| `manifest-kind` | string | — | yes | Manifest format determining how the version is extracted — cargo (first `version = "X"` in the Cargo.toml [package] section), node (package.json .version via jq), or go (modules are versioned by the tag itself; manifest comparison is skipped, other gates still run) |
| `extra-version-files` | string | — | no | Newline-separated entries. path is everything before the first colon. What follows is the anchored form when it contains the literal delimiter "::": anchor is the text before that first "::", pattern is everything after it and may itself contain further colons (e.g. "Cargo.lock:name = \"podup\"::version = \"VERSION\"" — use this form whenever the pattern isn't already scoped to the right entry by a unique prefix, since a bare "version = " match can hit an unrelated dependency at the same version). Otherwise the whole remainder is a flat grep -E pattern, matched anywhere in the file, colons and all (e.g. "debian/changelog:^podup \(VERSION\)"; a flat pattern is free to contain a literal colon, e.g. "notes.txt:Category: VERSION" matches that literal text anywhere in the file). An anchor containing a literal colon is not supported — the first "::" found always wins. An anchor must also uniquely identify one entry: if it matches more than one line, grep -A3 prints a window per match and they are concatenated before the pattern check runs against the combined text. Escape any literal regex metacharacter in anchor or pattern (parens, dots, etc. — grep -E, not a literal-string match); the literal token VERSION is substituted into both anchor and pattern before matching. Blank lines are skipped; every non-blank entry must match its file (and anchor, when given) or the job fails naming that file. Default checks nothing extra. |
| `tag` | string | — | yes | The tag being verified, e.g. the github.ref_name context value on a tag push, or the caller's own workflow_dispatch tag input for a re-run |
| `audit-command` | string | — | no | Dependency-audit command to run after the version gates (e.g. "cargo audit --locked"); skipped when empty |

---

Generated from `.github/workflows/release-verify.yml` by `scripts/render-reusable-docs.py`.
Edit the workflow, not this page.
