# Changelog

All notable changes to this project are documented here. This file is managed
automatically by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/).

## [0.2.1](https://github.com/toussahpoual/sonosregie/compare/sonosregie-v0.2.0...sonosregie-v0.2.1) (2026-06-21)


### Bug Fixes

* README Docker section uses the published image (pull, not build) ([1bfcc05](https://github.com/toussahpoual/sonosregie/commit/1bfcc05d49a98fbba4db851c1b1eddb1319591b9))

## [0.2.0](https://github.com/toussahpoual/sonosregie/compare/sonosregie-v0.1.0...sonosregie-v0.2.0) (2026-06-21)


### Features

* deploy from the image alone; drop set-mode.sh ([c529a5e](https://github.com/toussahpoual/sonosregie/commit/c529a5e50761029b9d20867862778cfe99fdc032))

## 0.1.0 (2026-06-21)


### Features

* initial public release ([7f53864](https://github.com/toussahpoual/sonosregie/commit/7f53864b36aa118b60a0864420906d8c7b597eb1))

## 0.1.0 (unreleased)

Initial public release.

- Schedule web-radio (HTTP stream) playback on Sonos / Symfonisk speakers by IP,
  across multiple sites.
- Reconciler loop (desired-state model): automatic retry when a speaker was off at
  the start of a slot, multi time-slot support, stop at end of slot.
- Web UI ("broadcast console" theme), responsive.
- Optional SSO protection via oauth2-proxy + an OIDC provider (Authentik bootstrap
  included), with a toggle to run open (no auth).
