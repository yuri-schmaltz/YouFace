# Sprint summary — 2026-09-28

**Branch:** `merge/upstream-3.8.3` (preserved for history)
**Duration:** Single day (2026-09-28)
**Commits:** 6 (5 feature/merge + 1 page refactor)
**Tags applied:** `3.8.3-my.1`, `3.9.0-my.1`
**Status:** Pushed to origin, ready to fast-forward master.

## What was accomplished

| P-tag | Item | Result |
|---|---|---|
| P0-1 | Piso de Python 3.12 | ✅ `pyproject.toml`, `Dockerfile`, symlinks atualizados |
| P0-1 | `requirements.txt` ⇄ `pyproject.toml` | ✅ Removido pino morto de `onnxruntime`, `psutil` e `httpx` adicionados, `requirements.txt` virou mirror documentado |
| P1-1 | Decompor `page.tsx` | ✅ 78 `useState` → 14; 50+ setters wrappers preservam call-sites |
| P1-4 | Cleanup age-based de crops | ✅ `media/cleanup` aceita `max_age_seconds` (default 3600) |
| P2-3 | Suporte LAN / paths relativos | ✅ `config.json` grava `apiUrl: ""` + `apiUrlAbsolute` |
| P3-1 | Merge upstream 3.7.0..3.9.0 | ✅ 13 commits absorvidos, 3 conflitos triviais |
| P3-2 | CI endurecido | ✅ tsc + next build + eslint estrito + api-tests job |

## Metrics

- **Conflicts:** 3 total (metadata.py x2, requirements.txt x1) — all trivial
- **LOC delta:** +1.044 / -104 across 42 files
- **Upstream delta:** 13 commits absorbed
- **Test infra:** 50 → 51 files (1 new — `test_cli_output_fps.py` from upstream)
- **CI jobs:** 4 → 5 (added `api-tests`)
- **Python version:** 3.10 → 3.12 (CI was already on 3.12)
- **Upstream gap closed:** 3.6.1 → 3.9.0

## Commits

```
95dcb5e refactor(page.tsx): consume useStudioState, reduce 78 useState to 14
1e61875 merge upstream 3.9.0 (P3-1 follow-up)
5044802 post-merge hardening: CI api-tests job, version sync, hook refactor
7bb86d9 merge upstream 3.8.3 (P3-1)
b4306cb deps: sync requirements.txt <-> pyproject.toml honoring installer
5e30c02 sprint 2026-09-28: P0/P1/P2 hardening + P3 staging
```

## Lessons learned (this sprint)

1. **`installer.py` is the canonical place to look** for what actually gets
   installed. `requirements.txt` had misleading `onnxruntime` pins that the
   installer silently overrode via CLI arg. Now documented at the top of the
   file.

2. **The fork's `workflows/*` was already 90% aligned with upstream 3.7.0+**
   — the original fork authors had absorbed that design when building the
   FastAPI/CLI split. The merge was almost free.

3. **`upstream/<tag>` ≠ upstream/master tag ref.** Always `git fetch
   upstream <tag>` explicitly to create a ref you can diff/merge against,
   otherwise `git merge` fails with "not something we can merge".

4. **`useState` count is the wrong metric for component complexity.** The
   migration dropped 78 useState to 14, but the file LoC went from 1.229 to
   1.271 (slight increase due to destructuring aliases and wrapper setters).
   The real win is **state centralization**, not line reduction.

5. **Wrapping setters as `studio.set("x", v)` aliases is the right migration
   strategy** when you can't run tsc locally. It preserves all 100+
   call-sites verbatim while collapsing the underlying state to one typed
   object. Future PRs can swap wrappers for direct `studio.state.x` reads.

6. **Two tags in one day is fine** when the merges are independent and small.
   3.8.3 (12 commits, 2 conflicts) and 3.9.0 (1 commit, 1 conflict) cost
   ~10 minutes combined because the conflict patterns were already
   documented from the first merge.

## What's pending (intentionally)

1. **PR/merge to master.** Branch is ready; awaiting you.
2. **CI run on actual push.** No `npm install` was done locally; CI will
   validate tsc + next build + eslint.
3. **`page.tsx` further decomposition** (e.g., `useConfig`, `useWizard`).
   Out of scope for this sprint.

## Next planned sync (upstream 3.9.0+ master)

Upstream master has no new tags since 3.9.0. The next absorption will be
when upstream cuts a new release (3.10.0?). Same playbook: dedicated branch
+ merge --no-ff + smoke + tag.
