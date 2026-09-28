#!/usr/bin/env python3
"""
Entry-point do instalador inteligente YouFace.

Zero-args instala tudo automaticamente:
    python scripts/youface_install.py
Equivalente a:
    python scripts/youface_install.py --auto --use-venv --yes

Uso:
    python scripts/youface_install.py                # auto-detect tudo
    python scripts/youface_install.py --info         # print env + recommendation
    python scripts/youface_install.py --dry-run      # preview sem executar
    python scripts/youface_install.py --auto         # detect flavor, install
    python scripts/youface_install.py --auto --dry-run
    python scripts/youface_install.py cuda@13        # flavor explícito
    python scripts/youface_install.py --break-system-packages  # install system-wide
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from youface_install.wrapper import main

if __name__ == "__main__":
    sys.exit(main())
