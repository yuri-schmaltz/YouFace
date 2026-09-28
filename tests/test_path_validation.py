"""
Testes para validação de caminhos (P1-3 do SWOT: Local File Inclusion).

Cobre:
- Caminho dentro de diretório permitido é aceito
- Caminho fora de diretório permitido é rejeitado (400)
- Tentativas de path traversal (../) são bloqueadas
- Caminhos absolutos não-autorizados são bloqueados
- A função lida com caminhos relativos corretamente
- Não confunde prefixos similares (ex: /tmp/foo vs /tmp/foobar)

NOTA: Os testes extraem a função via AST direto do source de routes.py
para evitar o `import facefusion.api.routes` que puxa cv2/onnxruntime
transitivamente. A função `validate_safe_path` é autocontida.
"""
import os
import sys
import tempfile
import ast
import pytest
from pathlib import Path
from fastapi import HTTPException


def _load_validate_safe_path():
    """Extrai apenas a função `validate_safe_path` do source de routes.py."""
    routes_path = Path(__file__).parent.parent / "facefusion" / "api" / "routes.py"
    source = routes_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    func_code = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "validate_safe_path":
            func_code = ast.unparse(node)
            break
    assert func_code is not None, "validate_safe_path not found in routes.py"
    from typing import Optional, List
    namespace = {"os": os, "HTTPException": HTTPException, "Optional": Optional, "List": List}
    exec(compile(func_code, "<isolated>", "exec"), namespace)
    return namespace["validate_safe_path"]


validate_safe_path = _load_validate_safe_path()


def test_validate_safe_path_accepts_path_inside_allowed_dir():
    """Caminho dentro de diretório permitido é aceito."""
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "subdir", "file.jpg")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        result = validate_safe_path(target, [tmp])
        assert os.path.abspath(target) == result


def test_validate_safe_path_rejects_path_outside_allowed_dir():
    """Caminho fora de diretório permitido é rejeitado com 400."""
    with tempfile.TemporaryDirectory() as allowed_tmp, tempfile.TemporaryDirectory() as other_tmp:
        target = os.path.join(other_tmp, "secret.txt")
        with pytest.raises(HTTPException) as exc:
            validate_safe_path(target, [allowed_tmp])
        assert exc.value.status_code == 400
        assert "Acesso negado" in exc.value.detail


def test_validate_safe_path_blocks_path_traversal():
    """Tentativa de path traversal (../) saindo do allowed é bloqueada."""
    with tempfile.TemporaryDirectory() as allowed_tmp:
        target = os.path.join(allowed_tmp, "..", "..", "etc", "passwd")
        with pytest.raises(HTTPException) as exc:
            validate_safe_path(target, [allowed_tmp])
        assert exc.value.status_code == 400


def test_validate_safe_path_blocks_absolute_unauthorized_path():
    """Caminho absoluto em /etc/passwd é bloqueado."""
    with tempfile.TemporaryDirectory() as allowed_tmp:
        with pytest.raises(HTTPException) as exc:
            validate_safe_path("/etc/passwd", [allowed_tmp])
        assert exc.value.status_code == 400


def test_validate_safe_path_accepts_exact_allowed_dir():
    """O próprio diretório permitido é aceito."""
    with tempfile.TemporaryDirectory() as allowed_tmp:
        result = validate_safe_path(allowed_tmp, [allowed_tmp])
        assert os.path.abspath(allowed_tmp) == result


def test_validate_safe_path_normalizes_relative_paths():
    """Caminhos relativos são normalizados para absolutos."""
    with tempfile.TemporaryDirectory() as allowed_tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(allowed_tmp)
            result = validate_safe_path("./subdir/file.png", [allowed_tmp])
            assert result.startswith(os.path.abspath(allowed_tmp))
        finally:
            os.chdir(old_cwd)


def test_validate_safe_path_multiple_allowed_dirs():
    """Aceita paths em qualquer um dos diretórios permitidos."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        target1 = os.path.join(tmp1, "a.jpg")
        assert validate_safe_path(target1, [tmp1, tmp2]) == os.path.abspath(target1)
        target2 = os.path.join(tmp2, "b.jpg")
        assert validate_safe_path(target2, [tmp1, tmp2]) == os.path.abspath(target2)
        with tempfile.TemporaryDirectory() as tmp3:
            target3 = os.path.join(tmp3, "c.jpg")
            with pytest.raises(HTTPException):
                validate_safe_path(target3, [tmp1, tmp2])


def test_validate_safe_path_handles_sibling_prefix_correctly(tmp_path):
    """Não confunde /foo/allowed com /foo/allowed_sibling (prefixo similar)."""
    # Cria duas dirs irmãs com prefixo similar dentro de tmp_path
    allowed = tmp_path / "allowed"
    sibling = tmp_path / "allowed_sibling"
    allowed.mkdir()
    sibling.mkdir()
    target = sibling / "secret.txt"
    target.write_text("data")
    with pytest.raises(HTTPException):
        validate_safe_path(str(target), [str(allowed)])
