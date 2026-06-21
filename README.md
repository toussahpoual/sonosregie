# Sonosregie

Schedule **web-radio (HTTP stream) playback** on **Sonos / Symfonisk** speakers
spread across multiple sites, addressed by **IP**.

[![CI](https://github.com/toussahpoual/sonosregie/actions/workflows/ci.yml/badge.svg)](https://github.com/toussahpoual/sonosregie/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/toussahpoual/sonosregie)](https://github.com/toussahpoual/sonosregie/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- 🎛️ **Multi-site, by IP** — speakers are reached by unicast IP (no SSDP discovery),
  so it works across routed / VPN networks.
- ⏰ **Time slots** — per speaker, start/end `HH:MM`, days of the week, optional volume.
  Multiple slots, overnight ranges supported.
- 🔁 **Self-healing retry** — if a speaker was off at the start of a slot, it's picked
  up automatically once it's back (within the window) — no retry bookkeeping.
- 📻 **Web-radio** — pushes an `x-rincon-mp3radio://` URI; prefer `http` streams.
- 🖥️ **Web UI** — a small "broadcast console" interface, responsive, with live status.
- 🔐 **Optional SSO** — drop an [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/)
  in front for OIDC login (Authentik bootstrap included), or run open.

## How it works

A **reconciler** runs every 30 s. For each speaker it computes the *desired stream*
(the active slot covering "now") and applies it:

- speaker unreachable at slot start → retried on the next tick until it answers;
- multiple time slots per speaker, with day-of-week;
- stop at end of slot (only if the speaker is playing one of *our* streams);
- clean recovery after an app restart — no state to track.

**Data model:** `Speaker` (name, IP, site, enabled) · `Stream` (name, URL, title) ·
`Slot` (speaker + stream + days `0=Mon..6=Sun` + start/end `HH:MM` + optional volume).
If `end <= start`, the slot crosses midnight.

## Quick start (Podman Quadlet, rootless — no clone)

Everything needed to deploy ships **inside the image** — no need to clone the repo.

```bash
IMG=ghcr.io/toussahpoual/sonosregie:latest
podman pull "$IMG" && podman tag "$IMG" localhost/sonosregie:latest

mkdir -p ~/.local/share/sonosregie ~/.config/sonosregie ~/.config/containers/systemd
# the Quadlet unit is baked into the image:
podman run --rm "$IMG" cat /srv/deploy/sonosregie.container \
  > ~/.config/containers/systemd/sonosregie.container
systemctl --user daemon-reload
systemctl --user start sonosregie.service
loginctl enable-linger "$USER"        # start at boot
```

Open `http://YOUR_HOST_IP:8095/` — API docs at `/docs`. Host networking is required to
reach Sonos devices on the LAN; the SQLite DB lives in `~/.local/share/sonosregie`. Set
your timezone by editing `Environment=TZ=` in the installed unit.

### Run with Docker instead

```bash
docker pull ghcr.io/toussahpoual/sonosregie:latest
docker run -d --name sonosregie --network host \
  -e TZ=Europe/Paris -v sonos-data:/data --restart unless-stopped \
  ghcr.io/toussahpoual/sonosregie:latest
```

### Develop locally (no container)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8095
```

## Optional: protect with SSO (oauth2-proxy + OIDC)

The app has **no built-in auth**. To gate it, run the bundled oauth2-proxy in front; the
app moves to an internal port. Switching modes needs **no script** — the image ships two
app-unit variants (open vs internal) and the mode is just *which one you install*. A
bootstrap for [Authentik](https://goauthentik.io/) is included (other OIDC providers:
write the env yourself, see `auth/.env.example`). Everything below runs **from the image**.

```bash
IMG=ghcr.io/toussahpoual/sonosregie:latest

# 1. configure the IdP + write the proxy secrets (from the image)
export AUTHENTIK_TOKEN=...                       # admin API token
podman run --rm --network host \
  -e AUTHENTIK_TOKEN -e AUTHENTIK_URL=https://auth.example.com -e PUBLIC_HOST=YOUR_HOST_IP \
  -v ~/.config/sonosregie:/out:Z \
  "$IMG" python /srv/deploy/auth/authentik_bootstrap.py
# -> provider + application + group "sonos-users";
#    writes ~/.config/sonosregie/oauth2-proxy.env (0600, secrets)

# 2. add your user to the "sonos-users" group in the IdP

# 3. switch to the SSO units (app -> internal :8096, proxy -> :8095) and restart
podman run --rm "$IMG" cat /srv/deploy/auth/sonosregie.container \
  > ~/.config/containers/systemd/sonosregie.container
podman run --rm "$IMG" cat /srv/deploy/auth/sonosregie-auth.container \
  > ~/.config/containers/systemd/sonosregie-auth.container
systemctl --user daemon-reload
systemctl --user restart sonosregie.service
systemctl --user start sonosregie-auth.service
```

Back to open mode (no script — reinstall the open unit, drop the proxy):

```bash
podman run --rm "$IMG" cat /srv/deploy/sonosregie.container \
  > ~/.config/containers/systemd/sonosregie.container
rm -f ~/.config/containers/systemd/sonosregie-auth.container
systemctl --user stop sonosregie-auth.service
systemctl --user daemon-reload && systemctl --user restart sonosregie.service
```

Notes: access is over `http` on the LAN (cookie marked non-secure) — for HTTPS, put
it behind a TLS reverse proxy / tunnel and update `OAUTH2_PROXY_REDIRECT_URL`. The
reconciler keeps running regardless of auth (auth only gates the HTTP UI/API).

## API

| Method | Path | Purpose |
|---|---|---|
| GET/POST/PUT/DELETE | `/api/speakers` | speakers |
| GET/POST/PUT/DELETE | `/api/streams` | web radios |
| GET/POST/PUT/DELETE | `/api/slots` | time slots |
| GET | `/api/status` | live per-speaker status |
| POST | `/api/speakers/{id}/play/{stream_id}` | play now (test) |
| POST | `/api/speakers/{id}/stop` | stop now |
| POST | `/api/reconcile` | force a reconcile tick |
| GET | `/healthz` | health check |

## Sonos notes

- Prefer **`http`** streams; native `https` is unreliable on Sonos. The app pushes
  `x-rincon-mp3radio://…` and compares canonical forms (the device rewrites the URI).
- No SSDP discovery: each speaker is addressed by static IP, so it works through a
  routed network / VPN. The speaker's own timezone is irrelevant — the app decides
  timing on its own clock (set `TZ` on the container to your zone).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
Security issues: see [SECURITY.md](SECURITY.md).

## Trademarks

*Sonos* and *Symfonisk* are trademarks of Sonos, Inc. and Inter IKEA Systems B.V.
respectively. This project is an independent, community tool and is **not affiliated
with, endorsed by, or sponsored by** Sonos or IKEA.

## License

[MIT](LICENSE) © GINC
