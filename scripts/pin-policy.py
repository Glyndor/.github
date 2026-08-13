#!/usr/bin/env python3
"""Check that every consumer's reusable pin points at a surface that matches
the latest released tag.

The CI standard's pin policy is "bump only when the tag's surface differs
from the current pin" — see `standards/ci` ("Pin policy for consumers"). A
hand-maintained table of consumer-pins is a drift waiting to happen: a
future tag whose surface happens to match a pin still goes in the table as
a bump, which the policy then closes without merging, burning Dependabot's
`open-pull-requests-limit` on no-op work. This script answers the question
fresh on every run, against the bytes the tag and the SHA point at, so the
policy does not depend on a hand-maintained ledger.

For every reusable pin a consumer has (extracted from every workflow file
under .github/workflows/), the script reads the reusable's surface at the
consumer's pinned SHA and at the latest released tag, then compares the
two byte-for-byte. A surface difference means a bump is owed under the
policy; a consumer the script cannot read also fails the job (run
31658807184, 2026-08-13, showed why the second condition is needed: it
skipped `template-repository` after a 404 and reported `OK: 15  DIFF: 0`).

Conscious non-goals: the script does not bump anything (Dependabot opens
the PR), and does not pin the consumer to the latest tag's SHA (that
re-introduces the lockout the policy exists to prevent).
"""

import base64
import json
import re
import subprocess
import sys

SELF_REPO = "Glyndor/.github"
CONSUMERS = [
    "apt",
    "homebrew-tap",
    "scoop-bucket",
    "klyradb",
    "template-repository",
]

# A reusable reference inside a `uses:` line. Matches:
#   uses: Glyndor/.github/.github/workflows/<X>.yml@<SHA> # v1.2.3
# Captures the reusable name and the SHA, with optional trailing comment
# kept out of the SHA group.
REUSABLE_REF = re.compile(
    r"^\s*uses:\s*"
    r"Glyndor/\.github/\.github/workflows/"
    r"(?P<reusable>[\w.-]+)\.yml@"
    r"(?P<sha>[0-9a-f]{7,40})"
    r"(?:\s*#.*)?$",
    re.MULTILINE,
)


def gh_api(path, jq=None):
    # `gh api` is banned for the maintainer's own credentials — the org account
    # has been suspended over raw API traffic before. A workflow is a different
    # actor: GITHUB_TOKEN is a scoped job token on its own rate limit, which is
    # the documented exception.
    cmd = ["gh", "api", path]
    if jq is not None:
        cmd += ["--jq", jq]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out.stdout


def gh_api_json(path):
    return json.loads(gh_api(path))


def call_failure(exc):
    """Return the reason a `gh api` call failed, for an operator to act on.

    The first version of this script formatted the CalledProcessError itself,
    which prints the argv and the exit status and drops stderr — so the run
    that skipped `template-repository` said only "returned non-zero exit
    status 1" and the actual API response never reached the log.
    """
    detail = (exc.stderr or "").strip()
    if detail:
        return " ".join(detail.split())
    return f"no stderr, exit status {exc.returncode}"


# Cache reusable surface bytes per (reusable, ref) so the latest tag is fetched
# once per reusable, not once per pin. A transient 5xx or a rate-limit hit on
# one of the first calls would otherwise turn into a red that reads like
# policy drift.
_SURFACE_CACHE = {}


def fetch_reusable_surface(reusable, ref):
    """Return the raw bytes of `.github/workflows/<reusable>.yml` at <ref>."""
    key = (reusable, ref)
    if key in _SURFACE_CACHE:
        return _SURFACE_CACHE[key]
    data = gh_api_json(
        f"repos/{SELF_REPO}/contents/.github/workflows/{reusable}.yml?ref={ref}"
    )
    if data.get("type") != "file":
        raise RuntimeError(
            f"repos/{SELF_REPO}/contents/.github/workflows/{reusable}.yml?ref={ref} "
            f"is a {data.get('type')!r}, expected a file"
        )
    bytes_ = base64.b64decode(data["content"])
    _SURFACE_CACHE[key] = bytes_
    return bytes_


def consumer_workflow_text(repo, workflow):
    """Return the raw text of `Glyndor/<repo>/.github/workflows/<workflow>` at main."""
    data = gh_api_json(
        f"repos/Glyndor/{repo}/contents/.github/workflows/{workflow}?ref=main"
    )
    if data.get("type") != "file":
        return None
    return base64.b64decode(data["content"]).decode("utf-8")


def consumer_workflow_list(repo):
    """List the workflow files in `Glyndor/<repo>/.github/workflows/` at main."""
    data = gh_api_json(
        f"repos/Glyndor/{repo}/contents/.github/workflows?ref=main"
    )
    if not isinstance(data, list):
        # The contents endpoint returns a single file object if the path is a
        # file; for a directory it returns an array. A 404 or other error
        # shape fails the gh_api_json call earlier.
        raise RuntimeError(
            f"repos/Glyndor/{repo}/contents/.github/workflows?ref=main returned "
            f"a {type(data).__name__}, expected a directory listing"
        )
    return [
        entry["name"]
        for entry in data
        if entry.get("type") == "file" and entry["name"].endswith((".yml", ".yaml"))
    ]


