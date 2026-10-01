"""
Testes para o helper de auto-relaunch no .venv (scripts/youface_venv.py).

Cobre:
- venv_python() retorna o caminho correto POSIX/Win
- in_any_venv() detecta venv ativo
- maybe_relaunch_in_venv() é no-op quando já estamos em algum venv
- maybe_relaunch_in_venv() é no-op quando não há .venv local
- maybe_relaunch_in_venv() execva no .venv quando em system Python (simulado)

Roda em <1s, sem GPU e sem rede.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from youface_venv import in_any_venv, maybe_relaunch_in_venv, venv_python  # noqa: E402


# ---------------------------------------------------------------------------
# venv_python()
# ---------------------------------------------------------------------------

def test_venv_python_returns_real_venv_when_present():
    """No projeto de testes o .venv existe de verdade (CI/local)."""
    vpy = venv_python(str(REPO_ROOT))
    if (REPO_ROOT / ".venv").is_dir():
        # .venv presente — caminho deve apontar pra dentro dele.
        # Usamos Path equality (sem .resolve()) porque alguns venvs têm
        # bin/python como symlink absoluto para /usr/bin/python — nesse
        # caso resolve() sai de .venv, mas o os.execv ainda funciona porque
        # o pyvenv.cfg instrui o Python a usar o venv site-packages.
        assert vpy is not None
        venv_dir = (REPO_ROOT / ".venv").resolve()
        vpy_path = Path(vpy)
        assert venv_dir in vpy_path.resolve().parents or vpy_path == venv_dir / "bin" / "python" \
            or vpy_path == venv_dir / "bin" / "python3" \
            or vpy_path == venv_dir / "Scripts" / "python.exe"
    else:
        # .venv ausente — deve retornar None
        assert vpy is None


def test_venv_python_returns_none_when_no_venv(tmp_path):
    """Em diretório sem .venv, retorna None."""
    assert venv_python(str(tmp_path)) is None


def test_venv_python_prefers_bin_python_over_bin_python3(tmp_path, monkeypatch):
    """Quando existem múltiplos candidatos, retorna o primeiro da lista."""
    fake_venv = tmp_path / ".venv"
    fake_venv.mkdir()
    (fake_venv / "bin").mkdir()
    (fake_venv / "bin" / "python").write_text("")  # POSIX primário
    (fake_venv / "bin" / "python3").write_text("")
    result = venv_python(str(tmp_path))
    assert result == str(fake_venv / "bin" / "python")


def test_venv_python_handles_windows_layout(tmp_path):
    """No Windows, Scripts/python.exe deve ser encontrado."""
    fake_venv = tmp_path / ".venv"
    fake_venv.mkdir()
    (fake_venv / "Scripts").mkdir()
    (fake_venv / "Scripts" / "python.exe").write_text("")
    result = venv_python(str(tmp_path))
    assert result == str(fake_venv / "Scripts" / "python.exe")


# ---------------------------------------------------------------------------
# in_any_venv()
# ---------------------------------------------------------------------------

def test_in_any_venv_true_inside_project_venv():
    """Quando rodamos os testes via .venv/bin/python, retorna True."""
    # Se este teste está rodando, é porque alguém (CI ou dev) ativou
    # o .venv. Se system_prefix == base_prefix, fallback é False.
    assert isinstance(in_any_venv(), bool)
    if sys.prefix != sys.base_prefix:
        assert in_any_venv() is True


def test_in_any_venv_false_for_system_python_marker():
    """Forçando sys.prefix == sys.base_prefix, retorna False."""
    real_prefix, real_base = sys.prefix, sys.base_prefix
    sys.prefix = sys.base_prefix
    try:
        assert in_any_venv() is False
    finally:
        sys.prefix, sys.base_prefix = real_prefix, real_base


# ---------------------------------------------------------------------------
# maybe_relaunch_in_venv()
# ---------------------------------------------------------------------------

def test_maybe_relaunch_is_noop_inside_any_venv(capsys):
    """Se já estamos num venv, não deve nem tentar execv."""
    real_prefix, real_base = sys.prefix, sys.base_prefix
    sys.prefix = "/some/random/venv"
    sys.base_prefix = "/usr"
    try:
        # Não deve levantar nem execvar
        maybe_relaunch_in_venv(str(REPO_ROOT))
        out = capsys.readouterr().out
        assert "[relaunch]" not in out
    finally:
        sys.prefix, sys.base_prefix = real_prefix, real_base


def test_maybe_relaunch_is_noop_without_local_venv(tmp_path, capsys):
    """Em diretório sem .venv e em system Python, é no-op (deixa falhar naturalmente)."""
    real_prefix, real_base = sys.prefix, sys.base_prefix
    sys.prefix = sys.base_prefix  # finge system Python
    try:
        maybe_relaunch_in_venv(str(tmp_path))
        out = capsys.readouterr().out
        assert "[relaunch]" not in out  # não imprime banner
    finally:
        sys.prefix, sys.base_prefix = real_prefix, real_base


def test_maybe_relaunch_calls_execv_when_system_python_and_venv_exists(monkeypatch):
    """No caso de uso real: system Python + .venv presente → chama os.execv."""
    # 1) finge sys.prefix == sys.base_prefix
    real_prefix, real_base = sys.prefix, sys.base_prefix
    sys.prefix = sys.base_prefix

    # 2) prepara diretório fake com .venv/bin/python válido
    fake_root = REPO_ROOT / ".venv-test-tmp"
    fake_venv = fake_root / ".venv"
    (fake_venv / "bin").mkdir(parents=True)
    fake_py = fake_venv / "bin" / "python"
    fake_py.write_text("")  # arquivo vazio — não importa, é só o path

    # 3) captura os.execv pra não trocar o processo do pytest
    exec_calls = []
    def fake_execv(path, argv):
        exec_calls.append((path, argv))
    monkeypatch.setattr(os, "execv", fake_execv)

    try:
        maybe_relaunch_in_venv(str(fake_root))
    finally:
        # restaura sys.prefix e limpa diretório temporário
        sys.prefix, sys.base_prefix = real_prefix, real_base
        import shutil
        shutil.rmtree(fake_root, ignore_errors=True)

    # 4) valida: os.execv foi chamado exatamente uma vez, com o venv Python
    assert len(exec_calls) == 1
    called_path, called_argv = exec_calls[0]
    assert called_path == str(fake_py)
    assert called_argv[0] == str(fake_py)
    # argv[1] deve ser o caminho absoluto do entry-point original
    assert called_argv[1] == os.path.abspath(sys.argv[0])
    # resto do argv preservado
    assert called_argv[2:] == sys.argv[1:]