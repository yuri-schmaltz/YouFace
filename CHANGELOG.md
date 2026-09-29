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

## [3.9.1-my.1] — 2026-09-28

**Fork base:** upstream `3.9.0` (sem mudança).
**Status:** Gran finale do gauntlet. **149 novos testes** em 9 suítes, **+2.000 LoC Python + 1.000 LoC TS**. Sem mudança de upstream.

### ✨ Highlights (gauntlet R7..R16)

#### R7 — Multi-tenant auth + quotas (#6)
- Novo `facefusion/api/tenants.py` com `TenantModel`, `TenantUsageModel`, hash SHA-256 das API keys.
- `TenantMiddleware` resolve o tenant via `X-API-Key` ou `Authorization: Bearer`, decora response com `X-RateLimit-Limit / X-RateLimit-Used / X-RateLimit-Remaining / X-RateLimit-Period` e `X-Tenant-Id` / `X-Tenant-Name`.
- Endpoints admin: `POST/GET/DELETE /api/admin/tenants`, `/api/admin/tenants/{id}/{rotate,disable,enable,quota}`, `GET /api/admin/usage`.
- Quota ledger cobra minutos de wall-time por job completed/failed. Default 1.000 min/mês. `monthly_quota_minutes=-1` → unlimited.
- **Bug fix (pré-existente):** `is_public_path` agora reconhece os caminhos com prefixo `/api` (antes `/api/config` retornava 401 indevidamente).
- **Bug fix (pré-existente):** `BearerAuthMiddleware` relê `FACEFUSION_API_TOKEN` a cada request (antes era cacheado na `__init__`, o que quebrava `os.environ` patches em testes).
- `tenant_id` agora é gravado em `JobModel.webhook_url`/`tenant_id` para accounting e webhook ownership.

#### R8 — Webhooks de conclusão (#7)
- Novo `facefusion/api/webhooks.py` com dispatcher síncrono (urllib stdlib, zero deps novas).
- Retry exponencial (1s, 2s, 4s, 8s, 16s, máx 5 tentativas). Configurável via `FACEFUSION_WEBHOOK_*` env vars.
- HMAC `sha256=<hex>` em `X-Webhook-Signature` quando `webhook_secret` é fornecido. `X-Webhook-Id` carrega `job_id` para idempotência no consumidor.
- Dead-letter em tabela `webhook_deliveries`; admin pode inspecionar via `GET /api/admin/webhooks[?job_id&status]` + `/api/admin/webhooks/failed`.
- Worker chama `fire_job_completion()` no terminal state (completed/failed/cancelled). Falha do webhook nunca bloqueia o job.
- Novos campos em `JobModel`: `webhook_url`, `webhook_secret`, `tenant_id`, `started_at`.

#### R9 — Presets / recipes (#5)
- Novo `facefusion/api/presets.py` com CRUD completo (`PresetModel`, `PresetCreate`, `PresetUpdate`, `PresetData` espelhando `JobCreateRequest`).
- Endpoints `GET/POST/PUT/DELETE /api/presets` + `POST /api/presets/{id}/apply` (retorna merged data pronto para `POST /api/jobs`).
- Scoping: tenants só veem seus próprios presets + os marcados `shared: true`. Apenas admin pode criar `shared: true`.

#### R10 — Métricas automáticas de qualidade (#8)
- Novo `facefusion/api/metrics.py` com `cosine_similarity`, `temporal_consistency`, `pose_drift` (com wrap-around em ±π).
- `compute_job_metrics(source_embedding, output_embeddings, output_poses)` retorna `{identity_similarity, temporal_consistency, pose_drift, frames_analyzed}`.
- Persistência em `job_metrics` table. Endpoint `GET /api/jobs/{id}/metrics`.
- Se GPU/InsightFace ausente, métricas ficam `None` em vez de falhar o job (graceful degradation).

#### R11 — Plugin marketplace (#4)
- Novo `facefusion/api/plugins.py` descobrindo entry-points via `importlib.metadata.entry_points(group="facefusion.processors")`.
- State persistido em `facefusion/api/plugins.json` (enable/disable toggle). `disable_plugin` sobrevive restart.
- Endpoints admin `GET/POST /admin/plugins`, `/admin/plugins/{name}/{enable,disable}`, `/admin/plugins/reload`.
- Plugin quebra → fica registrado com `summary: "failed to load: ..."` em vez de derrubar o app.

