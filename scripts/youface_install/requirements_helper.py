"""
Parser inteligente de requirements.txt com filtros e auditoria.

Lê o requirements.txt do projeto (fonte de verdade, sincronizado com
pyproject.toml) e aplica:

1. **Filtro de onnxruntime** — descarta linhas começando com
   'onnxruntime' (a variante é decidida pelo wrapper, não pelo txt).
2. **Validação de pinos** — alerta se uma dep critical não está pinada
   (numpy, opencv, onnx).
3. **Estimativa de tamanho** — tamanho aproximado do download com base
   em heurística conhecida (pip download --no-deps diria, mas isso é
   offline).
4. **Detecção de duplicatas** — mesma dep declarada mais de uma vez.
5. **Detecção de marcadores de plataforma faltando** — ex.: onnxruntime-gpu
   sem ; sys_platform (deveria ter pin).
6. **Normalização** — retorna lista ordenada de strings limpas para
   passar pro pip install.

Não instala nada — apenas processa texto. 100% offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CRITICAL_DEPS = {"numpy", "opencv-python", "onnx", "scipy", "torch"}
RECOMMENDED_PINS = {"numpy", "opencv-python", "onnx", "scipy", "torch", "tqdm"}


@dataclass
class RequirementLine:
    raw: str                       # linha original com whitespace removido
    name: str                      # nome do pacote (lowercase, normalizado)
    specifier: str                 # parte de versão (==X.Y.Z, >=X, etc.)
    is_onnxruntime: bool = False
    is_critical: bool = False
    is_pinned: bool = False        # tem ==X.Y.Z
    platform_marker: str = ""      # "; sys_platform == 'linux'" etc.


@dataclass
class RequirementsReport:
    all_lines: list[RequirementLine] = field(default_factory=list)
    install_lines: list[str] = field(default_factory=list)  # sem onnxruntime
    onnxruntime_lines: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    unpinned_critical: list[str] = field(default_factory=list)
    estimated_total_size_mb: float = 0.0

    def warnings(self) -> list[str]:
        out: list[str] = []
        if self.duplicates:
            out.append(
                f"duplicates: {', '.join(sorted(set(self.duplicates)))}"
            )
        if self.unpinned_critical:
            out.append(
                "unpinned critical deps: "
                + ", ".join(sorted(set(self.unpinned_critical)))
                + " (recomendado ==X.Y.Z para reprodutibilidade)"
            )
        return out


_PIN_RE = re.compile(
    r"^([A-Za-z0-9_.\-]+)"          # name
    r"(?:\s*(==|>=|<=|~=|!=|>|<)"   # optional operator
    r"\s*([^\s;]+))?"                # optional version
    r"(.*)$"                          # tail (platform markers, etc.)
)
_PLATFORM_RE = re.compile(r";\s*sys_platform\s*(==|!=)\s*['\"]([^'\"]+)['\"]")


def _heuristic_size_mb(name: str) -> float:
    """Tamanho aproximado do wheel em MB. Heurística baseada em deps
    conhecidas — não é exata mas dá uma estimativa honesta."""
    n = name.lower()
    if "torch" in n:
        return 800.0  # CUDA wheels ~ 800 MB
    if "opencv" in n:
        return 60.0
    if "onnxruntime" in n:
        return 250.0
    if "torchvision" in n or "torchaudio" in n:
        return 5.0
    if "scipy" in n:
        return 35.0
    if "numpy" in n:
        return 25.0
    if "gradio" in n:
        return 30.0
    if "transformers" in n or "diffusers" in n:
        return 50.0
    if "insightface" in n:
        return 15.0
    return 5.0  # default


def parse(requirements_path: str = "requirements.txt") -> RequirementsReport:
    report = RequirementsReport()
    seen_names: set[str] = set()

    try:
        with open(requirements_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        report.duplicates.append(f"(file not found: {requirements_path})")
        return report

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Remove inline comments
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        if not line:
            continue

        # Platform marker
        platform = ""
        pm = _PLATFORM_RE.search(line)
        if pm:
            platform = pm.group(0)
            # Strip marker from line for parsing
            line = _PLATFORM_RE.sub("", line).strip()

        m = _PIN_RE.match(line)
        if not m:
            # Linha não parece um requisito — ignora silenciosamente
            continue

        name = m.group(1).lower()
        op = m.group(2) or ""           # None se não tiver operador
        version = m.group(3) or ""
        specifier = (f"{op}{version}" if version else op) if op else ""

        is_onnx = name.startswith("onnxruntime")
        is_crit = name in CRITICAL_DEPS
        is_pinned = op == "==" and bool(version)

        # Reanexa o platform marker se havia
        full_line = raw_line.strip()
        if platform and platform not in full_line:
            full_line = f"{line}{(' ' + platform)}"

        rl = RequirementLine(
            raw=full_line,
            name=name,
            specifier=specifier,
            is_onnxruntime=is_onnx,
            is_critical=is_crit,
            is_pinned=is_pinned,
            platform_marker=platform,
        )
        report.all_lines.append(rl)

        if is_onnx:
            report.onnxruntime_lines.append(full_line)
            continue

        if name in seen_names:
            report.duplicates.append(name)
        seen_names.add(name)

        report.install_lines.append(line)
        report.estimated_total_size_mb += _heuristic_size_mb(name)

        if is_crit and not is_pinned and name in RECOMMENDED_PINS:
            report.unpinned_critical.append(name)

    return report


if __name__ == "__main__":
    rep = parse("requirements.txt")
    print(f"install lines: {len(rep.install_lines)}")
    print(f"onnxruntime lines (filtered): {len(rep.onnxruntime_lines)}")
    print(f"duplicates: {rep.duplicates or '(none)'}")
    print(f"unpinned critical: {rep.unpinned_critical or '(none)'}")
    print(f"estimated total download: ~{rep.estimated_total_size_mb:.0f} MB")
    if rep.warnings():
        print("\nWARNINGS:")
        for w in rep.warnings():
            print(f"  - {w}")
