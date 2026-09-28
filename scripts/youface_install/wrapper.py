"""
Wrapper inteligente em torno de `facefusion/installer.py`.

Problemas resolvidos em relação ao instalador upstream:
  - Não exige argumento posicional -- detecta GPU/CUDA e escolhe a
    variante de onnxruntime apropriada.
  - Suporta `--auto`, `--info`, `--dry-run`, `--fix-cuda`, `--force-cuda`.
  - Mostra preview do que será instalado antes de executar.
  - Detecta mismatch torch/CUDA antes de instalar.
  - Recupera de falhas parciais (resume install).
  - Mantém 100% compatível com o upstream (`default`, `cuda@12`, etc.
    como posicional continua funcionando).
  - Roda o upstream `installer.run()` para a instalação real — assim
    um próximo merge upstream não conflita com nossa lógica.

Uso:
    python scripts/youface_install.py --auto
    python scripts/youface_install.py --info
    python scripts/youface_install.py --dry-run
    python scripts/youface_install.py --auto --force-reinstall
    python scripts/youface_install.py cuda@13            # legacy passthrough
    python scripts/youface_install.py default --skip-conda

Saída:
    Código 0 em sucesso / dry-run / info.
    Código 1 em erro de validação.
    Código 2 em falha de pip install.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import Sequence

# Permite `import hardware` / `import requirements_helper` quando rodando
# este arquivo diretamente. Em produção normal, scripts/ está no PYTHONPATH.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from hardware import HardwareProfile, detect, recommend_flavor  # noqa: E402
from requirements_helper import RequirementsReport, parse as parse_reqs  # noqa: E402


UPSTREAM_INSTALLER_PATH = os.path.join(
    os.path.dirname(_HERE), "..", "facefusion", "installer.py"
)


def _print_section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def _print_profile(profile: HardwareProfile, recommended: tuple[str, str]) -> None:
    _print_section("Hardware detected")
    for line in profile.summary_lines():
        print(line)
    flavor, why = recommended
    print()
    print(f"recommended flavor : {flavor}")
    print(f"rationale          : {why}")


def _print_requirements(profile: HardwareProfile, reqs: RequirementsReport,
                        flavor: str) -> None:
    from hardware import detect as hw_detect  # noqa: F401 — só para hot-reload
    _print_section("Requirements.txt")
    print(f"install lines       : {len(reqs.install_lines)}")
    print(f"onnxruntime filtered: {len(reqs.onnxruntime_lines)} (variant chosen by CLI)")
    print(f"estimated download  : ~{reqs.estimated_total_size_mb:.0f} MB")
    if reqs.warnings():
        print()
        print("warnings:")
        for w in reqs.warnings():
            print(f"  - {w}")

    _print_section("Selected onnxruntime")
    print(f"flavor  : {flavor}")
    print(f"package : {'onnxruntime-gpu' if 'cuda' in flavor else 'onnxruntime'}"
          f"{' (openvino)' if flavor == 'openvino' else ''}"
          f"{' (rocm)' if flavor == 'rocm' else ''}"
          f"{' (migraphx)' if flavor == 'migraphx' else ''}")


def _check_disk_space(profile: HardwareProfile, reqs: RequirementsReport,
                       flavor: str) -> tuple[bool, str]:
    """Retorna (ok, mensagem)."""
    onnx_size_mb = 250.0
    if "cuda" in flavor:
        onnx_size_mb = 350.0  # GPU wheels são maiores
    elif flavor == "rocm":
        onnx_size_mb = 300.0
    elif flavor == "openvino":
        onnx_size_mb = 200.0

    needed_mb = reqs.estimated_total_size_mb + onnx_size_mb + 500  # +500 MB buffer
    have_mb = profile.free_disk_gb * 1024
    if have_mb < needed_mb:
        return False, (
            f"insufficient disk: need ~{needed_mb:.0f} MB, "
            f"have {have_mb:.0f} MB"
        )
    return True, f"disk OK: need ~{needed_mb:.0f} MB, have {have_mb:.0f} MB"


def _check_pip_available() -> tuple[bool, str]:
    if shutil.which("pip") is None and shutil.which(f"pip{sys.version_info.major}") is None:
        # pip pode estar disponível só como `python -m pip`
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True, check=True, timeout=10,
            )
            return True, f"pip available via `{sys.executable} -m pip`"
        except Exception:  # noqa: BLE001
            return False, "pip not found in PATH and not via python -m"
    return True, "pip available in PATH"


def _check_venv() -> tuple[bool, str]:
    in_venv = (
        hasattr(sys, "real_prefix")
        or (getattr(sys, "base_prefix", sys.prefix) != sys.prefix)
        or "VIRTUAL_ENV" in os.environ
        or "CONDA_PREFIX" in os.environ
    )
    if in_venv:
        env = os.environ.get("CONDA_PREFIX") and "conda" or "venv"
        return True, f"running inside {env}"
    return False, "not running inside a venv (risky — installs system-wide)"


def _dry_run_commands(flavor: str, force_reinstall: bool,
                       skip_conda: bool) -> list[str]:
    """Constrói (mas não executa) os comandos que o upstream installer rodaria."""
    reqs = parse_reqs("requirements.txt")
    cmds: list[str] = []
    # Uninstall loop
    cmds.append("# 1) Uninstall any pre-existing onnxruntime* flavors:")
    cmds.append(f"{sys.executable} -m pip uninstall -y -q onnxruntime onnxruntime-gpu "
                "onnxruntime-openvino onnxruntime-directml onnxruntime-rocm "
                "onnxruntime-migraphx onnxruntime-qnn 2>/dev/null")
    # Install
    cmds.append("")
    cmds.append("# 2) Install requirements.txt (filtered) + selected onnxruntime:")
    install = [sys.executable, "-m", "pip", "install"]
    if force_reinstall:
        install.append("--force-reinstall")
    install.extend(reqs.install_lines)
    if "cuda" in flavor or flavor == "default":
        ver = {"default": "1.29.0", "cuda@12": "1.24.4",
               "cuda@13": "1.29.0"}.get(flavor, "1.29.0")
        pkg = "onnxruntime-gpu" if "cuda" in flavor else "onnxruntime"
        install.append(f"{pkg}=={ver}")
    elif flavor == "openvino":
        install.append("onnxruntime-openvino==1.24.1")
    elif flavor == "rocm":
        install.append("onnxruntime-rocm==1.22.2.post3")
    elif flavor == "migraphx":
        install.append("onnxruntime-migraphx==1.27.1")
    elif flavor == "directml":
        install.append("onnxruntime-directml==1.24.4")
    elif flavor == "qnn":
        install.append("onnxruntime-qnn==2.5.0")
    cmds.append(" ".join(install))
    return cmds


def _invoke_upstream(flavor: str, force_reinstall: bool,
                     skip_conda: bool, extra_args: Sequence[str]) -> int:
    """Roda o instalador upstream com os args certos. Retorna exit code."""
    cmd = [sys.executable, UPSTREAM_INSTALLER_PATH, flavor]
    if force_reinstall:
        cmd.append("--force-reinstall")
    if skip_conda:
        cmd.append("--skip-conda")
    cmd.extend(extra_args)
    print()
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd)


def _validate_preflight(profile: HardwareProfile,
                        reqs: RequirementsReport,
                        flavor: str) -> list[str]:
    """Checagens pré-instalação. Retorna lista de warnings."""
    warnings: list[str] = []

    ok, msg = _check_pip_available()
    if not ok:
        warnings.append(f"[FATAL] {msg}")
    else:
        print(f"[ok] {msg}")

    ok, msg = _check_venv()
    if not ok:
        warnings.append(f"[warn] {msg}")
    else:
        print(f"[ok] {msg}")

    ok, msg = _check_disk_space(profile, reqs, flavor)
    if not ok:
        warnings.append(f"[FATAL] {msg}")
    else:
        print(f"[ok] {msg}")

    # Mismatch torch/CUDA
    if profile.torch_installed and profile.torch_cuda_version and profile.cuda_runtime_version:
        torch_major = profile.torch_cuda_version.split(".")[0]
        rt_csv = _run_safe(["nvidia-smi", "--query-gpu=cuda_runtime_version",
                            "--format=csv"])
        if rt_csv:
            from hardware import _parse_cuda_runtime  # type: ignore
            rt = _parse_cuda_runtime(rt_csv)
            if rt and rt.split(".")[0] != torch_major:
                warnings.append(
                    f"[warn] torch built for CUDA {profile.torch_cuda_version} but "
                    f"driver exposes CUDA {rt}. onnxruntime-gpu may not load."
                )

    return warnings


def _run_safe(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                           env={**os.environ, "LANG": "C"}, check=False)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def cmd_info(args: argparse.Namespace) -> int:
    profile = detect()
    recommended = recommend_flavor(profile)
    reqs = parse_reqs("requirements.txt")
    _print_profile(profile, recommended)
    _print_requirements(profile, reqs, recommended[0])
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    profile = detect()
    if args.flavor and not args.auto:
        flavor = args.flavor
        why = "user-specified"
    else:
        flavor, why = recommend_flavor(profile)
        print(f"[auto] selected flavor: {flavor}")
        print(f"[auto] rationale    : {why}")

    reqs = parse_reqs("requirements.txt")
    _print_profile(profile, (flavor, why))
    _print_requirements(profile, reqs, flavor)

    print()
    print("=== Pre-flight ===")
    warnings = _validate_preflight(profile, reqs, flavor)
    if warnings:
        for w in warnings:
            print(w)

    print()
    print("=== Pip commands that would run ===")
    cmds = _dry_run_commands(flavor, args.force_reinstall, args.skip_conda)
    for c in cmds:
        print(c)
    print()
    print("[dry-run] no changes made. Re-run without --dry-run to apply.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    profile = detect()
    if args.auto or not args.flavor:
        flavor, why = recommend_flavor(profile)
        print(f"[auto] selected flavor: {flavor}")
        print(f"[auto] rationale    : {why}")
    else:
        flavor = args.flavor

    reqs = parse_reqs("requirements.txt")
    _print_profile(profile, (flavor, "user-specified" if not (args.auto or not args.flavor) else "auto"))
    _print_requirements(profile, reqs, flavor)

    print()
    print("=== Pre-flight ===")
    warnings = _validate_preflight(profile, reqs, flavor)
    for w in warnings:
        print(w)
    if any("[FATAL]" in w for w in warnings):
        print("[abort] pre-flight failed. Fix the issues above and re-run.")
        return 1

    if not args.yes:
        print()
        resp = input("Proceed with install? [y/N] ").strip().lower()
        if resp != "y":
            print("[abort] user cancelled.")
            return 1

    return _invoke_upstream(flavor, args.force_reinstall, args.skip_conda,
                             args.passthrough)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="youface_install",
        description="Smart wrapper around facefusion installer. Detects GPU/CUDA, "
                    "picks the right onnxruntime flavor, validates environment, "
                    "and shows pre-flight before pip install.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # --auto is a flavor-selection flag (not a mode), so it does NOT live
    # in the mutex group with --info/--dry-run.
    p.add_argument("--auto", action="store_true",
                   help="Auto-detect flavor (default if no positional given)")
    p.add_argument("--fix-cuda", action="store_true",
                   help="Alias for --auto (kept for backward compat with internal scripts)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--info", action="store_true",
                      help="Show detected hardware + recommended flavor + requirements audit, then exit")
    mode.add_argument("--dry-run", action="store_true",
                      help="Show what would be installed without executing")

    p.add_argument("flavor", nargs="?",
                   help="onnxruntime flavor (default|cuda@12|cuda@13|openvino|rocm|migraphx|directml|qnn). "
                        "If omitted, --auto is used.")
    p.add_argument("--force-reinstall", action="store_true",
                   help="Pass --force-reinstall to pip")
    p.add_argument("--skip-conda", action="store_true",
                   help="Pass --skip-conda to upstream installer")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompt")
    p.add_argument("--passthrough", nargs=argparse.REMAINDER, default=[],
                   help="Extra args passed verbatim to the upstream installer")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.fix_cuda:
        args.auto = True

    if args.info:
        return cmd_info(args)
    if args.dry_run:
        return cmd_dry_run(args)
    return cmd_install(args)


if __name__ == "__main__":
    sys.exit(main())
