# Upstream v4 strategy — 2026-09-28

**Current state:** fork on `3.9.0-my.1` (master, tag applied).
**Upstream status:** no new tags since `3.9.0`. Active development on `v4`
branch (websocket store, session teardown, upload restrictions, token refresh).

## What's in upstream v4 (pre-tag)

From `git log 3.9.0..upstream/v4`:

- `c5392f0` — expose refresh token only on CREATE and UPDATE
- `d04fe62` — introduce websocket store, to kill open connections on session destroy
- `e59dff8` — observe cli session in order to teardown when api session is dead
- `667a037` — work on upload restrictions
- `48b35bb` — work on upload restrictions

These are substantial changes. The websocket store and session teardown
will require **significant changes** to the fork's FastAPI/worker layer.

## Recommended absorption strategy

When upstream cuts the v4 tag, follow this playbook:

### Pre-merge (now)

1. [ ] Review `notes/smoke_2026-09-28.md` for current baseline
2. [ ] Ensure all CI jobs are green on `master`
3. [ ] Review CHANGELOG.md for any pending migration notes

### Merge phase

```bash
# 1. Branch from current master (don't rebase to avoid losing history)
git checkout master
git pull --ff-only
git checkout -b merge/upstream-v4

# 2. Merge the v4 tag
git fetch upstream
git tag upstream-v4 v4-tag-sha
git merge --no-ff upstream-v4 -m "merge upstream v4 (P3-1)"

# 3. Expected high-conflict zones
#    - facefusion/api/ — upstream introduces websocket store, our fork
#      already has SSE in useJobs. Decide: keep both? wire them together?
#    - facefusion/jobs/ — upstream may restructure; fork has api/jobs/
#    - facefusion/upload — upstream adds restrictions; fork has open
#      uploads in /api/media/upload
```

### Conflict resolution order

1. `facefusion/installer.py` — accept upstream (CLI tool)
2. `facefusion/processors/modules/*` — accept upstream
3. `facefusion/api/*` — **manual resolution required**. Decide:
   - Keep our SSE + useJobs, or migrate to upstream's websocket store?
   - Keep our atomic JSON writes, or switch to upstream's new pattern?
4. `facefusion/api/routes.py` — merge carefully; the new upload
   restrictions will need to be configured for the fork's use case
5. `requirements.txt` — keep fork (Poetry is source of truth)
6. `pyproject.toml` — keep fork (Poetry is source of truth)
7. `facefusion/metadata.py` — fork wins, bump version

### Post-merge

```bash
# Smoke
python -m pytest tests/test_path_validation.py tests/test_media_cleanup.py -v
python run_api.py &  # check boots OK
curl http://127.0.0.1:8000/api/hardware/devices

# Test
pytest tests/test_api_*.py

# Tag
git tag -a 4.0.0-my.1 -m "..."
git push origin merge/upstream-v4 4.0.0-my.1

# PR/merge to master
git checkout master
git merge --ff-only merge/upstream-v4
git push origin master
```

## Open questions for v4

1. **WebSocket vs SSE.** Upstream v4 introduces a websocket store; our
   fork already has SSE for jobs streaming. Decision needed:
   - **Replace SSE with WebSocket:** more flexible, supports bidi
   - **Keep both:** SSE for jobs, WebSocket for upload progress
   - **Use only WebSocket:** simpler, single transport

2. **Session management.** Upstream adds CLI session observation +
   teardown. Our fork's CLI (facefusion.py) doesn't have sessions
   yet — easy adoption. Our FastAPI worker has job lifecycle, but
   no user sessions. **Impact: low.**

3. **Upload restrictions.** Upstream is working on this; will likely
   require configuration via `facefusion.ini` plus a new env var for
   the fork. **Impact: medium** — may break the open `/api/media/upload`
   endpoint.

4. **Refresh tokens.** Upstream exposes them only on CREATE/UPDATE.
   Our fork has no auth at all. **Impact: zero** (defer to a later
   sprint; v4 doesn't force adoption).

## Timeline estimate

- Pre-merge prep: 1 hour
- v4 merge attempt: 2-4 hours (high conflict surface)
- Conflict resolution: 2-4 hours
- Smoke + tag: 1 hour
- **Total: 1 working day**

Re-evaluate when upstream actually tags v4.
