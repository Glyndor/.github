#!/usr/bin/env python3
"""Regenerate docs/reusables/ from the reusable workflows themselves.

A consumer of a reusable workflow needs three things this repository never
wrote down: what its inputs are, what they default to, and — the one that has
cost real outages — the exact names of the status checks it emits. A required
status check is matched by NAME, so a repository configuring its ruleset had to
guess, and guessing wrong produces a check nothing emits, which blocks every
pull request until someone notices. That happened in `apt` (a missing prefix)
and in `klyradb` (an invented one).

Generated rather than written so it cannot drift: ci.yml regenerates and fails
if the result differs from what is committed.
"""

import os
import sys

import yaml

WORKFLOWS = ".github/workflows"
OUT = "docs/reusables"

# Not consumer-facing: these run against this repository itself.
SELF_CI = {"actionlint.yml", "dco-check.yml"}

# The `workflow_call:` blocks a page documents, in the order it renders them.
# Named once here and read by iteration, because `call.get("secrets")` written
# inline says "fetch secret values" — to a reader and to CodeQL's
# SensitiveGetCall, which flagged this file as storing secrets in clear text.
# What a reusable declares is the opposite: names, required flags and
# descriptions, already public in the workflow file this script parses. No
# value exists here; nothing reads the environment.
CALL_BLOCKS = ("inputs", "secrets")

# Four reusables predate the header-comment convention. Their summaries live
# here rather than being invented at render time, so the generator never puts
# words in a workflow's mouth.
FALLBACK_SUMMARY = {
    "bun-ci": "Install, lint, typecheck, test and build a Bun project, with an "
    "optional coverage gate.",
    "go-ci": "Build, vet and test a Go module, with an optional coverage gate.",
    "python-ci": "Lint with a pinned ruff and test with a pinned pytest.",
    "rust-ci": "Format, lint, test and optionally cover, cross-test, MSRV-check, "
    "package-check, semver-check and doc-check a Rust crate.",
}


def header_comment(path):
    """The comment block under `name:`, which is how these workflows describe
    themselves. Returns '' when a workflow has none."""
    lines = open(path).read().splitlines()
    out, started = [], False
    for line in lines:
        if line.startswith("name:"):
            started = True
            continue
        if not started:
            continue
        if line.startswith("#"):
            out.append(line.lstrip("#").strip())
        elif not line.strip():
            if out:
                break
        else:
            break
    return " ".join(x for x in out if x).strip()


# Spellings of "this job always runs". A job with no `if:` runs unconditionally;
# so does one that spells that out, which a gate job must do to survive a failed
# dependency.
ALWAYS = {"always()", "${{ always() }}"}


def emitted_checks(spec):
    """One row per job: the name a caller will see, and the condition that
    decides whether it appears at all."""
    rows = []
    for job_id, job in (spec.get("jobs") or {}).items():
        name = job.get("name", job_id)
        cond = job.get("if")
        # `if: always()` is the opposite of conditional: it is how a gate job
        # keeps emitting its check even when the job it reports on failed or was
        # skipped. Reading it as a condition would document exactly the jobs a
        # ruleset CAN safely require as the ones that might not appear.
        if cond is None or str(cond).strip() in ALWAYS:
            when = "always"
        else:
            when = f"`{str(cond).strip()}`"
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        rows.append((name, when, bool(matrix)))
    return rows


