# Security Policy

## Reporting a vulnerability

Please report security issues **privately** via GitHub's
["Report a vulnerability"](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (Security tab → Advisories), rather than opening a public issue.

We aim to acknowledge reports within a few days.

## Threat model & expectations

Sonosregie is a small self-hosted utility. Keep in mind:

- **The app has no built-in authentication.** Run it on a trusted LAN, or put it
  behind the bundled oauth2-proxy (`auth/`) for SSO. In "open" mode, anyone who
  can reach the port can read/modify the schedule and control your speakers.
- It controls Sonos devices over the LAN by **unicast IP** (UPnP/SOAP, port 1400).
  It does not expose your speakers to the internet.
- Secrets (oauth2-proxy client secret / cookie secret) are written to an
  `oauth2-proxy.env` file with mode `0600` and must never be committed.
- When protected by oauth2-proxy, access is further restricted to a dedicated
  identity-provider group.

## Supported versions

This project follows a rolling release. Only the latest released version is
supported with fixes.
