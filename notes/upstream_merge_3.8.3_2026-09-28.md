# Upstream merge report — `3.8.3-my.1` — 2026-09-28

**Branch:** `merge/upstream-3.8.3` (preserved for history)
**Merge commit:** `7bb86d9`
**Tag:** `3.8.3-my.1`

## What was merged

| Upstream release | Commit | Notes |
|---|---|---|
| 3.7.0 | `a2cbfd7` | first 3.7 release |
| 3.7.1 | `3f81a8a` | patch 3.7.1 |
| 3.8.0 | `b60ea40` | + `2dd10e0` memory leak hotfix |
| 3.8.1 | `6f5e4b9` | |
| 3.8.2 | (part of 3.8.1 chain) | |
| 3.8.3 | `4b1dedb` + `435521d` | fork base |
| 3.9.0 | `358f169` + `6b318a9` | **NOT MERGED** (1 commit) |

## Conflicts encountered

Only 2 manual conflicts out of 79 changed files:

| File | Fork side | Resolution |
|---|---|---|
| `youface/metadata.py` | `'version': '3.8.2-my.1'` | Bumped to `'3.8.3-my.1'` (fork identity preserved) |
| `requirements.txt` | Poetry-pinned | Fork wins (Poetry is the source of truth; installer overrides onnxruntime anyway) |

The remaining 77 files merged automatically. Notable points:

- **`youface/workflows/core.py`**: upstream version (canonical). The
  fork's pre-existing version was 90% identical; differences were in
  `conditional_get_target_vision_frames` (upstream adds `detect_video_fps`,
  `resolve_extract_frame_number`, `resolve_target_frame_number` plumbing).
  These functions also exist in upstream's `youface/vision.py`, which
  merged cleanly.

- **`youface/vision.py`**, **`youface/video_manager.py`**,
  **`youface/types.py`**: significant upstream expansion (+82, +151, +112
  LoC respectively). All additive; no fork code removed.

- **`youface/uis/*`**: upstream refactored the Gradio UI. Fork doesn't
  use Gradio (web cockpit replaces it), so changes passed through cleanly.

- **`youface/installer.py`**: minor update; still respects the CLI-arg
  flavor selection. No conflict with fork.

- **`youface/processors/modules/*`**: small refactors upstream; fork
  doesn't touch these files. Merged cleanly.

## Smoke test results

- All modified Python files parse cleanly (`ast.parse` ✓).
- `youface.metadata` reports `3.8.3-my.1` (✓).
- Pure-Python modules (`common_helper`, `installer`, `hash_helper`, `metadata`)
  import without errors in clean venv.
- Modules requiring `cv2` / `numpy` / `onnxruntime` need full install (CI will
  validate end-to-end).

## Validation pending

- [ ] `pytest tests/` in clean venv (needs full Poetry install)
- [ ] `python youface.py job-list` (CLI smoke)
- [ ] `python run_api.py` + `curl http://127.0.0.1:8000/api/hardware/devices`
- [ ] CI green: lint + frontend-check + test + api-tests

## Next planned merge

**Upstream 3.9.0** — single commit `358f169 load voice extractor on every
processor`. Trivial absorption expected (no fork code touches voice
extractor integration). Plan:

```bash
git checkout merge/upstream-3.9.0
git merge --no-ff upstream-3.9.0 -m "merge upstream 3.9.0"
# expected: 0 conflicts
pytest tests/test_audio.py
git tag -a 3.9.0-my.1
```

## Lessons learned

1. **Fork's `workflows/*` was already 90% aligned with upstream 3.7.0+** —
   the original fork authors had absorbed that design when building the
   FastAPI/CLI split. The merge was almost free.

2. **`installer.py` is the canonical place to look** when figuring out
   what actually gets installed. `requirements.txt` and `pyproject.toml`
   both had misleading `onnxruntime` pins that the installer silently
   overrode. The `requirements.txt` rewrite documents this.

3. **The 78-`useState` `page.tsx` is a real risk** for the next frontend
   refactor. The `useStudioState` hook is now ready, but a mechanical
   migration of that file must run with `tsc` available — not blindly.

4. **`upstream/master` ≠ `upstream/<latest_tag>`.** Always `git fetch
   upstream <tag>` explicitly to get a ref you can diff against, otherwise
   `git merge` fails with "not something we can merge".