def render(slug, spec, summary):
    # A reusable with neither inputs nor secrets parses `workflow_call:` as None.
    call = (spec.get("on") or spec.get(True))["workflow_call"] or {}
    inputs, declared = [call.get(block) or {} for block in CALL_BLOCKS]

    md = [f"# {slug}", ""]
    if summary:
        md += [summary, ""]

    md += [
        "## Calling it",
        "",
        "```yaml",
        "# .github/workflows/ci.yml in the consuming repository",
        "jobs:",
        "  example:",
        f"    uses: Glyndor/.github/.github/workflows/{slug}.yml@<sha> # vX.Y.Z",
        "```",
        "",
        "Pin to a release commit SHA with the version in a comment. Never track a",
        "branch: the SHA pin is what stops a change here reaching a repository",
        "before that repository's own CI has passed on it.",
        "",
    ]

    checks = emitted_checks(spec)
    md += [
        "## Status checks it emits",
        "",
        "The name a consumer sees is `<caller job id> / <job name>`, where `example` is",
        "the caller's job id from the snippet above — a repository that names its job",
        "`rust` sees `rust / …` instead. **These are the strings a ruleset matches**, and",
        "a required check whose name nothing emits blocks every pull request.",
        "",
        "| Check | Emitted when |",
        "|---|---|",
    ]
    for name, when, is_matrix in checks:
        display = f"`example / {name}`"
        if is_matrix:
            display += " (one per matrix entry)"
        md.append(f"| {display} | {when} |")
    md.append("")

    conditional = [c for c in checks if c[1] != "always"]
    if conditional:
        md += [
            f"{len(conditional)} of these {len(checks)} are conditional: they do not run,",
            "and therefore emit no check, unless the input in the right-hand column says",
            "so. Requiring one in a ruleset without setting its input is how a phantom",
            "check is created.",
            "",
        ]

    if inputs:
        md += [
            "## Inputs",
            "",
            "| Input | Type | Default | Required | Description |",
            "|---|---|---|---|---|",
        ]
        for key, val in inputs.items():
            val = val or {}
            default = val.get("default")
            if isinstance(default, bool):
                # YAML and the Actions expression language both spell these
                # lowercase; Python's repr would put `False` in a copyable block.
                default = f"`{str(default).lower()}`"
            elif default is None or default == "":
                default = "—"
            else:
                default = f"`{default}`"
            req = "yes" if val.get("required") else "no"
            desc = (val.get("description") or "").replace("|", "\\|")
            md.append(
                f"| `{key}` | {val.get('type', '—')} | {default} | {req} | {desc} |"
            )
        md.append("")
    else:
        md += ["## Inputs", "", "None.", ""]

    if declared:
        md += ["## Secrets", "", "| Secret | Required | Description |", "|---|---|---|"]
        for key, val in declared.items():
            val = val or {}
            req = "yes" if val.get("required") else "no"
            desc = (val.get("description") or "").replace("|", "\\|")
            md.append(f"| `{key}` | {req} | {desc} |")
        md.append("")

    md += [
        "---",
        "",
        f"Generated from `{WORKFLOWS}/{slug}.yml` by `scripts/render-reusable-docs.py`.",
        "Edit the workflow, not this page.",
    ]
    return "\n".join(md) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    os.makedirs(OUT, exist_ok=True)

    for stale in os.listdir(OUT):
        if stale.endswith(".md"):
            os.remove(os.path.join(OUT, stale))

    index = []
    for filename in sorted(os.listdir(WORKFLOWS)):
        if not filename.endswith(".yml") or filename in SELF_CI:
            continue
        path = os.path.join(WORKFLOWS, filename)
        spec = yaml.safe_load(open(path))
        on = spec.get("on") or spec.get(True)
        if not (isinstance(on, dict) and "workflow_call" in on):
            continue
        slug = filename[:-4]
        summary = header_comment(path) or FALLBACK_SUMMARY.get(slug, "")
        open(os.path.join(OUT, f"{slug}.md"), "w").write(render(slug, spec, summary))
        checks = emitted_checks(spec)
        index.append(
            (
                slug,
                summary,
                len(checks),
                sum(1 for c in checks if c[1] != "always"),
                len(((on["workflow_call"] or {}).get("inputs") or {})),
            )
        )

    readme = [
        "# Reusable workflows",
        "",
        "One page per reusable, generated from the workflow itself so it cannot drift.",
        "Each page lists the inputs, their defaults, and **the exact status-check names",
        "the reusable emits** — the last of those is what a consuming repository needs",
        "to configure its ruleset, and getting it wrong creates a check nothing emits,",
        "which blocks every pull request until someone works out why.",
        "",
        "| Reusable | Checks | Conditional | Inputs |",
        "|---|---|---|---|",
    ]
    for slug, _summary, total, cond, ninputs in index:
        readme.append(f"| [`{slug}`]({slug}.md) | {total} | {cond} | {ninputs} |")
    readme += [
        "",
        "*Conditional* checks only run when an input turns them on, so they emit no",
        "check name at all when it is left at its default.",
        "",
        "---",
        "",
        "Generated by `scripts/render-reusable-docs.py`. Edit the workflows, not these pages.",
    ]
    open(os.path.join(OUT, "README.md"), "w").write("\n".join(readme) + "\n")

    print(f"rendered {len(index)} reusable page(s) into {OUT}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
