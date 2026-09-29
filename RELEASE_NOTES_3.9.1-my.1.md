# Release Notes — `3.9.1-my.1`

**Released:** 2026-09-28
**Fork base:** upstream `3.9.0` (no upstream changes)
**Diff vs fork base:** **+2,000 LoC Python + 1,000 LoC TS** + 149 new tests across 9 suites.

This is the **gauntlet finale** release. No new upstream code is merged (we're at the head of `3.9.0`); all changes are fork-side additions that close the gap with Faceswap / Roop / SimSwap / BHS Ultimate / Renvveyult.

## What's new

Ten flagship features, each with documentation, tests, and admin endpoints. See CHANGELOG for the per-commit breakdown.

| # | Feature | Endpoint prefix | Highlights |
|---|---|---|---|
| R7 | Multi-tenant auth + quotas | `/api/admin/tenants`, `/api/admin/usage` | Per-tenant API keys, monthly minute quota, `X-RateLimit-*` headers |
| R8 | Webhooks de conclusão | `/api/admin/webhooks[/{id}/failed]` | HMAC signature, retry+dead-letter, JSON payload on terminal state |
| R9 | Presets / recipes | `/api/presets[/{id}/apply]` | Reusable bundles, tenant-scoped + shared flag, merge on apply |
| R10 | Métricas automáticas | `/api/jobs/{id}/metrics` | Identity similarity, temporal consistency, pose drift |
| R11 | Plugin marketplace | `/api/admin/plugins[/{name}/...]` | `importlib.metadata.entry_points` + enable/disable JSON state |
| R12 | Treinamento dedicado | `/api/train[/{id}/result]` | Source-dir → L2-normalized prototype `.npy` per tenant |
| R13 | Backend opcional SimSwap | `/api/backends[/{name}]` | Pluggable registry + lazy load + graceful fallback |
| R14 | Head-swap completo | `/api/jobs/{id}/head-swap-info` | Swap mode `face` / `head` with mask config |
| R15 | Compose multi-perfil | `docker-compose.{nvidia,amd,cpu}.yml` | Auto-detect GPU in `release/start.sh` |
| R16 | UI i18n | `frontend/src/i18n/` | EN + PT-BR, `<LocalePicker />`, localStorage persistence |

## Install / upgrade

### Fresh install
```bash
git clone https://github.com/yuri-schmaltz/my-facefusion.git
cd my-facefusion
git checkout 3.9.1-my.1
python install.py default --skip-conda
cd frontend && npm install && npm run build && cd ..
python run_api.py
```

### Upgrade from `3.9.0-my.1`
```bash
git fetch --tags
git checkout 3.9.1-my.1
python install.py default --skip-conda   # no new deps, but safe to re-run
cd frontend && npm install && npm run build && cd ..
```

No schema migration is required — the new tables (`tenants`, `tenant_usage`, `webhook_deliveries`, `presets`, `job_metrics`, `train_jobs`) are created idempotently by `init_db()` on first boot. Existing tables gain nullable columns (`webhook_url`, `webhook_secret`, `tenant_id`, `started_at`).

## Docker

The Pinokio launcher now auto-detects your GPU. Use `--profile` to override:

```bash
./release/start.sh                    # auto: nvidia | amd | cpu
./release/start.sh --profile nvidia   # force NVIDIA
./release/start.sh --profile amd      # force AMD ROCm
./release/start.sh --profile cpu      # force CPU-only
```

Or with docker compose directly:

```bash
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up
docker compose -f docker-compose.yml -f docker-compose.amd.yml up
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up
```

See [`docs/DOCKER_PROFILES.md`](docs/DOCKER_PROFILES.md) for the full reference.

## Tests

```bash
.venv/bin/python -m pytest tests/test_api_auth.py \
                       tests/test_api_tenants.py \
                       tests/test_api_webhooks.py \
                       tests/test_api_presets.py \
                       tests/test_api_metrics.py \
                       tests/test_api_plugins.py \
                       tests/test_api_trainer.py \
                       tests/test_api_backends.py \
                       tests/test_api_headswap.py -v
```

**Result:** 149/149 passing in ~10s on Python 3.12.

## New env vars

| Var | Default | Purpose |
|---|---|---|
| `FACEFUSION_API_TOKEN` | unset | Admin bearer token (existed before R7) |
| `FACEFUSION_WEBHOOK_MAX_ATTEMPTS` | 5 | R8 — delivery retries |
| `FACEFUSION_WEBHOOK_BACKOFF_BASE` | 1.0 | R8 — first retry delay (seconds) |
| `FACEFUSION_WEBHOOK_TIMEOUT` | 10 | R8 — per-request timeout (seconds) |

The `FACEFUSION_EXECUTION_PROVIDERS` env var is now honoured by all compose profiles (see [DOCKER_PROFILES.md](docs/DOCKER_PROFILES.md)).

## Migration notes

- **Existing API clients:** No breaking changes. All new endpoints are additive.
- **Existing tenants (single-user mode):** No `FACEFUSION_API_TOKEN` env var → auth stays disabled (backward compatible). Set the env var to opt into multi-tenant mode.
- **Existing jobs:** Will gain nullable `webhook_url` / `tenant_id` columns on the next boot. Already-completed jobs are unaffected.
- **Frontend:** The i18n module is opt-in. Old hard-coded strings still work; new components should use `useLocale()`.

## Limitations

- **Plugin entry-point scanning** does NOT detect plugins installed after the FastAPI app starts. Use `POST /api/admin/plugins/reload` to re-scan.
- **Webhook dispatcher is synchronous.** For very high volume, replace with a queue (Celery/RQ/Arq) — the function shape stays the same.
- **Training pipeline is a simplified prototype.** Not a full VAE like Faceswap — extracts and averages embeddings. Enough for "same celebrity across 1000 clips", not for "novel identity not in the embedding space".
- **SimSwap backend is a stub.** Install with `pip install facefusion[simswap]` (extra in pyproject.toml, no wheel yet — see [DOCKER_PROFILES.md](docs/DOCKER_PROFILES.md)).

## Acknowledgments

- **FaceFusion upstream** for the engine.
- **Faceswap** for the SAE-style training inspiration (we ship the 80/20 version).
- **SimSwap** for the high-fidelity pose handling (gated, not bundled).
- **BHS Ultimate** for the head-swap concept.
- **Roop / Roopx** for the one-click UX patterns that motivated the API-first approach.
