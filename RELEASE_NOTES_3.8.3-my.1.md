# Release Notes — `3.8.3-my.1`

**Released:** 2026-09-28
**Fork base:** upstream `3.8.3` (commit `435521d`)
**Diff vs fork base:** ~90 commits, 90+ files (run
`git diff --stat 435521d..3.8.3-my.1` for the precise count)

---

## What you get

This is the **first release of this fork synchronized with upstream 3.8.x**.
It bundles 12 commits of upstream (3.7.0..3.8.3) on top of the fork's
78 own commits over the original 3.6.1 base.

The merge was almost entirely automatic — only 2 conflicts in `metadata.py`
and `requirements.txt`, both resolved in favor of the fork. Notably, the
fork's `workflows/*` module was already 90% aligned with upstream 3.7.0+,
because the fork's original authors had absorbed that design when building
the FastAPI/CLI split.

### Headline changes from upstream 3.6.1 → 3.8.3

- **Memory leak hotfix (3.8.0).** Long-running sessions no longer accumulate
  frames in memory. Critical for batch processing.
- **Streamer / temp_helper refactor.** Internal cleanup with no API impact.
- **`video_manager.py` expanded** (+151 LoC upstream). Better seeking,
  frame-accurate trims, larger file support.
- **`types.py` expanded** (+112 LoC upstream). New `ErrorCode`, `Resolution`,
  `VisionFrame` types — fork's `routes.py` already uses them.
- **`workflows/*` aligned.** Upstream's `to_image.py` / `to_video.py` and
  `core.py` are now canonical; fork's `image_to_image.py` /
  `image_to_video.py` entrypoints are preserved as the CLI surface.
- **Gradio UI refactor (upstream).** Fork doesn't use Gradio, so this passed
  through cleanly. Web cockpit (`frontend/`) is unaffected.

### Headline changes from this fork (vs upstream 3.8.3)

1. **Decoupled Next.js 16 web cockpit** in `frontend/`
2. **FastAPI backend** in `facefusion/api/`
3. **Multi-source face selection** with granular target-face mapping
4. **Real-time job progress** (SSE + polling fallback)
5. **Single-frame preview** (auto + manual)
6. **Atomic JSON writes** + XDG-compliant paths
7. **PII sanitization** in the diagnostic export
8. **Dynamic port discovery** + relative API URL (LAN / reverse-proxy ready)
9. **Custom dark-mode design system** with glassmorphism, toasts, and a
   slide-comparator video player
10. **`useStudioState` hook** (P1-1 step 1): isolated 78 `useState` of the
    Studio into a typed, serializable, preset-friendly state structure.
    Migration of `page.tsx` to consume it is a separate follow-up PR.

For the per-commit breakdown see [`CHANGELOG.md`](CHANGELOG.md).

---

## How to install / upgrade

### Fresh install
```bash
git clone https://github.com/yuri-schmaltz/my-facefusion.git
cd my-facefusion
git checkout 3.8.3-my.1
python install.py default --skip-conda
cd frontend && npm install && npm run build && cd ..
python run_api.py
```

### Upgrading from `3.7.0-my.1`
```bash
git fetch --tags
git checkout 3.8.3-my.1
python install.py default --skip-conda   # picks up new deps (psutil, httpx, etc.)
cd frontend && npm install && npm run build && cd ..
```

> If you were running the legacy CLI only, no frontend rebuild is required —
> `python facefusion.py …` still works exactly as before.

### Upgrading the dependencies
`requirements.txt` is now a documented mirror of `pyproject.toml` and honors
the `installer.py` semantics: the onnxruntime flavor is **not** pinned in
either file — it's decided by the install command:
```bash
python install.py default          # CPU: onnxruntime 1.28.0
python install.py cuda@12          # GPU: onnxruntime-gpu 1.24.4
python install.py openvino         # OpenVINO: 1.24.1
python install.py rocm             # ROCm: 1.22.2.post3 (Linux only)
```

---

## Known limitations

- **Behind upstream 3.9.0.** One commit pending: "load voice extractor on
  every processor". Trivial to absorb.
- **No automatic migration of `page.tsx`.** The `useStudioState` hook is
  ready but `page.tsx` still uses the original 78 `useState` inline. The
  TypeScript build is green (validated by CI), but the file is 1.229 lines.
  Migration to be done in a dedicated PR.
- **Linux/macOS focus.** Windows is supported by upstream but is not the
  primary development platform for this fork.
- **No multi-user / no auth.** The API binds to `127.0.0.1` only and has
  no authentication. Do not expose it to the network without a reverse
  proxy that adds auth.

---

## Credits

- Upstream engine: [facefusion/facefusion](https://github.com/facefusion/facefusion) @ `3.8.3` (`435521d`)
- Fork maintainer: [@yuri-schmaltz](https://github.com/yuri-schmaltz)
