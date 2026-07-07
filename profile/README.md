# Glyndor

Open-source, self-hosted infrastructure software: a hosting panel, a mail
server, a compose-to-Podman translator, a process manager, an auth library, a
local database manager, and two browser extensions. Rust, Go and TypeScript.
Every repository is licensed Apache-2.0.

Website: glyndor.net

## Repositories

| Repository | Language | Description |
|---|---|---|
| [helmly](https://github.com/Glyndor/helmly) | Rust / TypeScript | Self-hosted VPS and container hosting panel |
| [helmly-agent](https://github.com/Glyndor/helmly-agent) | Rust | On-server executor for helmly |
| [podup](https://github.com/Glyndor/podup) | Rust | docker-compose translator and runner for rootless Podman |
| [epistle](https://github.com/Glyndor/epistle) | Rust | Self-hosted, headless mail server (SMTP/IMAP/JMAP) |
| [epistle-panel](https://github.com/Glyndor/epistle-panel) | TypeScript | Web admin panel for epistle |
| [authcore](https://github.com/Glyndor/authcore) | Go | Auth primitives library — passwords, tokens, OAuth2/OIDC |
| [unitpm](https://github.com/Glyndor/unitpm) | Go | systemd-native process manager |
| [klyradb](https://github.com/Glyndor/klyradb) | Rust | Local database instance manager (desktop app) |
| [specio](https://github.com/Glyndor/specio) | TypeScript | Browser extension: on-device website tech-stack detection |
| [viden](https://github.com/Glyndor/viden) | TypeScript | Browser extension: video stream downloader |

## Contributing

Issues are open to everyone. Pull requests are invitation-only — this code
touches kernel-level surfaces (SSH, firewall, ports). Report vulnerabilities
privately via [`SECURITY.md`](https://github.com/Glyndor/.github/blob/main/SECURITY.md);
contribution flow and conventions are in
[`CONTRIBUTING.md`](https://github.com/Glyndor/.github/blob/main/CONTRIBUTING.md).
