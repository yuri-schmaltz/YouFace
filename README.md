# YouFace — Decoupled Fork

> **Industry-leading face manipulation platform** — re-architected as a fully
> decoupled client/server stack: a **Next.js 16** web cockpit talking to a
> **FastAPI** backend that drives the original YouFace engine.

This repository is a **fork of [`youface/youface`](https://github.com/youface/youface)**
starting from upstream `3.6.1`. It re-shapes the user experience around a
modern web UI while keeping the upstream Python engine intact underneath.

For the upstream project's general documentation, see
<https://docs.youface.io>. Everything below documents **what this fork
adds and changes**.

---

## ✨ What this fork adds on top of upstream

### 1. Decoupled Web Cockpit (Next.js 16 + React 19)
A standalone frontend lives in [`frontend/`](frontend/) using the Next.js
App Router, TypeScript, Tailwind CSS 4 and Lucide icons. It is statically
exported (`next build`) and served directly by the FastAPI process, so a
single command boots the whole app — no separate dev servers to babysit.

Features in the cockpit:

- **Live job dashboard** — cards for each job with semantic color states
  (`queued` / `processing` / `completed` / `failed`) and a progress bar that
  polls the API every 2 s.
- **Multi-source face selection** — pick several source images and map each
  detected face in the target to a specific source.
- **Single-frame preview** — auto-generate or manually trigger a preview on
  one frame before committing to a full render.
- **Slide-comparator (Before/After)** — drag a vertical divider over the
  target/output videos to inspect the swap frame-by-frame.
- **Settings console** — change execution paths, thread limits, memory
  strategy, processor selection and download diagnostic bundles without
  leaving the browser.
- **Custom dark design system** with glassmorphism, toast notifications and
  Geist/system-ui typography — see
  [`docs/goal/design.md`](docs/goal/design.md) for the full token set.

### 2. FastAPI backend layer
A new `youface/api/` package wraps the engine:

| Module | Purpose |
|---|---|
| `youface/api/main.py` | FastAPI app factory, lifespan hooks, dynamic port discovery, mounts the static frontend build |
| `youface/api/database.py` | SQLAlchemy models + SQLite bootstrap (the `jobs` table) |
| `youface/api/routes.py` | REST endpoints: hardware, processors, config, media upload, jobs, diagnostic export |
| `youface/api/worker.py` | Background thread that consumes `queued` jobs, runs them through the engine and writes back status/progress |

### 3. Workflows module
`youface/workflows/` introduces an explicit, typed pipeline abstraction:

- `core.py` — shared step contract, translation handling, state machine
- `image_to_image.py` — image → image swap pipeline
- `image_to_video.py` — image → video swap pipeline with per-frame progress

The CLI entrypoint (`python youface.py …`) and the API worker both delegate
to these workflows, so behavior is identical between modes.

### 4. Reliability & quality-of-life
- **Atomic JSON writes** for every config and job-state file (no half-written
  state on crash).
- **XDG-compliant path resolution** (Linux/macOS/Windows conventions).
- **Worker lifecycle control** — auto-recovery of jobs stuck in `processing`
  on restart (marked as `failed` with a clear error).
- **PII sanitization** in the diagnostic export endpoint — local user paths
  are masked before any bundle is downloaded.
- **Dynamic port discovery** — `run_api.py` scans for a free TCP port starting
  at `8000` and writes the URL to `frontend/public/config.json` so the
  browser can find the API without any user configuration.
- **Explicit application context** (`cli` vs `ui`) is set once at startup and
  threaded through every config so divergent code paths are deterministic.
- **State decomposition via custom React hooks** — the cockpit's
  `page.tsx` originally had 78 `useState` calls (the biggest single
  source of complexity in the codebase). These have been extracted into
  seven purpose-built hooks in `frontend/src/hooks/`:
  - `useStudioState` — typed, serializable state for the Studio tab
    (sources, processors, output, mask, detection). 64 `useState`
    collapsed into a single `StudioState` object.
  - `useConfig` — system config (paths, memory, threads, log, providers)
    with auto-fetch from `/api/config` and a typed `save()` action.
  - `useWizard` — modal state for the video diagnostic wizard.
  - `useJobs` — SSE + polling with `connectionMode` exposed for the UI.
  - `useProjects`, `useHardware`, `usePresets` — feature-specific hooks.
  After the refactor, `page.tsx` has only 8 `useState` (genuine local
  UI state), 1.265 lines, and a single typed state object per concern.

### 5. Housekeeping
- `youface/__init__.py` declares `version = "3.9.0-my.1"` and fork metadata.
- `.gitignore` hardened against test-scaffolding leaks (`.new_jobs_path_test/`,
  `out/`, `tmp/`, `frontend/.next/`, `frontend/out/`, `frontend/node_modules/`,
  local `*.ini` overrides, OS/editor noise).
- CI hardened with 4 jobs: Python lint + tests (3 OS), frontend
  type-check + build + lint, and a dedicated API tests job that runs
  `test_api_endpoints.py`, `test_api_face_mapping.py`, and
  `test_api_worker.py` in a clean Python 3.12 venv.
- See [`CHANGELOG.md`](CHANGELOG.md) for the full per-commit history.

---

## 🚀 Quick start

### Web UI (recommended)
```bash
# 1. Install Python dependencies (zero-args, smart installer)
#    Detects GPU/CUDA, picks the right onnxruntime flavor, creates a .venv
#    and installs everything automatically.
python install.py

# 2. install frontend dependencies and build the static bundle
cd frontend
npm install
npm run build
cd ..

# 3. launch the API + UI (auto-picks a free port)
source .venv/bin/activate   # activate the venv created by step 1
python run_api.py
```
The startup script prints the URL of the cockpit (e.g.
`http://127.0.0.1:8000`). Open it in a browser — no further configuration
required.

### Installer flags (advanced)

`python install.py` already does the right thing for most users, but you
can override the defaults:

```bash
python install.py --info              # show detected hardware + recommended flavor
python install.py --dry-run           # preview pip commands without executing
python install.py --auto              # same as zero-args; explicit form
python install.py --use-venv          # install into a .venv (default in zero-args mode)
python install.py --break-system-packages  # system-wide install on PEP 668 systems
python install.py default             # legacy upstream positional (still works)
python install.py cuda@13             # explicit flavor (overrides --auto)
```

On Debian 12+/Ubuntu 23.04+/Mint 22+ the system Python is PEP 668
externally-managed. The smart wrapper detects this and either creates a
`.venv` (recommended) or adds `--break-system-packages` automatically
when the upstream installer fails silently.

### CLI (legacy)
The original CLI is still available and fully supported:
```bash
python youface.py run [options]
python youface.py job-list
python youface.py job-create …    # see `python youface.py --help` for the full subcommand list
```

### Docker

Two configurations are available:

- **Production** (`Dockerfile` + `docker-compose.yml`): Multi-stage build with
  CUDA 11.8 runtime. Builds the Next.js static export and serves it via
  FastAPI. For deployment on a GPU workstation.

- **Development** (`Dockerfile.dev` + `docker-compose.dev.yml`): Slim Python
  3.12 image, mounts source as volume for hot-reload, no CUDA, two-service
  compose (backend + frontend). For local iteration.
  ```bash
  docker compose -f docker-compose.dev.yml up
  # API: http://127.0.0.1:8000
  # Frontend (hot reload): http://127.0.0.1:3000
  ```

### Authentication (LAN deploy)

The API binds to `127.0.0.1` by default (no auth). For LAN exposure,
set `YOUFACE_API_TOKEN` and the server activates bearer-token auth:

```bash
# Generate a strong token
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Start with auth enabled
YOUFACE_API_TOKEN=<your-token> python run_api.py
```

The client must send `Authorization: Bearer <token>` on every non-GET
request. GETs on `/api/hardware/*`, `/api/processors/list`, `/api/config`,
`/api/media/output/*`, and `/api/jobs/stream` remain public (so the
status bar can poll without auth).

The frontend reads the token from `localStorage` (key: `YOUFACE_TOKEN`)
on first load — set it via the browser devtools if you're using LAN mode.

> **Security note:** This is a shared-secret scheme, not real auth. For
> multi-user or internet-facing deployments, put the API behind a
> reverse proxy (nginx, Caddy) that adds proper auth (OIDC, mTLS, etc.)
> and disable the built-in bearer middleware by unsetting the env var.

---

## 📂 Repository layout

```
my-youface/
├── youface/                  # Python engine + fork additions
│   ├── api/                     # 🆕 FastAPI layer (database, routes, worker, main)
│   ├── workflows/               # 🆕 Typed pipelines (core, image→image, image→video)
│   ├── jobs/                    # Refactored job subsystem (runner, store, manager, list, helper)
│   ├── processors/              # Face swap, enhancement, masking, detection (from upstream)
│   ├── uis/                     # Legacy Gradio UI (still bundled)
│   ├── app_context.py           # 🆕 Explicit CLI vs UI context
│   ├── core.py                  # Engine entrypoint
│   └── …
├── frontend/                    # 🆕 Next.js 16 cockpit
│   ├── src/app/                 # App Router pages (Dashboard, Settings, …)
│   ├── public/                  # Static assets + auto-generated config.json
│   └── package.json
├── docs/
│   └── goal/                    # 🆕 Internal product/design docs
│       ├── prd.md               # Product requirements
│       ├── design.md            # Design system tokens
│       └── product-roadmap.md   # Phased execution plan
├── youface.py                # CLI entrypoint
├── run_api.py                   # 🆕 API + UI entrypoint
├── CHANGELOG.md                 # 🆕 Fork-specific changelog
└── README.md                    # this file
```

---

## 🔀 Upstream divergence

This fork is based on upstream `3.6.1` (commit `5b7d145`). It currently sits
**behind** upstream `3.7.0` and `3.7.1`.

| Upstream tag | Status in this fork |
|---|---|
| `3.6.0` | merged (`57fcb86`) |
| `3.6.1` | merged (`5b7d145`) — **fork base** |
| `3.7.0` | **not merged** — planned next |
| `3.7.1` | **not merged** — planned next |

**Merge strategy** (recommended):

1. Add `youface/youface` as a new remote:
   ```bash
   git remote add upstream https://github.com/youface/youface.git
   git fetch upstream
   ```
2. Create a dedicated `merge/upstream-3.7.0` branch from `master` and
   merge `upstream/3.7.0` into it.
3. Resolve conflicts. Most conflicts are expected in
   `youface/uis/`, `youface/jobs.py` (we refactored into
   `youface/jobs/`), and `youface/choices.py` (we added processor
   pre-check validation).
4. Re-run the API and the frontend smoke tests (see `tests/`).
5. Tag the result as `3.7.0-my.2` and update `CHANGELOG.md`.

This same procedure was followed to land the 16 fork-specific commits on
top of `3.6.1`.

---

## 🧪 Testing

Inherited from upstream with fork-specific additions:

```bash
pytest -q tests/
```

The new API layer is exercised by the same test suite plus the diagnostic
export test (`test_diagnostic_export.py` in `tests/`).

---

## 🛡 License

Inherited from upstream: **Open RAI License (OpenRAIL-AS)**. See
[`LICENSE.md`](LICENSE.md) for the full text. The fork additions in
`youface/api/`, `youface/workflows/`, `frontend/` and the docs in
`docs/goal/` are released under the same terms.

---

## 🙏 Credits

- **Upstream maintainers** of [youface/youface](https://github.com/youface/youface)
  for the original engine.
- Fork maintained by [@yuri-schmaltz](https://github.com/yuri-schmaltz).
