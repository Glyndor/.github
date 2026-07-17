# Security Policy

Glyndor builds software that manages servers at a low level (ports, SSH,
firewall, containers, mail).

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report through GitHub's private vulnerability disclosure on the affected
repository: **Security tab → Report a vulnerability**.

If a repository has detached from the organization's code-security baseline
and no longer shows that button, open a draft security advisory on this
repository, **Glyndor/.github**, instead — its Security tab is always
available — and name the affected repository in the report. As a last
resort, reach the owner through their GitHub profile: **@Jaro-c**.

Include:

- Repository and component affected
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

If the report leads to a fix, you'll be credited in the advisory and release
notes (unless you prefer anonymity).

## Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgement | 48 hours |
| Initial assessment | 5 business days |
| Fix + release | Depends on severity |

**Critical** (RCE, auth bypass, crypto break, privilege escalation) — target
fix within 7 days.
**High** (data leak, firewall bypass, replay attack) — target fix within
14 days.
**Medium / Low** — addressed in the next regular release.

## Supported Versions

Only the latest release of each project is supported. Projects with
auto-update receive fixes automatically; for the rest, update to the latest
release before reporting.

## Scope

**In scope:** all public repositories in the Glyndor organization — in
particular authentication and session handling, command/transport integrity,
firewall and tunnel handling, container isolation, update pipelines, injection
of any kind.

**Out of scope:**

- Vulnerabilities requiring physical access to the server
- Issues in third-party dependencies (report upstream — we track them via
  Dependabot and audit tooling)
- Theoretical attacks with no practical exploit path
- Denial of service through resource exhaustion on your own installation
- Social engineering

Some repositories document their security architecture for threat modeling —
check the repository's `docs/` directory.