#### R12 — Treinamento dedicado (#1)
- Novo `facefusion/api/trainer.py` com pipeline extract → aggregate → save (`.npy` L2-normalizado de 512-d).
- Worker thread in-process; progresso persistido a cada 5 imagens via `TrainJobModel`. Callbacks `on_progress(processed, total, faces)`.
- Endpoints `POST /api/train`, `GET /api/train[/{id}[/result]]`, `DELETE /api/train/{id}`.
- Stub embedder/detector para CI sem GPU; produção chama `facefusion.face_recognizer`.
- Versão simplificada (não VAE completo como Faceswap); trade-off documentado no docstring.

#### R13 — Backend opcional SimSwap (#2)
- Novo `facefusion/api/backends.py` com `Backend` protocol + `InsightFaceBackend` (default) + `SimSwapBackend` (stub gated por `pip install facefusion[simswap]`).
- `resolve_backend(name)` faz fallback automático para `insightface` se o backend solicitado não estiver instalado.
- Endpoints `GET /api/backends`, `GET /api/backends/{name}`, `GET /api/backends/{name}/active` (lazy-load com cache).
- Novo campo `face_swapper_backend` em `JobCreateRequest`.

#### R14 — Head-swap completo (#3)
- Novo `facefusion/api/headswap.py` com `SwapMode` enum (`face` / `head` / `expression_only`) + `HeadSwapConfig` (mask_expansion_px, include_hair, include_ears, include_neck).
- Endpoint `GET /api/jobs/{id}/head-swap-info` retorna a config usada.
- Worker passa `head_swap` para o LivePortrait pipeline (máscara estendida vs padrão).

#### R15 — Compose multi-perfil (#9)
- 3 novos profiles: `docker-compose.nvidia.yml` (CUDA), `docker-compose.amd.yml` (ROCm), `docker-compose.cpu.yml` (sem GPU).
- `release/start.sh` agora detecta GPU via `nvidia-smi` / `/dev/dri` / `rocm-smi` e seleciona o profile. Override manual via `--profile`.
- Novo `docs/DOCKER_PROFILES.md` com troubleshooting por vendor.

#### R16 — UI i18n (#10)
- Novo `frontend/src/i18n/` com hook `useLocale()`, helper `t(key, values?)` e persistência em localStorage.
- Locale files `en.ts` + `pt-BR.ts` com 30+ strings (actions, job states, navigation, errors).
- `<LocalePicker />` component no header do cockpit.
- Zero deps npm; interpolação `{name}` simples. `docs/I18N.md` com guia de adicionar novos idiomas.

### 🧪 Tests (149 novos, total 252)

| Suite | Tests | Tempo |
|---|---|---|
| `test_api_auth.py` | 13 | 1.0s |
| `test_api_tenants.py` | 23 | 1.5s |
| `test_api_webhooks.py` | 12 | 7.5s |
| `test_api_presets.py` | 17 | 2.8s |
| `test_api_metrics.py` | 25 | 1.0s |
| `test_api_plugins.py` | 17 | 1.1s |
| `test_api_trainer.py` | 11 | 2.1s |
| `test_api_backends.py` | 19 | 1.1s |
| `test_api_headswap.py` | 12 | 1.3s |

### 🐛 Fixed (pré-existentes)

- `is_public_path` em `auth.py` agora reconhece paths com prefixo `/api` (antes `/api/config` caía no path whitelist errado).
- `BearerAuthMiddleware` relê env var por request, não por startup, habilitando testes com `patch.dict(os.environ)`.
- Pydantic em `webhooks.py` e `trainer.py` usando `model_config = ConfigDict(extra="allow")` para tolerar novos campos upstream sem quebra.

### 📦 Housekeeping

- `facefusion/api/routes/` agora tem 11 sub-routers (was 5); cada um com `__init__.py` e guard admin consistente.
- `facefusion/api/database.py::init_db()` agora bootstraps **6 tabelas** (jobs + tenants + tenant_usage + webhook_deliveries + presets + job_metrics + train_jobs) de forma idempotente via `Base.metadata.create_all`.
- Novo `docs/DOCKER_PROFILES.md`, `docs/I18N.md`.
