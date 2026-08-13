#!/usr/bin/env python3
"""Check that every consumer's reusable pin points to a commit whose surface
matches the latest tag.

The CI standard's pin policy is "bump only when the tag's surface differs from
the current pin" — see ai-context/standards/ci/index.md, "Pin policy for
consumers". A table of consumer-pins is a drift waiting to happen: a future
tag whose surface happens to match a pin still goes in the table as a bump,
which the policy then closes without merging, burning Dependabot's
open-pull-requests-limit on no-op work. This script answers the question
fresh on every run, against the bytes the tag and the SHA point at, so the
policy does not depend on a hand-maintained ledger.

For every reusable pin a consumer has (extracted from every workflow file
under .github/workflows/), the script:

  1. Reads the reusable's surface at the consumer's pinned SHA.
  2. Reads the reusable's surface at the latest released tag.
  3. Compares the two byte-for-byte.

A surface difference means a bump is owed under the policy. The job fails
when any pair differs, and the diff is the only output that needs human
attention; identical surfaces are reported as OK and not acted on.

Conscious non-goals:

  * The script does not bump anything. It only reports. A bump is still a
    reviewer decision, and Dependabot is the path that opens the PR.
  * The script does not read the SHA of the latest tag and ask the consumer
    to match it. That would be "always-latest" with the lockout and the
    alert-fatigue the policy is the alternative to.
"""

import base64
import json
import os
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
    cmd = ["gh", "api", path]
    if jq is not None:
        cmd += ["--jq", jq]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out.stdout


def gh_api_json(path):
    return json.loads(gh_api(path))


def fetch_reusable_surface(reusable, ref):
    """Return the raw bytes of `.github/workflows/<reusable>.yml` at <ref>."""
    data = gh_api_json(
        f"repos/{SELF_REPO}/contents/.github/workflows/{reusable}.yml?ref={ref}"
    )
    if data.get("type") != "file":
        raise RuntimeError(
            f"repos/{SELF_REPO}/contents/.github/workflows/{reusable}.yml?ref={ref} "
            f"is a {data.get('type')!r}, expected a file"
        )
    return base64.b64decode(data["content"])


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
        # shape would fail the gh_api_json call earlier.
        return []
    return [entry["name"] for entry in data if entry.get("type") == "file" and entry["name"].endswith((".yml", ".yaml"))]


def main():
    latest_tag = gh_api(f"repos/{SELF_REPO}/releases/latest", jq=".tag_name").strip()
    if not latest_tag:
        print("::error::No latest release on Glyndor/.github.")
        sys.exit(1)
    print(f"Latest tag: {latest_tag}")
    print()

    stale = []
    ok = 0

    for consumer in CONSUMERS:
        try:
            workflows = consumer_workflow_list(consumer)
        except subprocess.CalledProcessError as exc:
            print(f"SKIP Glyndor/{consumer}: cannot list workflows ({exc}).")
            continue

        for workflow in workflows:
            try:
                text = consumer_workflow_text(consumer, workflow)
            except subprocess.CalledProcessError:
                continue
            if text is None:
                continue

            for match in REUSABLE_REF.finditer(text):
                reusable = match.group("reusable")
                pinned = match.group("sha")
                try:
                    pinned_surface = fetch_reusable_surface(reusable, pinned)
                    latest_surface = fetch_reusable_surface(reusable, latest_tag)
                except subprocess.CalledProcessError as exc:
                    print(f"ERROR Glyndor/{consumer}/{workflow} pin {reusable}@{pinned[:7]}: {exc.stderr.strip()}")
                    stale.append((consumer, workflow, reusable, pinned, "fetch-failed"))
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
                    stale.append((consumer, workflow, reusable, pinned, "surface-differs"))

    print()
    print(f"OK: {ok}  DIFF: {len(stale)}")

    if stale:
        print()
        print("These consumer pins point at a SHA whose reusable surface differs from the")
        print(f"latest tag ({latest_tag}). Under the pin policy, a bump is owed for each.")
        print("Dependabot will open the bump when a release tags a surface change; the")
        print("merge is then a normal reviewer decision. If no Dependabot PR appears,")
        print("the dependabot-freshness guard will surface that as the alert it never")
        print("sent.")
        sys.exit(1)

    print()
    print("All consumer pins are at the latest surface. No bump owed.")


if __name__ == "__main__":
    main()
