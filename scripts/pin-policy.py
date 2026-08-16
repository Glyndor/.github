#!/usr/bin/env python3
"""Check that this repository's reusable pins point at a surface that matches
the latest released tag.

The CI standard's pin policy is "bump only when the tag's surface differs
from the current pin" — see `standards/ci` ("Pin policy for consumers"). A
hand-maintained table of consumer-pins is a drift waiting to happen: a
future tag whose surface happens to match a pin still goes in the table as
a bump, which the policy then closes without merging, burning Dependabot's
`open-pull-requests-limit` on no-op work. This script answers the question
fresh on every run, against the bytes the tag and the SHA point at, so the
policy does not depend on a hand-maintained ledger.

For every reusable pin in the repository this script is invoked from
(extracted from every workflow file under `.github/workflows/`), the script
reads the reusable's surface at the pinned SHA and at the latest released
tag, then compares the two byte-for-byte. A surface difference means a
bump is owed under the policy; an unreadable pin also fails the job (run
31658807184, 2026-08-13, showed why: the central cross-repo run skipped
`template-repository` after a 404 and reported `OK: 15  DIFF: 0`).

The script expects to be invoked from inside the repository it is
checking. Cross-repo reads are limited to the reusable surface at the
pinned SHA and at the latest tag (both in `Glyndor/.github`); the workflow
files of the consumer itself are read locally from the checkout. This is
the consumer-side reuse: every repo runs the check with its own
`GITHUB_TOKEN`, which always covers its own files, so a private consumer
no longer breaks the guard.

Conscious non-goals: the script does not bump anything (Dependabot opens
the PR), and does not pin the consumer to the latest tag's SHA (that
re-introduces the lockout the policy exists to prevent).
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys

UPSTREAM_REPO = "Glyndor/.github"

# A reusable reference inside a `uses:` line. Matches:
#   uses: Glyndor/.github/.github/workflows/<X>.yml@<SHA> # v1.2.3 (PR #121)
# Captures the reusable name, the SHA, and the trailing comment. The
# comment is optional and is consumed only to validate the tag token
# against a real tag on Glyndor/.github — see `extract_tag_token`.
REUSABLE_REF = re.compile(
    r"^\s*uses:\s*"
    r"Glyndor/\.github/\.github/workflows/"
    r"(?P<reusable>[\w.-]+)\.yml@"
    r"(?P<sha>[0-9a-f]{7,40})"
    r"(?:\s*#(?P<comment>.*))?$",
    re.MULTILINE,
)
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def extract_tag_token(comment):
    """Return the first v<major>.<minor>.<patch> token in `comment`, or None.

    Tolerates annotations like `# v1.14.0 (PR #121)`, `# v1.14.2 — see PR #120`,
    or free-form prose with no tag token. Used to validate the trailing
    comment of a `uses:` line against the real tags on Glyndor/.github.
    """
    if not comment:
        return None
    for token in comment.split():
        if TAG_RE.match(token):
            return token
    return None


# Cache reusable surface bytes per (reusable, ref) so the latest tag is fetched
# once per reusable, not once per pin. A transient 5xx or a rate-limit hit on
# one of the first calls would otherwise turn into a red that reads like
# policy drift.
_SURFACE_CACHE = {}


def gh_api(path, jq=None):
    # The cross-repo reads below (the reusable surfaces at pinned and tag
    # refs) are limited to Glyndor/.github and run with the job's
    # GITHUB_TOKEN, which is a scoped bot actor on its own rate limit — the
    # documented exception to the gh api ban that the maintainer's own
    # credentials do not get. Reading this repo's own workflows is a
    # checkout, not an API call.
    cmd = ["gh", "api", path]
    if jq is not None:
        cmd += ["--jq", jq]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out.stdout


def gh_api_json(path):
    return json.loads(gh_api(path))


def call_failure(exc):
    """Return the reason a `git api` call failed, for an operator to act on.

    The first version of this script formatted the CalledProcessError itself,
    which prints the argv and the exit status and drops stderr — so the run
    that skipped `template-repository` said only "returned non-zero exit
    status 1" and the actual API response never reached the log.
    """
    detail = (exc.stderr or "").strip()
    if detail:
        return " ".join(detail.split())
    return f"no stderr, exit status {exc.returncode}"


def fetch_reusable_surface(reusable, ref):
    """Return the raw bytes of `.github/workflows/<reusable>.yml` at <ref>."""
    key = (reusable, ref)
    if key in _SURFACE_CACHE:
        return _SURFACE_CACHE[key]
    data = gh_api_json(
        f"repos/{UPSTREAM_REPO}/contents/.github/workflows/{reusable}.yml?ref={ref}"
    )
    if data.get("type") != "file":
        raise RuntimeError(
            f"repos/{UPSTREAM_REPO}/contents/.github/workflows/{reusable}.yml?ref={ref} "
            f"is a {data.get('type')!r}, expected a file"
        )
    bytes_ = base64.b64decode(data["content"])
    _SURFACE_CACHE[key] = bytes_
    return bytes_


def list_workflows(workdir):
    """List workflow files under <workdir>/.github/workflows/, by basename."""
    wf_dir = os.path.join(workdir, ".github", "workflows")
    if not os.path.isdir(wf_dir):
        raise RuntimeError(f"{wf_dir} is not a directory")
    return sorted(
        name
        for name in os.listdir(wf_dir)
        if name.endswith((".yml", ".yaml"))
        and os.path.isfile(os.path.join(wf_dir, name))
    )


def read_workflow(workdir, name):
    path = os.path.join(workdir, ".github", "workflows", name)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_repo(repo, latest_tag, workdir, self_reusables=None):
    """Compare every reusable pin in <repo>'s checked-out workflows.

    Returns `(ok, fully_read, stale, unreadable)` where `stale` is a list of
    `(workflow, reusable, pinned)` tuples and `unreadable` is a list of
    `(where, reason)` tuples. `fully_read` is False if any read against
    this repository failed — a single failure makes the summary treat the
    repository as not approved, even if other pins compared clean.

    `self_reusables` is an iterable of reusable names to skip — the
    caller's own invocation (`pin-policy-reusable`) and any reusables
    that have been added since the latest tag was cut and live on main
    only. The check cannot verify a reusable against itself before the
    reusable has a tag, and the same gap applies to not-yet-tagged
    reusables on the same repo.
    """
    try:
        workflows = list_workflows(workdir)
    except (OSError, RuntimeError) as exc:
        print(f"::error::{repo}: cannot list .github/workflows at HEAD: {exc}")
        return 0, False, [], [(f"{repo}/.github/workflows", str(exc))]

    ok = 0
    stale = []
    unreadable = []
    pins = 0

    for workflow in workflows:
        try:
            text = read_workflow(workdir, workflow)
        except OSError as exc:
            print(f"::error::{repo}/{workflow}: cannot read the file: {exc}")
            unreadable.append((f"{repo}/{workflow}", str(exc)))
            continue

        for match in REUSABLE_REF.finditer(text):
            reusable = match.group("reusable")
            pinned = match.group("sha")
            if self_reusables is not None and reusable in self_reusables:
                # The caller's own reusable lives in the caller's workflow
                # files (typically `ci.yml`). Checking it against itself
                # would always fail until the reusable's first tag is cut,
                # which is the opposite of the guard's purpose. The list
                # also covers reusables that were added since the latest
                # tag and live on main only — same shape, same gap.
                continue
            pins += 1
            try:
                pinned_surface = fetch_reusable_surface(reusable, pinned)
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                reason = (
                    call_failure(exc)
                    if isinstance(exc, subprocess.CalledProcessError)
                    else str(exc)
                )
                print(
                    f"::error::{repo}/{workflow} pin {reusable}@{pinned[:7]}: "
                    f"cannot read the surface at the pinned SHA: {reason}"
                )
                unreadable.append(
                    (
                        f"{repo}/{workflow} {reusable}@{pinned[:7]}",
                        f"pinned-SHA: {reason}",
                    )
                )
                continue
            try:
                latest_surface = fetch_reusable_surface(reusable, latest_tag)
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                reason = (
                    call_failure(exc)
                    if isinstance(exc, subprocess.CalledProcessError)
                    else str(exc)
                )
                print(
                    f"::error::{repo}/{workflow} pin {reusable}@{pinned[:7]}: "
                    f"{latest_tag} no longer contains a {reusable} file: {reason}"
                )
                unreadable.append(
                    (
                        f"{repo}/{workflow} {reusable}@{pinned[:7]}",
                        f"latest-tag: {reason}",
                    )
                )
                continue

            if pinned_surface == latest_surface:
                print(
                    f"OK    {repo}/{workflow} {reusable}@{pinned[:7]} matches "
                    f"{latest_tag} surface ({len(pinned_surface)} bytes)"
                )
                ok += 1
            else:
                print(
                    f"DIFF  {repo}/{workflow} {reusable}@{pinned[:7]} surface differs "
                    f"from {latest_tag} (pinned {len(pinned_surface)} B vs latest "
                    f"{len(latest_surface)} B)"
                )
                stale.append((workflow, reusable, pinned))
                # No need to validate the comment for a pin that already
                # requires a bump — Dependabot will rewrite the comment
                # when the bump lands.
                continue

            # Surface equality holds. Validate the trailing comment against
            # a real tag on Glyndor/.github: the bytes are the same, but the
            # comment is what Dependabot reads to propose bumps, and a
            # bogus comment ("that tag doesn't exist") produces the same
            # drift class as a byte diff — see homebrew-tap#62.
            comment_tag = extract_tag_token(match.group("comment"))
            if comment_tag is None:
                # No-tag-comment case. The byte check is enough; the
                # standard recommends the comment but does not require it.
                continue
            if comment_tag == latest_tag:
                # Comment names the same tag we just compared against —
                # the cheapest possible proof.
                continue
            try:
                comment_surface = fetch_reusable_surface(reusable, comment_tag)
            except subprocess.CalledProcessError as exc:
                detail = call_failure(exc)
                if "Not Found" in detail:
                    print(
                        f"::error::{repo}/{workflow} pin {reusable}@{pinned[:7]}: "
                        f"comment names tag {comment_tag}, but that tag does not exist on {UPSTREAM_REPO}: {detail}"
                    )
                    unreadable.append(
                        (
                            f"{repo}/{workflow} {reusable}@{pinned[:7]}",
                            f"comment-tag-404: {detail}",
                        )
                    )
                    continue
                # Rate-limit / transient — same path as the other reads.
                print(
                    f"::error::{repo}/{workflow} pin {reusable}@{pinned[:7]}: "
                    f"cannot read the surface at the comment-named tag {comment_tag}: {detail}"
                )
                unreadable.append(
                    (
                        f"{repo}/{workflow} {reusable}@{pinned[:7]}",
                        f"comment-tag: {detail}",
                    )
                )
                continue
            except RuntimeError as exc:
                print(
                    f"::error::{repo}/{workflow} pin {reusable}@{pinned[:7]}: "
                    f"comment named tag {comment_tag} but the surface at that tag is not a file: {exc}"
                )
                unreadable.append(
                    (
                        f"{repo}/{workflow} {reusable}@{pinned[:7]}",
                        f"comment-tag-shape: {exc}",
                    )
                )
                continue

            if comment_surface != pinned_surface:
                print(
                    f"::error::{repo}/{workflow} pin {reusable}@{pinned[:7]}: "
                    f"comment names tag {comment_tag}, but the surface at that tag "
                    f"({len(comment_surface)} B) differs from the pinned SHA "
                    f"({len(pinned_surface)} B). Either the SHA or the tag is wrong."
                )
                stale.append((workflow, reusable, pinned))

    if pins == 0 and not unreadable:
        # No pins found AND every workflow read cleanly. Printed explicitly,
        # because a repository that produces no line at all is
        # indistinguishable in the log from one that was never reached.
        print(f"NONE  {repo}: no reusable pin in {len(workflows)} workflow file(s)")

    return ok, not unreadable, stale, unreadable


def main():
    # The cache lives for the duration of one process invocation only;
    # clearing it here also lets test harnesses re-import the module
    # without seeing stale results.
    _SURFACE_CACHE.clear()

    parser = argparse.ArgumentParser(
        description="Compare a repository's reusable pins against the latest .github tag."
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="Repository name in 'owner/repo' form (default: $GITHUB_REPOSITORY).",
    )
    parser.add_argument(
        "--workdir",
        default=".",
        help="Path to the checked-out repository (default: current directory).",
    )
    parser.add_argument(
        "--self-reusables",
        default="pin-policy-reusable",
        help=(
            "Comma-separated names of reusables to skip. The caller's own "
            "invocation (pin-policy-reusable) is always skipped, since the "
            "check cannot verify a reusable against itself before the "
            "reusable has a tag. Also include any reusables added since the "
            "latest tag was cut — they live on main only, which is the same "
            "gap as a self-reference."
        ),
    )
    args = parser.parse_args()
    if not args.repo or "/" not in args.repo:
        print("::error::--repo (or $GITHUB_REPOSITORY) must be in 'owner/repo' form.")
        sys.exit(1)

    latest_tag = gh_api(
        f"repos/{UPSTREAM_REPO}/releases/latest", jq=".tag_name"
    ).strip()
    if not latest_tag:
        print(f"::error::No latest release on {UPSTREAM_REPO}.")
        sys.exit(1)
    if not TAG_RE.match(latest_tag):
        # Defensive: the tag string is interpolated into every request path
        # below, and the API response is the only place it comes from. A bad
        # shape here would be a script-level bug, not a policy one.
        print(
            f"::error::Latest release tag {latest_tag!r} does not match v<major>.<minor>.<patch>."
        )
        sys.exit(1)
    print(f"Latest tag: {latest_tag}")
    print()

    self_reusables = frozenset(
        s.strip() for s in args.self_reusables.split(",") if s.strip()
    )
    ok, fully_read, stale, unreadable = check_repo(
        args.repo, latest_tag, args.workdir, self_reusables=self_reusables
    )
    compared = ok + len(stale)

    print()
    print(
        f"Pins compared: {compared}  OK: {ok}  DIFF: {len(stale)}  "
        f"UNREADABLE: {len(unreadable)}  "
        f"({'fully read' if fully_read else 'partially read'})"
    )

    if unreadable:
        print()
        print("These reads failed, so their pins were never compared. A pin this")
        print("job cannot read is not a pin it approved:")
        for where, reason in unreadable:
            print(f"  {where}: {reason}")

    if stale:
        print()
        print(
            f"These pins point at a SHA whose reusable surface differs from {latest_tag}."
        )
        print("Under the pin policy, a bump is owed for each:")
        for workflow, reusable, pinned in stale:
            print(f"  {args.repo}/{workflow} {reusable}@{pinned[:7]}")
        print("Dependabot will open the bump when a release tags a surface change; the")
        print("merge is then a normal reviewer decision. If no Dependabot PR appears,")
        print("the dependabot-freshness guard will surface that as the alert it never")
        print("sent.")

    if unreadable or stale:
        sys.exit(1)

    print()
    print(f"All {ok} pin(s) are at the {latest_tag} surface. No bump owed.")


if __name__ == "__main__":
    main()
