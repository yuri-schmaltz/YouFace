# Changelog

All notable changes to this fork are documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/) for the
fork-specific portion of the version (`-my.X`).

> **Upstream:** This is a fork of [`facefusion/facefusion`](https://github.com/facefusion/facefusion).
> Upstream releases and their notes live at <https://github.com/facefusion/facefusion/releases>.
> Only **fork-specific** changes appear here; for upstream changes, consult the
> corresponding upstream release notes (see the "Upstream divergence" section in `README.md`).

---

## [3.9.0-my.1] — 2026-09-28

**Fork base:** upstream `3.9.0` (commit `6b318a9`).
**Merged upstream:** `3.7.0`..`3.9.0` (13 commits, ~80 files).
**Status:** Sincronizado com upstream 3.9.x. Inclui 78 commits próprios do fork
sobre a base 3.6.1 + 13 commits upstream. **Ahead** of upstream 3.6.1 by ~90
commits. Upstream master pós-3.9.0 sem novos tags.

### 🛠 Changed

- **P3-1 — Merge upstream 3.9.0.** Commit único (`6b318a9 load voice extractor
  on every processor`). 8 arquivos, +118/-15 LoC. Adiciona suporte a voice
  extractor no face swapper e expande `face_landmarker.py` (+84 LoC).
- **P1-1 — Decomposição do `page.tsx` concluída.** 78 `useState` reduzidos a
  8, todos migrados para os 7 hooks agregadores em `frontend/src/hooks/`. Os
  64 `useState` do Studio foram para `useStudioState`, 6 do system config
  foram para `useConfig`, 3 do wizard foram para `useWizard`. As 100+
  referências a setters foram preservadas via wrappers thin (zero overhead)
  para não tocar nos call-sites no JSX. Arquivo tem 1.265 linhas mas está
  semanticamente decomposto: cada hook é um bounded context com API tipada.
- **P2-1 — SSE hardening no `useJobs`.** `connectionMode` exposto
  (`'connecting' | 'sse' | 'polling' | 'offline'`), 30s inactivity timeout
  que detecta SSE zumbi, `fetchJobs()` no mount (data imediata), Visibility
  API integration (polling pausa quando aba oculta). Novo
  `ConnectionModeBadge` renderiza o estado com cores semânticas no
  `StatusBar` (verde SSE, amber polling, vermelho offline).

### 🐛 Fixed

- **Testes adicionados (P1-3 + P1-4).** 14 novos testes unitários em
  `tests/test_path_validation.py` (8 testes LFI) e
  `tests/test_media_cleanup.py` (6 testes age-based cleanup). Rodam em
  0.4s sem dependências externas. Função `validate_safe_path` validada
  contra path traversal, prefixos similares (`/foo/allowed` vs
  `/foo/allowed_sibling`), paths absolutos não-autorizados, etc.

### 🧪 Housekeeping

- **E2E infrastructure (Playwright).** Novo `frontend/playwright.config.ts`
  + `frontend/e2e/cockpit-smoke.spec.ts` (3 testes smoke). `@playwright/test`
  adicionado a `package.json`. Job `e2e` no CI boota backend + roda os
  testes; depende de `test`+`frontend-check`+`api-tests` verde.
- **Backend smoke em hardware real.** Verificado em RTX 3060 / driver
  595 / CUDA 13: 23/23 módulos importam, 9/9 endpoints retornam 200, GPU
  detectada. Detalhes em `notes/smoke_2026-09-28.md`.
- **Release notes** para `3.9.0-my.1` em `RELEASE_NOTES_3.9.0-my.1.md`.
- **README** atualizado com a decomposição em hooks e versão bumped.

### ⬆️ Upstream divergence

| Upstream tag | Status |
|---|---|
| `3.6.0` | ✅ merged (`57fcb86`) |
| `3.6.1` | ✅ merged (`5b7d145`) — fork base |
| `3.7.0` | ✅ merged em `3.8.3-my.1` (`7bb86d9`) |
| `3.7.1` | ✅ merged em `3.8.3-my.1` (`7bb86d9`) |
| `3.8.0` | ✅ merged em `3.8.3-my.1` — memory leak hotfix |
| `3.8.1` | ✅ merged em `3.8.3-my.1` |
| `3.8.2` | ✅ merged em `3.8.3-my.1` |
| `3.8.3` | ✅ merged em `3.8.3-my.1` |
| `3.9.0` | ✅ merged em `3.9.0-my.1` (`1e61875`) — fork base |
| `3.9.0+` | upstream master sem novos tags; nada pendente |

---

## [3.8.3-my.1] — 2026-09-28

**Fork base:** upstream `3.6.1` (commit `5b7d145`).
**Merged upstream:** `3.7.0`..`3.8.3` (12 commits, 79 files).
**Status:** Primeiro release do fork sincronizado com upstream 3.8.x.
**Behind** upstream `3.9.0` (1 commit, absorvido em `3.9.0-my.1`).

### 🛠 Changed

- **P3-1 — Merge upstream 3.7.0..3.8.3.** 12 commits absorvidos: hotfix de
  memory leak (3.8.0), refactor de `streamer.py` e `temp_helper.py`,
  expansão de `video_manager.py` (+151 LoC) e `types.py` (+112 LoC), e
  alinhamento quase-completo do módulo `workflows/*` (que o fork já tinha
  criado a partir do design upstream 3.7.0+).
- **P3-1 — Resolução de 2 conflitos.** `metadata.py` (fork vence, version
  bumped para `3.8.3-my.1`); `requirements.txt` (fork vence — pinos do Poetry
  são a fonte da verdade). Resto do merge automático.
- **P2-3 — Suporte a LAN / paths relativos.** O backend grava agora
  `apiUrl: ""` (caminho relativo) em `frontend/public/config.json`,
  adicionando `apiUrlAbsolute` para compatibilidade. O frontend (`utils/api.ts`)
  prefere caminho relativo quando disponível, destravando deploy via reverse
  proxy e acesso via IP de LAN sem trocar `config.json` manualmente.
- **P1-4 — Cleanup age-based.** `POST /media/cleanup` aceita agora
  `max_age_seconds` (default 3600s). Arquivos mais novos que o limite são
  preservados para evitar race com jobs em curso.
- **P1-1 — Decomposição do `page.tsx` (passo 1).** Adicionado o hook agregador
  `frontend/src/hooks/useStudioState.ts` (221 linhas tipadas, 5 interfaces
  públicas: `StudioState`, `ProcessorOptions`, `OutputOptions`, `MaskOptions`,
  e a função `useStudioState()`). JSDoc inclui migration guide.
- **P0-1 — Piso de Python subido para 3.12** em `pyproject.toml` e `Dockerfile`.
  CI já rodava em 3.12 — alinhamento sem regressão.
- **P0-1 — `requirements.txt` ⇄ `pyproject.toml` sincronizados.** Removido
  pino morto de `onnxruntime` (o `installer.py` injeta o flavor correto via
  CLI arg: `default`/`cuda@12`/`cuda@13`/`openvino`/`rocm`/`directml`).
  Adicionado `psutil` ao Poetry (já era dependência runtime usada em
  `routes.py:167-201`) e `httpx` ao dev group (TestClient nos testes de API).
  `requirements.txt` agora é mirror documentado do Poetry.

### 🐛 Fixed

- **P3-2 — CI endurecido.** Adicionado `npx tsc --noEmit` (type-check TS),
  `npm run build` (next export) e `npm run lint` (eslint estrito, sem `|| true`)
  no job `frontend-check`. Jobs `test` e `report` agora instalam as deps
  fork (`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `python-multipart`,
  `psutil`, `httpx`) que o `install.py` oficial pode não trazer.
- **P3-2 — Job `api-tests` dedicado.** Novo job CI roda `pytest
  tests/test_api_endpoints.py tests/test_api_face_mapping.py
  tests/test_api_worker.py` em Python 3.12 limpo, com upload de artefatos
  em caso de falha. Precisa do `test` e `frontend-check` verde para rodar.

---

## [3.7.0-my.1] — 2026-07-15

**Fork base:** upstream `3.6.1` (commit `5b7d145`).
**Status:** First tagged release of this fork. Brings the codebase in line with
upstream `3.6.1` plus 16 fork-specific commits. **Behind** upstream `3.7.0` / `3.7.1`
(merged into `3.8.3-my.1` / `3.9.0-my.1` — see above).

### ✨ Highlights

- **New: Decoupled Web UI (Cockpit).** A Next.js 16 frontend replaces the Gradio
  monolithic UI. The frontend is statically exported and served by FastAPI,
  communicating with the backend exclusively through a documented REST API
  (`/api/...`).
- **New: FastAPI backend layer.** Added `facefusion/api/` (database, routes,
  worker, main) and a `run_api.py` entrypoint that auto-discovers a free TCP
  port and publishes the URL to the frontend.
- **New: Workflows module.** Added `facefusion/workflows/` with dedicated
  pipelines for `image_to_image` and `image_to_video`, including a modernized
  type system and standardized translation handling.
- **New: Multi-source face selection + granular face mapping.** Submit multiple
  source images and choose exactly which detected face in the target receives
  which source face.
- **New: Real-time job progress tracking.** Jobs now expose a `progress` field
  (0–100) that updates while the worker is running, and the frontend polls it
  every 2 s.
- **New: Single-frame preview (auto + manual).** Generate a quick preview of
  the swap on a single frame before committing to a full render.
- **New: Diagnostic export endpoint with PII sanitization.** Downloads a ZIP
  bundle of logs, configs and system info, with all local user paths
  (`/home/<user>`, `C:\Users\<user>`) masked to `/home/user` / `C:\Users\user`.
- **New: Atomic JSON writes + XDG-compliant path management** to prevent
  half-written config files and to respect platform conventions.
- **New: Backend logger + custom frontend design system** (dark mode, glass
  surfaces, semantic status colors, toast notifications, slide-comparator
  video player).
- **New: Explicit application context** (`cli` vs `ui`) wired through
  `facefusion.app_context` so code paths that must differ between modes are
  deterministic.

### 🛠 Changed

- **API endpoint refactor** (`1c1f741`) — frontend layout optimized for
  responsive display.
- **FFmpeg process robustness** (`18a4a3a`) — better job path resolution and
  file-download tracking.
- **Environment initialization** (`368e13f`) — added GPU memory limit and
  refreshed the frontend video comparator.
- **Frontend static export mount** (`f740f0b`) — Next.js build is now served
  directly by FastAPI; build binaries are git-ignored.
- **Default thread count** is now set in core (`dd90887`).
- **Processor pre-check validation** added before kickoff (`dd90887`) — early
  fail with a clear error message instead of a mid-run crash.

### 🐛 Fixed

- **FFmpeg test invocations** now pass `-y` so existing outputs can be
  overwritten (`1ff545f`).
- **Test fixtures** hardened with null checks and explicit boolean
  type-casting (`6d86b16`).

### 🧹 Housekeeping

- `.new_jobs_path_test/` removed from the working tree and added to
  `.gitignore` to prevent re-leaking test scaffolding.
- `.gitignore` extended to cover `frontend/.next/`, `frontend/out/`,
  `frontend/node_modules/`, `out/`, `tmp/`, local `*.ini` overrides, and
  common OS/editor noise.
- `facefusion/__init__.py` previously empty; now declares
  `version = "3.7.0-my.1"` and metadata so the Python package is
  introspectable.

---

## Pre-fork history

Inherited from upstream `facefusion/facefusion`. See upstream
[`CHANGELOG.md`](https://github.com/facefusion/facefusion/blob/master/CHANGELOG.md)
for everything before `3.6.1`.
