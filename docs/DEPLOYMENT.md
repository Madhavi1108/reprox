# Deployment (Phase 32, spec-required)

Status: new. States plainly what's deployable today and what isn't —
acceptance checklist item 39 is "Docker deployment works"; this document
does not claim that's true where it isn't.

## What exists today

- **`docker-compose.yml`** (repo root): containerizes **only Postgres**.
  Its own comment explains why the backend isn't containerized alongside
  it: the backend needs to `docker run` the sandbox workload image
  (Phase 17), which would need Docker-in-Docker if the backend itself
  were containerized — so the dev flow runs the backend on the host.
- **`docker-compose.test.yml`**: an ephemeral Postgres for integration
  tests, on a separate port (`5433`) and `tmpfs` storage so it never
  collides with the dev DB. (No test in this repo currently uses it —
  `docs/TESTING.md` — but it's ready for when one does.)
- **`.env.example`** (repo root): the full set of configuration variables
  (`DATABASE_URL`, `API_HOST`/`API_PORT`, sandbox limits, `.env` is
  `pydantic-settings`-loaded by `app/config.py`).
- **Backend**: runs directly on the host via `uvicorn` against the venv
  in `backend/.venv`; Alembic migrations (`backend/alembic/`) apply the
  schema (`alembic upgrade head`).
- **Frontend**: `frontend/`'s Vite scaffold — `npm run dev` for local
  development (proxies API calls to the backend), `npm run build` for a
  static production bundle. No server is configured to actually serve
  that bundle in production (no nginx config, no static-file mount in
  the FastAPI app).
- **The one real Dockerfile**: `docker/sandbox/Dockerfile` builds
  `reprox-sklearn-runner:latest`, the image `SandboxRunner` (Phase 17)
  runs experiment workloads inside — this containerizes the *thing
  REPROX executes*, not REPROX itself.

## What does not exist

- **No backend Dockerfile.** The FastAPI app has never been packaged as
  a container image.
- **No frontend Dockerfile / static-serving container.**
- **No compose service for the API or frontend** — only Postgres (and,
  separately, the test-only ephemeral Postgres) are in either compose
  file.
- **No CORS middleware** on the backend (`docs/FRONTEND.md`'s Phase 20
  note) — deploying the built frontend against a backend on a different
  origin would fail without adding one.
- **No reverse proxy / TLS termination configuration.**

Acceptance item 39 ("Docker deployment works") is true for the
*database* and the *sandbox execution environment*, and not true for
*REPROX itself* — a whole-app container/compose setup was never built in
any phase. This is a real, currently-unaddressed gap, not a documentation
oversight; see `docs/OUT_OF_SCOPE.md`.

## What a real deployment would need

1. A backend `Dockerfile` (Python 3.12 base, `pip install .`, run
   `uvicorn app.main:app`).
2. A frontend `Dockerfile` or static-hosting setup for `npm run build`'s
   output, plus CORS configuration on the backend for its real origin.
3. A `docker-compose.yml` (or equivalent) service definition for both,
   alongside the existing Postgres service.
4. `alembic upgrade head` run against the target Postgres instance before
   first boot.
5. The sandbox image (`docker/sandbox/Dockerfile`) built and available to
   whatever Docker daemon the backend container would need access to
   (itself requiring Docker-in-Docker or a mounted host socket — the same
   constraint the current host-uvicorn setup avoids).
6. Secrets (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`DATABASE_URL`) supplied
   via the deployment platform's secret store, not committed `.env`.

None of this has been built or verified in this environment.
