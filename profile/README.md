# Glyndor

Open-source, self-hosted infrastructure software: a VPS and container panel, a
mail server, a Compose runner for Podman, an auth library and browser
extensions, written in Rust, Go and TypeScript. [glyndor.net](https://glyndor.net)

## Install

Each channel has its own repository with the exact command, what it checks
before installing, and how to verify what you installed.

| Platform | Channel | What it serves |
|---|---|---|
| Debian and Ubuntu | [apt](https://github.com/Glyndor/apt) | podup, podman and epistle |
| macOS and Linux with Homebrew | [Homebrew tap](https://github.com/Glyndor/homebrew-tap) | podup |
| Windows | [Scoop bucket](https://github.com/Glyndor/scoop-bucket) | podup |
| RPM-based distributions | [rpm](https://github.com/Glyndor/rpm) | in preparation, nothing published yet |
| Arch Linux | [pacman](https://github.com/Glyndor/pacman) | in preparation, nothing published yet |

On macOS and Windows, podup needs a running `podman machine`; the
[podup README](https://github.com/Glyndor/podup#install) has the details. The
other products are not distributed through these channels: see their
repositories.

## Products

| Repository | Language | What it is | License |
|---|---|---|---|
| [podup](https://github.com/Glyndor/podup) | Rust | Run Compose projects on rootless Podman | MIT |
| [podman](https://github.com/Glyndor/podman) | Shell | Signed Podman packages for Debian 13 and Ubuntu 24.04 and 26.04, built from the latest stable upstream releases | MIT |
| [epistle](https://github.com/Glyndor/epistle) | Rust | A self-hosted mail server for your own domains | MIT |
| [epistle-panel](https://github.com/Glyndor/epistle-panel) | TypeScript | Admin panel for the Epistle mail server | MIT |
| [helmly](https://github.com/Glyndor/helmly) | Rust / TypeScript | Self-hosted VPS and container manager | Apache-2.0 |
| [helmly-agent](https://github.com/Glyndor/helmly-agent) | Rust | Hardened server-side daemon for the Helmly panel | MIT |
| [authcore](https://github.com/Glyndor/authcore) | Go | Authentication library for Go | MIT |
| [specio](https://github.com/Glyndor/specio) | TypeScript | Chrome/Chromium extension that detects the technologies behind a web page | MIT |
| [viden](https://github.com/Glyndor/viden) | TypeScript | Browser extension that detects and downloads the video playing on a page | MIT |

## Trust

Release binaries are signed with the organization's Ed25519 release key. The
Homebrew tap and the Scoop bucket take every checksum from a signed manifest
checked against that key, and the apt archive is signed with its own Ed25519
key. The archive key's fingerprint is published in the apt repository, a second
place that does not depend on the website:
[verify the signing key](https://github.com/Glyndor/apt#verify-the-signing-key).

## Contributing and security

Issues are open to everyone. Pull requests are invitation-only, because this
code touches kernel-level surfaces (SSH, firewall, ports). Report
vulnerabilities privately via [`SECURITY.md`](https://github.com/Glyndor/.github/blob/main/SECURITY.md);
contribution flow and conventions are in
[`CONTRIBUTING.md`](https://github.com/Glyndor/.github/blob/main/CONTRIBUTING.md).
