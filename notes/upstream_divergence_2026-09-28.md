# Upstream divergence snapshot — 2026-09-28

**Branch:** `merge/upstream-3.8.3`
**Status:** preparat\u00f3ria (sem merge aplicado). Aguarda decis\u00e3o de estrat\u00e9gia.

## Upstream releases merged

| Tag | Merged? | Notas |
|---|---|---|
| 3.6.0 | ✅ `57fcb86` | antes da base do fork |
| 3.6.1 | ✅ `5b7d145` | **fork base** |
| 3.7.0 | ❌ | pendente |
| 3.7.1 | ❌ | pendente |
| 3.8.0 | ❌ | hotfix memory leak (`2dd10e0`) |
| 3.8.1 | ❌ | |
| 3.8.2 | ❌ | |
| 3.8.3 | ❌ | |
| 3.9.0 | ❌ | ("load voice extractor on every processor") |

**Alerta de atualiza\u00e7\u00e3o:** o `CHANGELOG.md` e o `RELEASE_NOTES_3.7.0-my.1.md` dizem
"behind upstream 3.7.0 and 3.7.1". **Est\u00e1 desatualizado** — upstream lan\u00e7ou
3.8.x e 3.9.0 desde a \u00faltima sincroniza\u00e7\u00e3o.

## Diff upstream 3.7.1..master — escopo

```
8 commits total
facefusion/choices.py: +6/-? (additions em processors)
facefusion/processors/modules/* : +91/-65 (ajustes em todos os 11 processors)
```

**\u00c1reas tocadas (provavelmente sem conflito):**
- `facefusion/choices.py` — apenas adicionar entries; o fork mant\u00e9m o pre-check
- `facefusion/processors/modules/*/core.py` — refactor uniforme (~7 linhas cada);
  provavelmente n\u00e3o colide com o fork porque o fork n\u00e3o tocou esses arquivos

**\u00c1reas provavelmente livres de conflito:**
- `facefusion/state_manager.py` — fork j\u00e1 adicionou `_STATE_LOCK`; upstream n\u00e3o tocou
- `facefusion/jobs/` — fork reestruturou em `facefusion/api/jobs/` + workflows
- `facefusion/workflows/` — fork-only

## Pr\u00f3ximos passos sugeridos

1. **Decidir estrat\u00e9gia:** merge, rebase ou cherry-pick?
   - **Merge ff-only** se upstream master \u00e9 descendente direto do `5b7d145`? **N\u00c3O** — diverg\u00eancia real.
   - **Merge --no-ff** com resolu\u00e7\u00e3o manual \u00e9 a abordagem documentada no `UPSTREAM_MERGE.md`.
2. **Smoke test** ap\u00f3s cada commit upstream: `python facefusion.py job-list && pytest tests/`.
3. **Tag nova:** `3.8.3-my.1` (fork base 3.8.3) ou `3.7.1-my.1` (conservador, apenas 3.7.1).
4. **Atualizar `CHANGELOG.md` e `RELEASE_NOTES_3.7.0-my.1.md`** — marcar 3.8.x como ainda
   n\u00e3o merged e listar 3.9.0 tamb\u00e9m.

## Estado da branch

```
merge/upstream-3.8.3 (this branch)
├── 77 commits a frente do upstream/master (fork features)
├── 8 commits atr\u00e1s do upstream/master (pending merge)
└── working tree cont\u00eam altera\u00e7\u00f5es deste sprint (CI/P2-3/P1-4/...)
```

Nenhum conflito foi resolvido ainda. **N\u00e3o fa\u00e7a merge automaticamente** — requer revis\u00e3o humana.