# Release Notes — `3.9.0-my.1`

**Released:** 2026-09-28
**Fork base:** upstream `3.9.0` (commit `6b318a9`)
**Diff vs fork base:** ~93 commits, 95+ files (run
`git diff --stat 6b318a9..3.9.0-my.1` for the precise count)

---

## What you get

The third and latest tagged release of this fork. Built on top of
`3.8.3-my.1`, this release adds a 1-commit absorption of upstream
3.9.0 (the voice-extractor integration in face swapper) plus a series
of follow-up quality improvements that came from running the live
backend on real hardware (RTX 3060, driver 595, CUDA 13.2).

### Headline changes from `3.8.3-my.1`

1. **`useJobs` SSE hardening.** Added `connectionMode` state exposed to
   the UI (now shows "Jobs: SSE" / "Polling" / "Conectando…" / "Offline"
   badge in the status bar), 30s inactivity timeout that catches zombie
   SSE connections, immediate `fetchJobs()` on mount so the UI is never
   empty, and Visibility API integration that pauses polling when the
   tab is hidden (saves CPU/battery).
2. **Connection mode UI indicator.** New `ConnectionModeBadge`
   component renders the SSE/polling state with color coding (green for
   SSE, amber for polling, red for offline).
3. **Additional unit tests.** 14 new tests covering the LFI mitigation
   (`validate_safe_path`) and the age-based media cleanup. All run in
   0.4s with no transitive deps.
4. **Backend smoke-tested on real hardware.** Verified 23/23 module
   imports, 9/9 endpoints return 200, GPU detection (RTX 3060 12GB,
   driver 595.84, CUDA 13.2), and SSE keep-alive. See
   `notes/smoke_2026-09-28.md` for the full report.
5. **Decomposition step 2-3 of `page.tsx`.** Extracted `useConfig` (6
   system-config fields + save/refresh actions) and `useWizard` (modal
   state for video diagnostic wizard). `page.tsx` now has only 8
   useState — down from 78 at the start of the sprint.

### Headline changes from upstream 3.9.0 (the merge)

- **`facefusion/face_landmarker.py` expanded (+84 LoC).** Adds voice
  extractor integration support.
- **Voice extractor loaded in face swapper processor.** The
  `facefusion/processors/modules/face_swapper/core.py` now loads the
  voice extractor module alongside the face swapper model.
- **Types/touch-ups.** `facefusion/types.py` and a few other modules
  got small type adjustments to accommodate the new integration.

For the per-commit breakdown see [`CHANGELOG.md`](CHANGELOG.md).

---

## How to install / upgrade

### Fresh install
```bash
git clone https://github.com/yuri-schmaltz/my-facefusion.git
cd my-facefusion
git checkout 3.9.0-my.1
python install.py default --skip-conda
cd frontend && npm install && npm run build && cd ..
python run_api.py
```

### Upgrading from `3.8.3-my.1`
```bash
git fetch --tags
git checkout 3.9.0-my.1
# No new Python deps; install.py not required
cd frontend && npm install && npm run build && cd ..
```

> If you were running the legacy CLI only, no rebuild is required —
> `python facefusion.py …` still works exactly as before.

---

## Known limitations

- **Upstream master has no new tags** since 3.9.0. The next absorption
  will be when upstream cuts a 3.10.0 (or v4.0).
- **`page.tsx` still has 1.265 lines.** The state decomposition
  (78 → 8 useState) is done, but the JSX tree is still monolithic. A
  follow-up PR can split it into `<StudioTab>`, `<ProjectsTab>`,
  `<JobsTab>`, and `<SettingsTab>` components.
- **No multi-user / no auth.** The API binds to `127.0.0.1` only. For
  LAN/reverse-proxy exposure, see the security warning in the README.
- **Linux/macOS focus.** Windows is supported by upstream but is not
  the primary development platform for this fork.

---

## Credits

- Upstream engine: [facefusion/facefusion](https://github.com/facefusion/facefusion) @ `3.9.0` (`6b318a9`)
- Fork maintainer: [@yuri-schmaltz](https://github.com/yuri-schmaltz)
