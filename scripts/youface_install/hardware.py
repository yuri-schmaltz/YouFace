"""
Detecção de hardware / runtime para o instalador inteligente.

Identifica GPU, driver NVIDIA, versão CUDA disponível, versão CUDA do
torch (se instalado), plataforma e arquitetura. Não chama subprocess
externos pesados — apenas shutil.which + queries pequenas via nvidia-smi
quando disponível.

Este módulo é **read-only** e seguro para rodar em qualquer contexto
(inclusive CI sem GPU).
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class HardwareProfile:
    """Snapshot completo do ambiente de execução."""

    platform: str = ""            # "linux" | "windows" | "darwin"
    arch: str = ""                # "x86_64" | "arm64" | ...
    python_version: str = ""      # "3.12.3"
    has_nvidia_smi: bool = False
    gpu_names: list[str] = field(default_factory=list)
    nvidia_driver_version: str = ""
    cuda_runtime_version: str = ""  # via nvidia-smi (driver-reported)
    nvcc_version: str = ""          # via nvcc (toolkit, se houver)
    torch_installed: bool = False
    torch_version: str = ""
    torch_cuda_version: str = ""    # torch.version.cuda
    torch_cuda_available: bool = False
    torch_device_count: int = 0
    onnxruntime_installed: bool = False
    onnxruntime_version: str = ""
    onnxruntime_providers: list[str] = field(default_factory=list)
    free_disk_gb: float = 0.0

    def summary_lines(self) -> list[str]:
        """Linhas de texto para --info (uma por linha, prefixo padronizado)."""
        lines = []
        lines.append(f"platform      : {self.platform} ({self.arch})")
        lines.append(f"python        : {self.python_version}")
        if self.gpu_names:
            for i, name in enumerate(self.gpu_names):
                lines.append(f"gpu[{i}]         : {name}")
        else:
            lines.append("gpu            : (none detected)")
        if self.has_nvidia_smi:
            lines.append(f"driver        : NVIDIA {self.nvidia_driver_version or '(unknown)'}")
            if self.cuda_runtime_version:
                lines.append(f"cuda (driver) : {self.cuda_runtime_version}")
            if self.nvcc_version:
                lines.append(f"nvcc          : {self.nvcc_version}")
        else:
            lines.append("nvidia-smi     : not available")
        if self.torch_installed:
            lines.append(f"torch         : {self.torch_version} (cuda: {self.torch_cuda_version or 'cpu'})")
            lines.append(f"torch.cuda    : available={self.torch_cuda_available} devices={self.torch_device_count}")
        else:
            lines.append("torch         : not installed")
        if self.onnxruntime_installed:
            lines.append(f"onnxruntime   : {self.onnxruntime_version}")
            lines.append(f"  providers   : {', '.join(self.onnxruntime_providers) or '(none)'}")
        else:
            lines.append("onnxruntime   : not installed")
        lines.append(f"disk free     : {self.free_disk_gb:.1f} GB")
        return lines


def _run(cmd: list[str], timeout: float = 5.0) -> str | None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            check=False, env={**os.environ, "LANG": "C"},
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _parse_nvidia_smi_csv(raw: str) -> tuple[list[str], str, str]:
    """Parse a saída de nvidia-smi em formato CSV.

    Aceita tanto o formato com header ('name, driver_version') quanto o
    sem header ('NVIDIA GeForce RTX 3060, 595.84'). Drivers NVIDIA 595+
    removeram a flag 'noheader', então temos que lidar com as duas formas.

    Returns (gpu_names, driver_version, empty_cuda_runtime_fallback).
    """
    names: list[str] = []
    driver = ""
    if not raw:
        return names, driver, ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip header (drivers antigos)
        if line.lower().startswith("name") and "driver" in line.lower():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 1 and parts[0]:
            names.append(parts[0])
        if len(parts) >= 2 and not driver:
            driver = parts[1]
    return names, driver, ""


def _parse_cuda_runtime(raw: str) -> str:
    """Parse 'nvidia-smi --query-gpu=cuda_runtime_version --format=csv'."""
    if not raw:
        return ""
    # Formato: "13.0" — pegamos a primeira linha não-vazia
    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit():
            return line
    return ""


def _parse_nvcc_version(raw: str) -> str:
    """Parse 'nvcc --version' — extrai 'release X.Y'."""
    if not raw:
        return ""
    m = re.search(r"release\s+(\d+\.\d+)", raw)
    return m.group(1) if m else ""


def detect() -> HardwareProfile:
    """Roda todos os detectores e devolve um snapshot consolidado."""
    profile = HardwareProfile()
    profile.platform = platform.system().lower()
    profile.arch = platform.machine().lower()
    profile.python_version = platform.python_version()

    # nvidia-smi. Drivers 595+ rejeitam a flag 'noheader' (issue NVIDIA R555+),
    # então usamos --format=csv simples e deixamos o parser tratar o header.
    if shutil.which("nvidia-smi") is not None:
        profile.has_nvidia_smi = True
        smi_csv = _run(["nvidia-smi", "--query-gpu=name,driver_version",
                         "--format=csv"])
        if smi_csv:
            names, driver, _ = _parse_nvidia_smi_csv(smi_csv)
            profile.gpu_names = names
            profile.nvidia_driver_version = driver
        cuda_runtime_csv = _run(["nvidia-smi",
                                 "--query-gpu=cuda_runtime_version",
                                 "--format=csv"])
        if cuda_runtime_csv:
            profile.cuda_runtime_version = _parse_cuda_runtime(cuda_runtime_csv)

    # nvcc (opcional)
    nvcc_out = _run(["nvcc", "--version"])
    if nvcc_out:
        profile.nvcc_version = _parse_nvcc_version(nvcc_out)

    # torch (opcional, não importa — só inspeciona)
    try:
        import torch  # type: ignore
        profile.torch_installed = True
        profile.torch_version = torch.__version__
        profile.torch_cuda_version = getattr(torch.version, "cuda", "") or ""
        try:
            profile.torch_cuda_available = bool(torch.cuda.is_available())
            profile.torch_device_count = (
                torch.cuda.device_count() if profile.torch_cuda_available else 0
            )
        except Exception:  # noqa: BLE001 — torch pode estar parcialmente quebrado
            profile.torch_cuda_available = False
            profile.torch_device_count = 0
    except ImportError:
        pass

    # onnxruntime (opcional)
    try:
        import onnxruntime  # type: ignore
        profile.onnxruntime_installed = True
        profile.onnxruntime_version = onnxruntime.__version__
        try:
            profile.onnxruntime_providers = list(
                onnxruntime.get_available_providers()
            )
        except Exception:  # noqa: BLE001
            profile.onnxruntime_providers = []
    except ImportError:
        pass

    # Espaço em disco (cwd)
    try:
        usage = shutil.disk_usage(os.getcwd())
        profile.free_disk_gb = usage.free / (1024 ** 3)
    except OSError:
        pass

    return profile


def recommend_flavor(profile: HardwareProfile) -> tuple[str, str]:
    """Decide a melhor variante de onnxruntime para o ambiente.

    Returns (flavor_key, rationale).
    flavor_key ∈ {default, cuda@12, cuda@13, openvino, rocm, migraphx, directml, qnn}.
    """
    # Sem GPU → default (CPU)
    if not profile.gpu_names and not profile.torch_cuda_available:
        return "default", "no NVIDIA GPU detected — using CPU onnxruntime"

    # AMD ROCm (heurística: torch.version.cuda vazio mas tem GPU AMD? difícil
    # detectar de forma confiável sem rocm-smi). Deixamos o default GPU
    # primeiro e o usuário escolhe via flag explícita para ROCm/MIGraphX.

    # CUDA disponível via torch → descobrir versão CUDA dominante.
    # Ordem de prioridade: torch_cuda_version (o que efetivamente roda
    # a inferência) > cuda_runtime_version (driver) > nvcc_version (toolkit).
    # Se há mismatch entre eles, é sintoma de ambiente bagunçado e logamos.
    cuda_major = ""
    source_used = ""
    for src, name in (
        (profile.torch_cuda_version, "torch"),
        (profile.cuda_runtime_version, "nvidia-smi"),
        (profile.nvcc_version, "nvcc"),
    ):
        if src:
            m = re.match(r"(\d+)", src)
            if m:
                cuda_major = m.group(1)
                source_used = name
                break

    # Diagnóstico de mismatch — não bloqueia, mas avisa.
    if cuda_major and profile.torch_cuda_version:
        m = re.match(r"(\d+)", profile.torch_cuda_version)
        if m and m.group(1) != cuda_major:
            # torch diz versão diferente da fonte escolhida — usa torch
            cuda_major = m.group(1)
            source_used = "torch (override)"

    if cuda_major == "13":
        return "cuda@13", (
            f"CUDA 13.x detected via {source_used} — using onnxruntime-gpu 1.29.0"
        )
    if cuda_major in ("12",):
        return "cuda@12", (
            f"CUDA 12.x detected via {source_used} — using onnxruntime-gpu 1.24.4"
        )
    if cuda_major in ("11",):
        # CUDA 11 não tem build oficial novo; cai pra default CPU
        return "default", (
            f"CUDA {cuda_major}.x detected but no onnxruntime-gpu build for it"
            " — falling back to CPU"
        )

    # Fallback: GPU detectada mas versão CUDA indeterminada.
    if profile.has_nvidia_smi or profile.torch_cuda_available:
        return "cuda@13", (
            "NVIDIA GPU detected but CUDA version unknown — defaulting to cuda@13"
        )

    return "default", "GPU present but no CUDA toolchain — using CPU onnxruntime"


if __name__ == "__main__":
    # Quick CLI sanity check
    p = detect()
    for line in p.summary_lines():
        print(line)
    flavor, why = recommend_flavor(p)
    print(f"\nrecommended flavor: {flavor}")
    print(f"rationale         : {why}")