def check_consumer(consumer, latest_tag, stale, unreadable):
    """Compare every reusable pin in one consumer against the latest tag.

    Returns a tuple `(ok, fully_read)`:
      - `ok` is the number of pins whose surface matched the latest tag
      - `fully_read` is False if any read against this consumer failed (a
        list, a file, or a surface); a single failed read is enough — the
        summary treats such a consumer as not approved, even if other pins
        in the same consumer compared clean.
    """
    try:
        workflows = consumer_workflow_list(consumer)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        reason = call_failure(exc) if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"::error::Glyndor/{consumer}: cannot list .github/workflows at main: {reason}")
        unreadable.append((consumer, reason))
        return 0, False

    ok = 0
    consumer_unread = 0
    pins = 0

    for workflow in workflows:
        try:
            text = consumer_workflow_text(consumer, workflow)
        except subprocess.CalledProcessError as exc:
            reason = call_failure(exc)
            print(f"::error::Glyndor/{consumer}/{workflow}: cannot read the file: {reason}")
            unreadable.append((f"{consumer}/{workflow}", reason))
            consumer_unread += 1
            continue
        if text is None:
            continue

        for match in REUSABLE_REF.finditer(text):
            reusable = match.group("reusable")
            pinned = match.group("sha")
            pins += 1
            try:
                pinned_surface = fetch_reusable_surface(reusable, pinned)
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                reason = call_failure(exc) if isinstance(exc, subprocess.CalledProcessError) else str(exc)
                print(
                    f"::error::Glyndor/{consumer}/{workflow} pin "
                    f"{reusable}@{pinned[:7]}: cannot read the surface at the pinned SHA: {reason}"
                )
                unreadable.append(
                    (f"{consumer}/{workflow} {reusable}@{pinned[:7]}", f"pinned-SHA: {reason}")
                )
                consumer_unread += 1
                continue
            try:
                latest_surface = fetch_reusable_surface(reusable, latest_tag)
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                reason = call_failure(exc) if isinstance(exc, subprocess.CalledProcessError) else str(exc)
                print(
                    f"::error::Glyndor/{consumer}/{workflow} pin "
                    f"{reusable}@{pinned[:7]}: {latest_tag} no longer contains a {reusable} file: {reason}"
                )
                unreadable.append(
                    (f"{consumer}/{workflow} {reusable}@{pinned[:7]}", f"latest-tag: {reason}")
                )
                consumer_unread += 1
                continue

            if pinned_surface == latest_surface:
                print(
                    f"OK    Glyndor/{consumer}/{workflow} "
                    f"{reusable}@{pinned[:7]} matches {latest_tag} surface "
                    f"({len(pinned_surface)} bytes)"
                )
                ok += 1
            else:
                print(
                    f"DIFF  Glyndor/{consumer}/{workflow} "
                    f"{reusable}@{pinned[:7]} surface differs from {latest_tag} "
                    f"(pinned {len(pinned_surface)} B vs latest {len(latest_surface)} B)"
                )
                stale.append((consumer, workflow, reusable, pinned))

    if pins == 0 and consumer_unread == 0:
        # No pins found AND every workflow read cleanly. Printed explicitly,
        # because a consumer that produces no line at all is indistinguishable
        # in the log from one that was never reached. The consumer that
        # contributed no pins may not stay that way; the consumer whose reads
        # failed is reported in the UNREADABLE block below instead.
        print(
            f"NONE  Glyndor/{consumer}: no reusable pin in "
            f"{len(workflows)} workflow file(s)"
        )

    return ok, consumer_unread == 0


TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def main():
    latest_tag = gh_api(f"repos/{SELF_REPO}/releases/latest", jq=".tag_name").strip()
    if not latest_tag:
        print("::error::No latest release on Glyndor/.github.")
        sys.exit(1)
    if not TAG_RE.match(latest_tag):
        # Defensive: the tag string is interpolated into every request path
        # below, and the API response is the only place it comes from. A bad
        # shape here would be a script-level bug, not a policy one.
        print(f"::error::Latest release tag {latest_tag!r} does not match v<major>.<minor>.<patch>.")
        sys.exit(1)
    print(f"Latest tag: {latest_tag}")
    print()

    stale = []
    unreadable = []
    ok = 0
    fully_read = 0

    for consumer in CONSUMERS:
        consumer_ok, clean = check_consumer(consumer, latest_tag, stale, unreadable)
        ok += consumer_ok
        if clean:
            fully_read += 1

    print()
    print(
        f"Consumers read: {fully_read} of {len(CONSUMERS)}  "
        f"pins compared: {ok + len(stale)}  OK: {ok}  DIFF: {len(stale)}  "
        f"UNREADABLE: {len(unreadable)}"
    )

    if unreadable:
        print()
        print("These reads failed, so their pins were never compared. A consumer this")
        print("job cannot read is not a consumer it approved:")
        for name, reason in unreadable:
            print(f"  Glyndor/{name}: {reason}")

    if stale:
        print()
        print("These consumer pins point at a SHA whose reusable surface differs from the")
        print(f"latest tag ({latest_tag}). Under the pin policy, a bump is owed for each:")
        for consumer, workflow, reusable, pinned in stale:
            print(f"  Glyndor/{consumer}/{workflow} {reusable}@{pinned[:7]}")
        print("Dependabot will open the bump when a release tags a surface change; the")
        print("merge is then a normal reviewer decision. If no Dependabot PR appears,")
        print("the dependabot-freshness guard will surface that as the alert it never")
        print("sent.")

    if unreadable or stale:
        sys.exit(1)

    print()
    print(
        f"All {ok} pin(s) across {fully_read} of {len(CONSUMERS)} consumer(s) are at the "
        f"latest surface. No bump owed."
    )


if __name__ == "__main__":
    main()
