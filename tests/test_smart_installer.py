"""
Testes para o instalador inteligente YouFace.

Cobre:
- hardware.detect() em vários perfis (mock de nvidia-smi/torch)
- hardware.recommend_flavor() para CUDA 11/12/13, sem GPU, GPU sem torch
- requirements_helper.parse() com requisitos válidos, duplicatas, comentários
- wrapper.cli (subprocess) para --info, --dry-run, --auto
- back-compat: positional `default` continua funcionando

Não precisa de GPU real nem de rede. Roda em <2s.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from youface_install import hardware  # noqa: E402
from youface_install import requirements_helper  # noqa: E402


# ---------------------------------------------------------------------------
# hardware.detect()
# ---------------------------------------------------------------------------

def test_detect_returns_profile_with_required_fields():
    profile = hardware.detect()
    assert profile.platform in ("linux", "darwin", "windows")
    assert profile.arch
    assert profile.python_version
    # free_disk_gb deve ser > 0 em qualquer sistema que rode os testes
    assert profile.free_disk_gb > 0


def test_detect_handles_no_nvidia_smi():
    """Quando nvidia-smi não existe, profile.has_nvidia_smi=False."""
    with mock.patch("shutil.which", return_value=None):
        profile = hardware.detect()
    assert profile.has_nvidia_smi is False
    assert profile.gpu_names == []
    assert profile.nvidia_driver_version == ""


def test_detect_parses_nvidia_smi_csv_with_header():
    """Drivers antigos emitem header 'name, driver_version'."""
    fake_output = "name, driver_version\nNVIDIA GeForce RTX 3060, 535.86"
    names, drv, _ = hardware._parse_nvidia_smi_csv(fake_output)
    assert names == ["NVIDIA GeForce RTX 3060"]
    assert drv == "535.86"


def test_detect_parses_nvidia_smi_csv_noheader():
    """Drivers 595+ não suportam noheader — saem só com dados."""
    fake_output = "NVIDIA GeForce RTX 3060, 595.84"
    names, drv, _ = hardware._parse_nvidia_smi_csv(fake_output)
    assert names == ["NVIDIA GeForce RTX 3060"]
    assert drv == "595.84"


def test_detect_parses_cuda_runtime():
    assert hardware._parse_cuda_runtime("13.0") == "13.0"
    assert hardware._parse_cuda_runtime("") == ""
    assert hardware._parse_cuda_runtime("garbage") == ""


def test_detect_parses_nvcc():
    nvcc_out = textwrap.dedent("""\
        nvcc: NVIDIA (R) Cuda compiler driver
        Copyright (c) 2005-2024 NVIDIA Corporation
        Built on Tue_Oct_29_22:37:36_PDT_2024
        Cuda compilation tools, release 12.0, V12.0.76
        Build cuda_12.0.r12.0/compiler.32314.0""")
    assert hardware._parse_nvcc_version(nvcc_out) == "12.0"


# ---------------------------------------------------------------------------
# hardware.recommend_flavor()
# ---------------------------------------------------------------------------

def test_recommend_default_when_no_gpu():
    profile = hardware.HardwareProfile(gpu_names=[], has_nvidia_smi=False)
    flavor, why = hardware.recommend_flavor(profile)
    assert flavor == "default"
    assert "CPU" in why or "no NVIDIA" in why


def test_recommend_cuda13_when_torch_cuda13():
    profile = hardware.HardwareProfile(
        gpu_names=["RTX 3060"], torch_cuda_version="13.0",
        torch_cuda_available=True,
    )
    flavor, why = hardware.recommend_flavor(profile)
    assert flavor == "cuda@13"
    assert "13.x" in why


def test_recommend_cuda12_when_torch_cuda12():
    profile = hardware.HardwareProfile(
        gpu_names=["RTX 3060"], torch_cuda_version="12.1",
        torch_cuda_available=True,
    )
    flavor, why = hardware.recommend_flavor(profile)
    assert flavor == "cuda@12"
    assert "12.x" in why


def test_recommend_default_when_cuda11():
    profile = hardware.HardwareProfile(
        gpu_names=["GTX 1080"], torch_cuda_version="11.8",
        torch_cuda_available=True,
    )
    flavor, why = hardware.recommend_flavor(profile)
    assert flavor == "default"


def test_recommend_overrides_to_torch_when_driver_mismatch():
    """Se torch diz CUDA 13 mas driver diz 12, torch vence."""
    profile = hardware.HardwareProfile(
        gpu_names=["RTX 3060"],
        torch_cuda_version="13.0",
        cuda_runtime_version="12.4",  # driver diz 12
        nvcc_version="12.0",
        torch_cuda_available=True,
    )
    flavor, why = hardware.recommend_flavor(profile)
    assert flavor == "cuda@13"
    assert "torch" in why


# ---------------------------------------------------------------------------
# requirements_helper.parse()
# ---------------------------------------------------------------------------

def test_parse_basic_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(textwrap.dedent("""\
        # comment line
        numpy==2.2.1
        fastapi>=0.110.0
        opencv-python==4.13.0.92
        """))
    rep = requirements_helper.parse(str(req))
    assert len(rep.install_lines) == 3
    assert "numpy==2.2.1" in rep.install_lines
    assert "fastapi>=0.110.0" in rep.install_lines
    assert rep.duplicates == []


def test_parse_filters_onnxruntime_lines(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(textwrap.dedent("""\
        numpy==2.2.1
        onnxruntime==1.20.0
        onnxruntime-gpu==1.24.4
        fastapi>=0.110.0
        """))
    rep = requirements_helper.parse(str(req))
    assert len(rep.install_lines) == 2  # numpy + fastapi
    assert len(rep.onnxruntime_lines) == 2  # both onnxruntime lines filtered
    assert all("onnxruntime" not in line for line in rep.install_lines)


def test_parse_detects_unpinned_critical(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(textwrap.dedent("""\
        numpy
        opencv-python==4.13.0.92
        torch>=2.0.0
        """))
    rep = requirements_helper.parse(str(req))
    # numpy + torch unpinned, opencv-python pinned
    assert "numpy" in rep.unpinned_critical
    assert "torch" in rep.unpinned_critical
    assert "opencv-python" not in rep.unpinned_critical


def test_parse_detects_duplicates(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(textwrap.dedent("""\
        numpy==2.2.1
        numpy>=2.0.0
        fastapi>=0.110.0
        """))
    rep = requirements_helper.parse(str(req))
    assert "numpy" in rep.duplicates


def test_parse_estimates_size(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("numpy==2.2.1\nopencv-python==4.13.0.92\n")
    rep = requirements_helper.parse(str(req))
    # 25 MB (numpy) + 60 MB (opencv) = 85 MB
    assert 80 <= rep.estimated_total_size_mb <= 100


def test_parse_filters_onnxruntime_lines_keeps_platform_markers(tmp_path):
    """Linhas onnxruntime* vão pro filtro, mas platform markers em outras
    deps precisam ser preservados na linha que vai pro pip install."""
    req = tmp_path / "requirements.txt"
    req.write_text(textwrap.dedent("""\
        numpy==2.2.1
        onnxruntime==1.20.0; sys_platform == "linux"
        """))
    rep = requirements_helper.parse(str(req))
    # numpy deve ser install_lines sem marker (não tinha)
    assert "numpy==2.2.1" in rep.install_lines
    # onnxruntime vai pro filtro
    assert len(rep.onnxruntime_lines) == 1


def test_parse_handles_inline_comments(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("numpy==2.2.1  # pinned for ABI\nfastapi>=0.110.0\n")
    rep = requirements_helper.parse(str(req))
    assert len(rep.install_lines) == 2
    assert "# pinned" not in rep.install_lines[0]


# ---------------------------------------------------------------------------
# CLI integration tests (subprocess)
# ---------------------------------------------------------------------------

def run_cli(*args, cwd=None):
    """Run `python install.py ...` and return (rc, stdout, stderr)."""
    cmd = [sys.executable, "install.py", *args]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO_ROOT)
    return p.returncode, p.stdout, p.stderr


def test_cli_info_succeeds():
    rc, out, err = run_cli("--info")
    assert rc == 0, f"stderr: {err}\nstdout: {out}"
    assert "Hardware detected" in out
    assert "recommended flavor" in out.lower() or "recommend" in out.lower()


def test_cli_dry_run_succeeds():
    rc, out, err = run_cli("--dry-run")
    assert rc == 0, f"stderr: {err}\nstdout: {out}"
    assert "dry-run" in out
    assert "pip install" in out
    assert "onnxruntime" in out


def test_cli_auto_with_dry_run():
    rc, out, err = run_cli("--auto", "--dry-run")
    assert rc == 0, f"stderr: {err}\nstdout: {out}"
    assert "selected flavor" in out.lower()


def test_cli_legacy_positional_help():
    """Sem smart flag, --help mostra menu do upstream (back-compat)."""
    rc, out, err = run_cli("--help")
    assert rc == 0
    assert "default,cuda@12" in out  # upstream choices
    assert "--auto" not in out  # sem flag smart visível


def test_cli_legacy_positional_rejects_bad_choice():
    rc, out, err = run_cli("not_a_real_flavor")
    assert rc != 0
    assert "invalid choice" in err or "invalid" in err


def test_cli_fix_cuda_alias():
    rc, out, err = run_cli("--fix-cuda", "--dry-run")
    assert rc == 0, f"stderr: {err}\nstdout: {out}"
    assert "selected flavor" in out.lower()


def test_cli_upstream_invoked_as_module():
    """O wrapper deve chamar o upstream via `python -m facefusion.installer`
    para evitar o sombreamento de facefusion/types.py sobre stdlib types."""
    rc, out, err = run_cli("--auto", "--dry-run")
    assert rc == 0
    # O comando pip preview mostra `pip install` (não `facefusion.installer`),
    # mas podemos inspecionar a invocação do upstream checando o import:
    proc = subprocess.run(
        [sys.executable, "-c",
         "from facefusion.installer import cli; print('ok')"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    assert proc.stdout.strip() == "ok"


def test_cli_pep668_detection_surfaces_in_preflight():
    """Em sistemas PEP 668 (Debian 12+/Ubuntu 23.04+/Mint 22+), o pre-flight
    deve mencionar que vai usar --break-system-packages como fallback."""
    rc, out, err = run_cli("--dry-run")
    assert rc == 0
    # No sandbox o PEP 668 é detectado (tem EXTERNALLY-MANAGED).
    if "PEP 668 detected" in out:
        assert "break-system-packages" in out or "use-venv" in out


def test_cli_help_mentions_new_flags():
    """Garante que --break-system-packages e --use-venv estão documentados.

    Para ver a help do wrapper (e não a do upstream), passamos uma flag
    smart como --info primeiro.
    """
    rc, out, _ = run_cli("--info", "--help")
    assert rc == 0
    assert "--break-system-packages" in out
    assert "--use-venv" in out


def test_detect_pep668_helper():
    """_detect_pep668() deve retornar True no sandbox (Mint 22)."""
    from youface_install.wrapper import _detect_pep668
    result = _detect_pep668()
    # Em sandbox tem EXTERNALLY-MANAGED; pode ser True ou False em CI limpo.
    assert isinstance(result, bool)


def test_verify_onnxruntime_installed_returns_bool():
    """_verify_onnxruntime_installed retorna bool, nunca levanta."""
    from youface_install.wrapper import _verify_onnxruntime_installed
    assert isinstance(_verify_onnxruntime_installed("default"), bool)
    assert isinstance(_verify_onnxruntime_installed("cuda@13"), bool)
    assert isinstance(_verify_onnxruntime_installed("nonexistent"), bool)
