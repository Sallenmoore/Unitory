# Unitory

Server inventory management for Binghamton University Linux servers.

Stack: FastAPI · HTMX · Foundation 6 · MongoDB · Redis/RQ · built on the local
[`autonomous`](./autonomous) framework for models, tasks, and user auth.

## Quick start

```bash
cp .env.example .env
# fill in DB_PASSWORD, SESSION_SECRET, GOOGLE_AUTH_CLIENT_ID, GOOGLE_AUTH_CLIENT_SECRET
docker compose up --build
```

Then open <http://localhost:8000/>. The first user to sign in via Google is
auto-promoted to `admin`; subsequent users land as `viewer` until an admin
elevates them from **Admin → Users**.

## Features

- Quick server entry & lookup (Foundation 6 UI, HTMX live search)
- Extended server attribute form (hardware, network, compliance, rack)
- Extensive markdown notes with server-side preview
- Admin panel
  - User account & role management (viewer / editor / admin)
  - Autodiscovery: paste hostnames, scan their `node_exporter` endpoints,
    auto-create or refresh server records
- JSON API: `GET /api/servers` (list) and `GET /api/servers/{id}` (detail)

## Autodiscovery

From **Admin → Discovery**, paste a list of hostnames (one per line), set a
port (default `9100`), and submit. An RQ worker fetches
`http://<host>:<port>/metrics`, parses the Prometheus node_exporter output,
and upserts a `Server` record for each host. Human-entered fields (owner,
notes, rack, tags, compliance) are never overwritten by discovery.

## Development

The `autonomous/` directory is a live submodule — edit it freely; changes are
picked up via editable install and the `--reload` dev server.

```bash
# run tests inside the web container
docker compose run --rm web pytest
```

See [compose.yml](compose.yml) for service definitions.
