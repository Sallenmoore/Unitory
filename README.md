# Unitory

Server inventory management for the Binghamton University Linux Team.

Stack: FastAPI · HTMX · Foundation 6 · MongoDB · Redis/RQ · built on the
[`autonomous-app`](https://pypi.org/project/autonomous-app/) framework
(installed from PyPI) for models, tasks, and user auth.

## Running it

This service is a member of the unified [`dockerStacks`](../) tree and is
operated through the shared [`./containers`](../containers) driver. **Do not**
`docker compose up` against this directory — the file expects `mongo`, `redis`,
`sops-decrypt`, the `docknet` network, and the `secrets` volume to come from
sibling compose files under `dockerStacks/common/`.

```bash
# from /home/itsadmin/dockerStacks/
./containers up unitory worker        # bring up web + RQ worker (deps come along)
./containers logs worker              # tail the RQ worker
./containers rebuild unitory          # build --no-cache after Dockerfile / requirements changes
./containers down unitory worker
```

The compose service keys are **`unitory`** (web) and **`worker`** (RQ); the
worker's container is named `unitory-worker`. `REDIS_PASSWORD` is read from
`/run/secrets/redis.pass`, populated by the `sops-decrypt` bootstrap service.

### `.env`

`.env` is gitignored and must exist for compose to parse. Copy
[.env.example](.env.example) to `.env` and fill in the four placeholder
values (`SESSION_SECRET`, `DB_PASSWORD`, `GOOGLE_AUTH_CLIENT_ID`,
`GOOGLE_AUTH_CLIENT_SECRET`). All accepted keys are documented in
[app/config.py](app/config.py).

### First-user bootstrap

Open <https://unitory.bu-its.binghamton.edu/> (or `APP_BASE_URL` for local
runs). The first user to sign in via Google is auto-promoted to `admin`;
subsequent users land as `viewer` until an admin elevates them from
**Admin → Users**.

## Features

- Quick server entry & lookup (Foundation 6 UI, HTMX live search)
- Extended server attribute form (hardware, network, compliance, rack)
- Markdown notes with server-side preview
- Admin panel
  - User account & role management (viewer / editor / admin)
  - Autodiscovery: paste hostnames, scan their `node_exporter` endpoints,
    auto-create or refresh server records
- JSON API: `GET /api/servers` (list) and `GET /api/servers/{id}` (detail)

## Autodiscovery

From **Admin → Discovery**, paste a list of hostnames (one per line), set a
port (default `9100`), and submit. An RQ worker fetches
`http://<host>:<port>/metrics`, parses the Prometheus node_exporter output,
and upserts a `Server` record for each host. Human-entered fields (`owner`,
`notes`, `rack`, `tags`, `compliance_tags`, `purpose`, etc.) are never
overwritten by discovery — only the names listed in
[`DISCOVERY_FIELDS`](app/models/server.py) can be touched.

## Tests

Tests run on the **host** (and that is also how CI runs them — see
[.github/workflows/test-unit.yml](.github/workflows/test-unit.yml)):

```bash
pip install -r requirements.txt -r requirements-dev.txt && pip install -e .
make test-unit                                          # pytest -m unit
pytest -m unit tests/test_markdown.py::test_name        # single test
```

Integration tests need MongoDB + Redis. CI runs them on PRs to `main` against
GitHub Actions service containers (see
[test-integration.yml](.github/workflows/test-integration.yml)). Locally,
point `DB_*` / `REDIS_*` env vars at running instances and call
`pytest -m integration` directly. `make test-integration` is currently broken
(it `cd`s into `tests/` expecting a compose file that does not exist).

## Troubleshooting

### `ServerSelectionTimeoutError` on Google OAuth callback

**Cause**: the `unitory` service started before MongoDB was ready.

**Mitigation in place**: [compose.yml](compose.yml) gates `unitory` and
`worker` on `mongo: service_healthy`; the mongo healthcheck itself lives in
[../common/mongo/compose.yml](../common/mongo/compose.yml). If the error
recurs, raise `start_period` / `retries` on that healthcheck rather than
adding a duplicate one here.

### Worker not picking up jobs

`./containers logs worker` should show `*** Listening on high, default, low...`.
If `REDIS_PASSWORD` is empty or wrong the worker will fail at startup —
verify `/run/secrets/redis.pass` exists in the container and that
`sops-decrypt` reported healthy at boot.

## Further reading

- [CLAUDE.md](CLAUDE.md) — architecture, invariants, CI pipeline.
- [../CLAUDE.md](../CLAUDE.md) `*` — parent stack notes (covers `./containers`,
  sops, traefik, bluecat-api).
- [compose.yml](compose.yml) — the canonical wiring for this service.

`*` That parent file is `~/CLAUDE.md`; the `dockerStacks/` repo itself does
not currently ship its own CLAUDE.md.
