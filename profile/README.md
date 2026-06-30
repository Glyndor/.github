<div align="center">

<img src="https://raw.githubusercontent.com/Glyndor/.github/main/profile/assets/logo.webp" alt="Glyndor" width="130" />

# Glyndor

### Secure, self-hosted infrastructure you actually own.

Open-source, security-first tools for self-hosters and teams — hardened,
lightweight, and built to OWASP ASVS Level 3.

[![License](https://img.shields.io/badge/license-Apache--2.0-3fb950?style=flat-square)](https://github.com/Glyndor/.github/blob/main/LICENSE)
&nbsp;![ASVS](https://img.shields.io/badge/OWASP_ASVS-Level_3-3fb950?style=flat-square)
&nbsp;![Secure by default](https://img.shields.io/badge/secure-by_default-3fb950?style=flat-square)
&nbsp;![Stack](https://img.shields.io/badge/Rust_·_Go_·_TypeScript-30363d?style=flat-square)

[**glyndor.net**](https://glyndor.net)&nbsp; · &nbsp;[**Support**](https://glyndor.net/support)&nbsp; · &nbsp;[**Security**](https://github.com/Glyndor/.github/security/policy)

</div>

---

## 🖥️ The platform

<table>
<tr>
<td valign="top" width="50%">

### 🖥️ [helmly](https://github.com/Glyndor/helmly)
Self-hosted hosting panel — firewall, SSH, containers and WireGuard tunnels. One server or a hardened fleet. A cPanel / Plesk / Coolify alternative.

![Rust](https://img.shields.io/badge/Rust-CE412B?style=flat-square&logo=rust&logoColor=white) ![Next.js](https://img.shields.io/badge/Next.js-30363d?style=flat-square&logo=nextdotjs&logoColor=white) ![status](https://img.shields.io/badge/status-in_development-d29922?style=flat-square)

</td>
<td valign="top" width="50%">

### 🛡️ [helmly-agent](https://github.com/Glyndor/helmly-agent)
Hardened per-server agent — runs Ed25519-signed commands and reports telemetry over WireGuard + mTLS.

![Rust](https://img.shields.io/badge/Rust-CE412B?style=flat-square&logo=rust&logoColor=white) ![release](https://img.shields.io/github/v/release/Glyndor/helmly-agent?style=flat-square&color=3fb950&label=)

</td>
</tr>
<tr>
<td valign="top" width="50%">

### 📦 [podup](https://github.com/Glyndor/podup)
`docker-compose` translated to rootless Podman — Rust library and a drop-in CLI.

![Rust](https://img.shields.io/badge/Rust-CE412B?style=flat-square&logo=rust&logoColor=white) ![release](https://img.shields.io/github/v/release/Glyndor/podup?style=flat-square&color=3fb950&label=)

</td>
<td valign="top" width="50%"></td>
</tr>
</table>

## ✉️ Mail

<table>
<tr>
<td valign="top" width="50%">

### ✉️ [epistle](https://github.com/Glyndor/epistle)
Self-hosted mail server — SMTP, IMAP and modern email security behind an API and CLI. Standalone or panel-integrated.

![Rust](https://img.shields.io/badge/Rust-CE412B?style=flat-square&logo=rust&logoColor=white) ![release](https://img.shields.io/github/v/release/Glyndor/epistle?style=flat-square&color=3fb950&label=)

</td>
<td valign="top" width="50%">

### 📬 [epistle-panel](https://github.com/Glyndor/epistle-panel)
Next.js admin UI for the mail server — domains, mailboxes, security and queues on top of the mail API.

![Next.js](https://img.shields.io/badge/Next.js-30363d?style=flat-square&logo=nextdotjs&logoColor=white) ![status](https://img.shields.io/badge/status-in_development-d29922?style=flat-square)

</td>
</tr>
</table>

## 🧰 Developer tools

<table>
<tr>
<td valign="top" width="50%">

### 🔐 [authcore](https://github.com/Glyndor/authcore)
Drop-in auth for Go — Argon2id passwords, EdDSA JWTs with refresh rotation, opaque API keys, OIDC + OAuth2. Zero boilerplate.

![Go](https://img.shields.io/badge/Go-00ADD8?style=flat-square&logo=go&logoColor=white) ![release](https://img.shields.io/github/v/release/Glyndor/authcore?style=flat-square&color=3fb950&label=)

</td>
<td valign="top" width="50%">

### ⚡ [unitpm](https://github.com/Glyndor/unitpm)
Fast, secure process manager for Linux — the zero-overhead, systemd-native alternative to PM2.

![Go](https://img.shields.io/badge/Go-00ADD8?style=flat-square&logo=go&logoColor=white) ![status](https://img.shields.io/badge/status-in_development-d29922?style=flat-square)

</td>
</tr>
<tr>
<td valign="top" width="50%">

### 🗄️ [klyradb](https://github.com/Glyndor/klyradb)
Desktop app to manage isolated PostgreSQL, MySQL, MariaDB and Redis instances on Linux — DBngin for Ubuntu.

![Go](https://img.shields.io/badge/Go-00ADD8?style=flat-square&logo=go&logoColor=white) ![release](https://img.shields.io/github/v/release/Glyndor/klyradb?style=flat-square&color=3fb950&label=)

</td>
<td valign="top" width="50%"></td>
</tr>
</table>

## 🧩 Browser extensions

<table>
<tr>
<td valign="top" width="50%">

### 🧩 [specio](https://github.com/Glyndor/specio)
Detects the tech a site is built with — CMS, frameworks, analytics, CDNs, servers, fonts. An open Wappalyzer alternative.

![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) ![release](https://img.shields.io/github/v/release/Glyndor/specio?style=flat-square&color=3fb950&label=)

</td>
<td valign="top" width="50%">

### 🎬 [viden](https://github.com/Glyndor/viden)
Detects and downloads the video playing on a page — including hidden or obscured streams (MP4, HLS, DASH).

![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) ![status](https://img.shields.io/badge/status-coming_soon-1f6feb?style=flat-square)

</td>
</tr>
</table>

## 🔭 How it fits together

```mermaid
flowchart LR
  helmly["helmly panel"] -->|signed commands| agent["helmly-agent"]
  agent -->|rootless containers| podup["podup"]
  helmly -. manages .-> epistle["epistle"]
  epistle --> ep["epistle-panel"]
```

## 🛡️ Principles

**Secure by default** — the most restrictive config ships active.&nbsp; **You own it** — native binaries, no SaaS lock-in.&nbsp; **Open source** — every project public and Apache-2.0.&nbsp; **Minimal & native** — small binaries, audited supply chain.

## 🤝 Contributing

**Issues** are open to everyone. **Pull requests** are invitation-only — this code touches kernel-level surfaces (SSH, firewall, ports). Report vulnerabilities privately via [`SECURITY.md`](https://github.com/Glyndor/.github/blob/main/SECURITY.md); flow and conventions in [`CONTRIBUTING.md`](https://github.com/Glyndor/.github/blob/main/CONTRIBUTING.md).

---

<div align="center">
<sub>Built in the open · <a href="https://glyndor.net">glyndor.net</a></sub>
</div>
