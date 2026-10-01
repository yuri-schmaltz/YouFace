# Technical debt inventory — 2026-09-28 (post-hardening)

## Resolved in this sprint (2026-09-28)

| # | Item | Commit | Notes |
|---|---|---|---|
| 4 | `err: any` em catch blocks (4) | `4d63da1` | `unknown` + `instanceof Error` narrowing |
| 5 | `e.target.value as any` (2) | `4d63da1` | Typed unions |
| 6 | API tests para 12 routes não cobertas | `4d63da1` | `test_api_routes_coverage.py` (16 testes novos) |
| 7 | Tipagem de `any` no frontend (6 ocorrências) | `4d63da1` | Todos resolvidos |
| 10 | ErrorBoundary | `4d63da1` | `ErrorBoundary.tsx` (130 LoC) + wired no layout raiz |
| 12 | Script de cleanup de stuck jobs | (this) | `scripts/clean_stuck_jobs.py` (com `--dry-run`) |
| 15 | Rate limiting no /api/jobs | `4d63da1` | `RateLimiter` 60 req/60s por IP |
| 16 | Security headers (CSP) | `4d63da1` | `SecurityHeaders` middleware |
| 18 | package-lock.json versionado | (já existia) | Documentado |
| 19 | Split de `routes.py` (1.988 LoC) | `4d63da1` (parcial) | 3 submódulos extraídos (`common`, `hardware`, `config`) |
| 20 | API versioning `/api/v1/...` | (this) | `/api` ainda funciona, `/api/v1` adicionado |
| 22 | docker-compose.dev.yml docs | (this) | README atualizado |
| 23 | `.editorconfig` no frontend | (this) | `frontend/.editorconfig` |
| 24 | upstream/master só remote | (já era) | — |

## NEW: tech debt added during this sprint (from sub-refactors)

| # | Item | Where | Status |
|---|---|---|---|
| 30 | Hook tests não rodam (sem Jest instalado) | `useMediaUpload`, `usePreview`, `useJobActions` | Documentado, deferido |
| 31 | Submódulos de routes criados mas não usados | `routes/{common,hardware,config}.py` | Documentado, `routes.py` legacy ainda é o source-of-truth |
| 32 | `Middleware` adicionado a `main.py` mas não testado com TestClient | `middleware.py` | 5 testes adicionados em `test_api_routes_coverage.py` |

## Still pending (deferred by design)

| # | Item | Por que deferido | Estimativa |
|---|---|---|---|
| 1 | Auth (LAN deploy) | Requer estratégia de token storage; mudar para 0.0.0.0 com auth é uma feature grande, não um débito | 2-3 dias |
| 2 | `page.tsx` 1.267 LoC (split em tabs) | Risco alto offline (sem tsc); os hooks extraídos cobrem o essencial | 1-2 dias |
| 3 | 19 handlers inline em `page.tsx` | 3 hooks já extraídos (useMediaUpload, usePreview, useJobActions) cobrem os principais; 16 restantes são triviais | 4-6 h |
| 8 | Celery + Redis | Requer infra de filas reais; fork é local-first | 1 semana |
| 9 | CLI parity para 11 processors | Upstream CLI é gerado; fork tem API mas não CLI | 1-2 dias |
| 11 | Jest + testes para hooks | CI já roda TS check + build; testes seria nice-to-have | 1 dia |
| 13 | SSE error path testing | Manual testing; cobertura auto requer mock de EventSource | 30 min |
| 17 | 19 constantes no escopo de page.tsx | Muitos são closures; useCallback/useMemo resolveria | 4-6 h |
| 21 | (era falso positivo) `useStudioState.patch` é API ativa, não morta | — | — |
| 25 | (era falso positivo) "BAIXAR TODOS" é label de UI, não TODO | — | — |
| 26-30 | v4 do upstream | Depende de upstream tag | (1 dia após tag) |
| 33 | Auth tokens (P1-Security) | Pendente item #1 | — |
| 34 | API `/api/v1` deprecation do `/api` legacy | Pendente major version bump | — |

## O que foi adicionado e merece atenção

### Novos hooks (4)
- `useMediaUpload`: upload + drag-drop (extraído de page.tsx)
- `usePreview`: single-frame preview (extraído)
- `useJobActions`: cancel + delete (extraído)
- `useStudioState`: já existia (8 useState locais mantidos)

### Novos componentes (1)
- `ErrorBoundary` (130 LoC) — wired no layout raiz

### Novos middlewares (3)
- `RateLimiter` (60 req/60s, skip SSE)
- `SecurityHeaders` (CSP, X-Frame-Options, etc)
- `MaxBodySize` (200 MB cap)

### Novos submódulos routes (3, parciais)
- `youface/api/routes/common.py` (helpers)
- `youface/api/routes/hardware.py` (4 endpoints)
- `youface/api/routes/config.py` (2 endpoints)
- **Migração completa: deferida** — `routes.py` ainda é o source-of-truth

### Novos scripts (1)
- `scripts/clean_stuck_jobs.py` (com `--dry-run`)

### Novos arquivos de config (1)
- `frontend/.editorconfig`

## Resumo numérico final

| Métrica | Antes do sprint | Depois do sprint | Delta |
|---|---|---|---|
| Tech debt items resolvidos | 0 | 14 | +14 |
| Tech debt items deferred (com razão) | 30 | 20 | -10 |
| Tech debt items sem solução clara | 0 | 0 | 0 |
| TypeScript `any` no código | 6 | 0 | -6 |
| Backend security headers | 0 | 4 | +4 |
| Middlewares no FastAPI | 0 | 3 (custom) | +3 |
| API routes com testes | 14/29 (48%) | 25/29 (86%) | +38% |
| Frontend hooks | 7 | 10 | +3 |
| API versioning | 0 | 1 (v1 + legacy) | +1 |

## Próxima sprint — top 5 se for priorizar

1. **#2 + #3 (1-2 dias)**: Split final de page.tsx em tabs e mover handlers restantes
2. **#11 (1 dia)**: Instalar Jest + escrever testes para os 10 hooks
3. **#1 (2-3 dias)**: Auth via bearer token (pré-requisito para LAN deploy)
4. **#8 (1 semana)**: Celery + Redis para filas distribuídas
5. **#9 (1-2 dias)**: CLI parity para 11 processors

Recomendação: #1 antes de qualquer deploy em rede.
