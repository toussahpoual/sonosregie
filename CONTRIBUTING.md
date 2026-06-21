# Contributing

Thanks for your interest in improving Sonos Scheduler! Contributions of all
kinds are welcome — bug reports, features, docs, tests.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"        # or: pip install pytest ruff httpx

# run the app locally (no container, open mode)
uvicorn app.main:app --reload --port 8095
```

## Before opening a pull request

```bash
ruff check .
ruff format --check .
pytest
```

CI runs the same checks plus a container build, so it's worth running them locally.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
and [release-please](https://github.com/googleapis/release-please) to automate
versioning and the changelog. Use prefixes such as:

- `feat: ...` — a new feature (minor bump)
- `fix: ...` — a bug fix (patch bump)
- `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...` — no release on their own
- add `!` (e.g. `feat!: ...`) or a `BREAKING CHANGE:` footer for a major bump

## Scope & guidelines

- Keep it small and dependency-light; this is a single-process utility.
- Speakers are reached by **unicast IP** (no SSDP discovery) so it works across
  routed / VPN networks — keep that assumption.
- New API inputs must be validated (see the Pydantic models in `app/main.py`).
- Avoid inline `onclick` with user data in the UI — use event delegation.

## Reporting security issues

Please do not open public issues for security problems. See [SECURITY.md](SECURITY.md).
