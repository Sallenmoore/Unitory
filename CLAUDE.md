# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This compose file is **not standalone** — it expects `mongo`, `redis`, `sops-decrypt`, the `docknet` network, and the `secrets` volume to come from the parent [dockerStacks](../) tree. Bring the app up via the parent driver, not `docker compose` directly:

```bash
# from /home/itsadmin/dockerStacks/
./containers up unitory worker        # web + RQ worker (and their deps via depends_on)
./containers logs worker              # tail the RQ worker (service key is 'worker', container is 'unitory-worker')
./containers down unitory worker
./containers rebuild unitory          # build --no-cache
```

The compose **service keys** in [compose.yml](compose.yml) are `unitory` (web) and `worker` (RQ); the worker's `container_name` is `unitory-worker`, but the docker-compose service key — what `./containers <action> <svc>` takes — is just `worker`. Both services share one image and bind-mount `./app` and `./worker` for live reload (`uvicorn --reload`). `REDIS_PASSWORD` is read from `/run/secrets/redis.pass` (decrypted by `sops-decrypt`) at container start — see the `command:` line in [compose.yml](compose.yml).

Tests run on the **host**, not in the container — that is also how CI runs them:

```bash
pip install -r requirements.txt -r requirements-dev.txt && pip install -e .
make test-unit                                       # pytest -m unit
pytest -m unit tests/test_markdown.py::test_name     # single test
```

