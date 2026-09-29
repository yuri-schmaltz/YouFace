# Docker deployment profiles (R15 of gauntlet)

YouFace ships with **three compose profiles** that operators stack on
top of the base `docker-compose.yml` to pick the right acceleration
backend for their hardware.

## Quick start

```bash
# NVIDIA GPU
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up

# AMD GPU
docker compose -f docker-compose.yml -f docker-compose.amd.yml up

# CPU only
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up
```

The Pinokio launcher (`release/start.sh`) auto-detects and picks the
right profile if you don't pass `--profile`.

## What each file does

| File | Overrides | Why |
|------|-----------|-----|
| `docker-compose.nvidia.yml` | Adds `nvidia` device reservation, sets `FACEFUSION_EXECUTION_PROVIDERS=cuda` | Lets the backend see all NVIDIA GPUs |
| `docker-compose.amd.yml` | Adds `/dev/kfd`, `/dev/dri` device passthrough, sets `HSA_OVERRIDE_GFX_VERSION` and `rocm` provider | ROCm support in onnxruntime |
| `docker-compose.cpu.yml` | Caps CPU+memory usage, forces `cpu` execution provider | Works on any host, no GPU drivers required |

## Environment variables honoured by the backend

| Var | Default | Used by |
|-----|---------|---------|
| `FACEFUSION_EXECUTION_PROVIDERS` | auto-detected at startup | All profiles |
| `FACEFUSION_EXECUTION_THREAD_COUNT` | unset (= all cores) | CPU profile |
| `FACEFUSION_API_TOKEN` | unset | Bearer auth for `/api/admin/*` |
| `FACEFUSION_WEBHOOK_MAX_ATTEMPTS` | 5 | Webhook delivery |
| `FACEFUSION_WEBHOOK_BACKOFF_BASE` | 1.0 | Webhook delivery |
| `FACEFUSION_WEBHOOK_TIMEOUT` | 10 | Webhook delivery |

## Choosing the right onnxruntime flavor

The base Dockerfile installs `onnxruntime` (CPU). For GPU, you need:

- **NVIDIA CUDA 12.x** — `onnxruntime-gpu` (pulls CUDA 12 deps; the
  base image already provides the CUDA runtime; the onnxruntime
  package doesn't include the CUDA runtime itself).
- **NVIDIA CUDA 13.x** — install via `pip install onnxruntime-gpu-cu13`
  (when available) or build from source.
- **AMD ROCm** — `onnxruntime-rocm` (currently only on Linux).
- **Apple Silicon** — `onnxruntime-silicon` or build from source;
  Apple GPUs are also accessible via CoreML.

`facefusion/installer.py` selects the right flavor at install time
based on the host GPU. Re-run `python install.py` after switching
profiles if the wheels don't match.

## Troubleshooting

- **`docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]]`**
  Install the NVIDIA Container Toolkit: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html>

- **`/dev/kfd: no such file or directory`**
  ROCm isn't loaded. Check `lsmod | grep amdgpu`.

- **All jobs fail with "CUDAExecutionProvider not available"**
  The onnxruntime wheel doesn't match the host CUDA. Check
  `pip show onnxruntime` and reinstall the matching flavor.
