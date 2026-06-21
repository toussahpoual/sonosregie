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

## Quick start (Podman Quadlet, rootless)

```bash
git clone https://github.com/toussahpoual/sonosregie.git
cd sonosregie
podman build -t localhost/sonosregie:latest .

mkdir -p ~/.local/share/sonosregie
cp sonosregie.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start sonosregie.service
```

Open `http://YOUR_HOST_IP:8095/` — API docs at `/docs`. The container uses host
networking (required to reach Sonos devices on the LAN) and stores its SQLite DB
in `~/.local/share/sonosregie`.

### Run with Docker instead

```bash
docker build -t sonosregie .
docker run -d --name sonosregie --network host \
  -v sonos-data:/data sonosregie
```

### Develop locally (no container)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8095
```

## Optional: protect with SSO (oauth2-proxy + OIDC)

The app has **no built-in auth**. To gate it behind your identity provider, run the
bundled oauth2-proxy in front; the app moves to an internal port. A bootstrap script
for [Authentik](https://goauthentik.io/) is provided (other OIDC providers work too —
just create the env file yourself, see `auth/.env.example`).

```bash
mkdir -p ~/.config/sonosregie
export AUTHENTIK_TOKEN=...                       # admin API token
podman run --rm --network host \
  -e AUTHENTIK_TOKEN \
  -e AUTHENTIK_URL=https://auth.example.com \
  -e PUBLIC_HOST=YOUR_HOST_IP \
  -v "$PWD/auth:/auth:z" \
  -v ~/.config/sonosregie:/out:Z \
  localhost/sonosregie python /auth/authentik_bootstrap.py
# -> creates provider + application + group "sonos-users",
#    writes ~/.config/sonosregie/oauth2-proxy.env (0600, secrets)

# Add your user to the "sonos-users" group in your IdP, then:
./auth/set-mode.sh auth      # app internal :8096, oauth2-proxy on :8095
./auth/set-mode.sh noauth     # back to open mode on :8095
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