`make test-integration` is currently broken (it `cd`s into `tests/` expecting a compose file that doesn't exist). For local integration runs, point Mongo/Redis env vars at running instances and call `pytest -m integration` directly — CI does this with GitHub Actions service containers (see [test-integration.yml](.github/workflows/test-integration.yml)). Python 3.13+ is required.

`.env` is gitignored and must exist for compose to parse — copy [.env.example](.env.example) and fill in the placeholders (`SESSION_SECRET`, `DB_PASSWORD`, `GOOGLE_AUTH_CLIENT_ID`, `GOOGLE_AUTH_CLIENT_SECRET`). All accepted keys are read in [app/config.py](app/config.py).

### Startup dependencies

`unitory` and `unitory-worker` wait on `sops-decrypt` (healthy), `mongo` (healthy), and `redis` (started). The mongo healthcheck lives in [dockerStacks/common/mongo/compose.yml](../common/mongo/compose.yml), not here — don't add a duplicate. This ordering prevents the OAuth-callback `ServerSelectionTimeoutError` that motivated the gating in the first place.

### Healthchecks

`unitory` exposes `GET /healthz` ([app/routes/health.py](app/routes/health.py)) which pings Mongo and Redis with short (~1.5s) timeouts and returns `{"db": "ok", "redis": "ok"}` on 200, or `{"db": "fail: ...", ...}` on 503 if either is down. `compose.yml` calls it via `curl -fs` every 30s.

`unitory-worker` has no HTTP surface; its compose healthcheck runs [worker/healthcheck.py](worker/healthcheck.py), a tiny script that pings Redis with the same credentials the worker uses. Mongo is intentionally not pinged from the worker — the worker's "healthy" state is "process running, listening on Redis." Mongo failures surface as job failures, not container-level unhealthy.

### Test tiers

Tests are split into two tiers via pytest markers (registered in [pyproject.toml](pyproject.toml); `--strict-markers` is enforced):

- `pytest -m unit` — pure logic, no external services. CI runs on every PR to `dev` and `main`.
- `pytest -m integration` — needs Mongo + Redis. CI runs only on PRs to `main` and nightly. Locally: `make test-integration` spins up the compose stack first.

When adding a test, pick the tier. Unit tests must not import anything that opens a DB/Redis connection at import time.

## Architecture

### Dependency on the `autonomous` framework

The `autonomous-app` package (PyPI, pinned `>=0.3.113` in [requirements.txt](requirements.txt)) provides the ORM (`AutoModel` + `autoattr` typed fields backing MongoDB), auth primitives (`autonomous.auth.user.User`), and the RQ-backed task runner (`AutoTasks`). It is installed into the image — it is **not** mounted from a sibling directory; the Dockerfile only `COPY`s `app/` and `worker/`. Models in [app/models/](app/models/) inherit from `AutoModel`; [AppUser](app/models/user.py) subclasses the framework `User` specifically to stop `authenticate()` from clobbering admin-promoted roles on each login and to bootstrap the first user as admin. [tests/conftest.py](tests/conftest.py) preemptively inserts `autonomous/src` onto `sys.path` so a locally-checked-out copy (when one exists alongside the repo) shadows the installed package — useful when iterating on the framework, irrelevant otherwise.

### Request flow

[app/main.py](app/main.py) mounts five routers — `health`, `auth`, `api`, `admin`, `web` — and registers custom 401/403 handlers that branch on `/api/` path prefix: API paths get JSON/text errors, HTML paths redirect to `/auth/login` or render `403.html`. Auth is cookie-session (`SessionMiddleware`) storing only `user_pk`; the current user is resolved per-request by [get_current_user](app/deps.py) and role-gated via `require_viewer` / `require_editor` / `require_admin` dependencies. Templates receive the user via `request.state.user` (attached by the same dependencies).

### Roles and the first-admin invariant

Three roles in [app/models/user.py](app/models/user.py): `viewer` → `editor` → `admin`. `AppUser.authenticate` assigns `admin` to the *first* user to log in (when no admins exist) and `viewer` to everyone after; on repeat logins the existing role is preserved. Admins cannot demote or delete themselves (see [app/routes/admin.py](app/routes/admin.py)).

### Autodiscovery: the human-fields-are-sacred rule

[app/services/discovery.py](app/services/discovery.py) enqueues RQ jobs that scrape `http://<host>:<port>/metrics` (node_exporter) and upsert a `Server`. The critical invariant is [DISCOVERY_FIELDS](app/models/server.py) — a hard-coded frozenset of attribute names (hardware, network, OS, DMI data). Only fields in this set are allowed to be overwritten by discovery; human-authored fields (`owner`, `notes`, `rack`, `tags`, `compliance_tags`, `purpose`, etc.) are never touched by a scan. When adding a new `Server` attribute, decide deliberately whether it belongs in `DISCOVERY_FIELDS`.

Discovery imports the ORM *inside* `scan_hosts` (not at module top) so the Mongo connection is opened in the RQ worker process, not at import time. The worker is a separate Compose service running `rq worker high default low` via [worker/entrypoint.sh](worker/entrypoint.sh) and shares the image with `web`.

### Node exporter parsing

[app/services/node_exporter.py](app/services/node_exporter.py) flattens Prometheus metric families into a Server-shaped dict. Note that `prometheus_client` strips the `_total` suffix from counter names, so code looks up both `node_cpu_seconds` and `node_cpu_seconds_total`. Missing metrics produce missing keys (not errors) — the upsert step then skips empty values so partial scans don't wipe previously-known data.

### HTMX + server-rendered markdown

The UI is Jinja2 + Foundation 6 + HTMX. Live search (`/servers/search`) and the discovery job status poll return HTML partials from `templates/partials/` and `templates/admin/_job_status.html`. Notes are markdown rendered server-side by [render_markdown](app/services/markdown.py) (markdown2 → bleach allowlist sanitization); the same function is registered as a Jinja filter in [app/deps.py](app/deps.py) *and* exposed via `POST /servers/preview-notes` for live preview.

## CI/CD

### Pipeline shape

```text
ai/<feature-slug>          (per-task branch, cut from ai-development)
        │
        ▼  PR (lint + unit tests required)
      dev                  (integration tier; PRs to main cut from here)
        │
        ▼  PR (lint + unit + integration tests required, 1 approval)
      main                 (protected; default branch)
        │
        ▼  git tag vX.Y.Z
```

### AI contribution conventions

- AI-authored branches are named `ai/<slug>` and cut from `ai-development`.
- PRs target `dev`. Squash-merge preferred to keep `dev` history readable.
- `ai-development` is periodically fast-forwarded to `dev` so future AI branches start from the latest integrated state:

  ```bash
  git checkout ai-development
  git merge --ff-only origin/dev
  git push
  ```

- Before opening a PR, run `make test-unit` locally to catch breakage early — CI will do the same but local feedback is faster.
- After a `dev → main` merge, tag a release: `git tag vX.Y.Z && git push origin vX.Y.Z`. The `release.yml` workflow creates the GitHub Release with auto-generated notes.

### Workflows

- [.github/workflows/lint.yml](.github/workflows/lint.yml) — flake8 hard-error subset (E9/F63/F7/F82) + soft report. Runs on PRs to `dev` and `main`.
- [.github/workflows/test-unit.yml](.github/workflows/test-unit.yml) — `pytest -m unit` on Python 3.13 and 3.14. Runs on PRs to `dev` and `main`.
- [.github/workflows/test-integration.yml](.github/workflows/test-integration.yml) — `pytest -m integration` against Mongo + Redis service containers. Runs on PRs to `main` and nightly (06:00 UTC).
- [.github/workflows/release.yml](.github/workflows/release.yml) — creates a GitHub Release on `v*` tag push.

## Conventions

- Environment config is centralized in [app/config.py](app/config.py) (`Settings` dataclass, `lru_cache`d via `get_settings()`). `SESSION_SECRET` is required — startup raises if unset.
- Model query patterns use the framework's `Model.objects`, `Model.get(pk)`, `Model.find(**kwargs)`, `Model.search(...)` — not raw pymongo.
- When writing tests that need Mongo, `mongomock` is in `requirements-dev.txt`; unit tests in [tests/](tests/) avoid the DB entirely where possible (parser and markdown tests are pure functions).
