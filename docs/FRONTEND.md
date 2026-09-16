# Frontend

Status: implemented (Phase 20), build- and lint-verified. Never rendered
against a live backend in this environment — see Verification limitation.

Spec section 52 (`REPROX.pdf` page 45, verbatim):

> **§52 FRONTEND** — Use: React, TypeScript, Vite, Tailwind CSS. The dashboard must use real backend data. Core screens: 1. Dashboard, 2. Projects, 3. Experiments, 4. Experiment Detail, 5. Run Detail, 6. Experiment Comparison, 7. Reproducibility Analysis, 8. Provenance Explorer, 9. Experiment Lineage, 10. Dataset Registry, 11. Environment Registry, 12. Artifact Explorer, 13. Investigation Center, 14. Counterfactual Experiments, 15. Historical Search, 16. AI Assistant, 17. Jobs, 18. Reports, 19. Settings.

19 screens total. Per the tracker's own scoping, Phase 20 builds only the
first 3 (Dashboard/Projects/Experiments) — the backend endpoints and
tooling for most of the rest (Investigations, Counterfactuals, Dataset/
Environment/Artifact registries, Search, Reports) are already `OUT OF
SCOPE for MVP`, so their screens are out of scope here too. Screen 6
(Experiment Comparison) is Phase 21's job.

## Stack

`frontend/`, scaffolded via `npm create vite@latest frontend -- --template react-ts`:
React 19 + TypeScript + Vite, `react-router-dom` for the 3 routes, and
**Tailwind CSS v4** (`@tailwindcss/postcss` + `autoprefixer`, imported via
`@import "tailwindcss";` in `src/index.css` — v4's setup, no
`tailwind.config.js`/`@tailwind` directives needed).

## Dev-server → backend wiring: proxy, not CORS

`vite.config.ts` proxies `/api/*` to `http://localhost:8000` in dev. This
means **no CORS middleware was added to the backend** — Phase 20 stays
pure frontend, consistent with Phase 19's own note that "Phases 20/21 are
pure frontend... no backend work expected." In production this app would
be served behind the same origin as the API (or a reverse proxy
replicating this rule); that's a deployment concern, not addressed here.

## API client

`src/api/types.ts` — hand-written TypeScript types mirroring
`backend/app/schemas/*.py` field-for-field. Not code-generated: for 5
endpoints across 3 pages, an OpenAPI-codegen dependency would be more
machinery than the surface justifies, consistent with this project's
existing "no dependency beyond what's needed" pattern (e.g. Phase 13
skipped a stats library for tolerance math, Phase 16 skipped a graph
library). `src/api/client.ts` is a thin `fetch` wrapper (no axios) that
translates the backend's `{"error": {"code","message","details"}}` shape
(from `app.core.errors.reprox_error_handler`) into a typed `ApiError`.

## Visualizations

`src/components/BarBreakdown.tsx` is a hand-rolled proportional bar
chart (Tailwind width percentages driven directly by real counts) — no
charting library. Satisfies §53's "meaningful, not decorative, every
visualization must represent actual backend data" without one: a bar's
width *is* the data, nothing is precomputed or decorative.

## Pages

- **Dashboard** (`/`) — `GET /api/v1/dashboard`: stat cards for all 8
  §53 fields, the reproducibility-classification `BarBreakdown`, and a
  recent-experiments list.
- **Projects** (`/projects`) — `GET`/`POST /api/v1/projects`: list plus
  a create form (name/slug/description), refreshing the list on success.
- **Experiments** (`/experiments`) — `GET`/`POST /api/v1/experiments`:
  list plus a create form with a project selector populated from the
  Projects list.

Every page distinguishes **loading / error / empty / populated** states
via the shared `src/hooks/useApiResource.ts` hook — not a corner cut for
this environment specifically, but the correct way to build a page whose
backend may legitimately be unreachable.

## Verification limitation

Unlike Phases 17-19, this phase's tooling *is* fully available here
(Node v22.20.0, npm 10.9.3, and the npm registry is reachable) — so
`npm install`, `npm run build` (TypeScript project build via `tsc -b` +
`vite build`), and `npm run lint` (`oxlint`) all ran successfully in this
session, and the Vite dev server was started and confirmed to serve the
app shell (`curl` against `/` returns the expected HTML, `200` on
`/src/main.tsx`).

**What is not verified**: that any page renders real data. No reachable
Postgres exists in this environment (the same limitation Phase 19
documented), so opening these pages against a running backend was never
actually tried — a real run would need `uvicorn` + Postgres up, at which
point the loading → ready path (not just the loading → error path) could
be observed for the first time.
