#!/usr/bin/env python3
"""
Entry-point do instalador inteligente YouFace.

Uso:
    python scripts/youface_install.py --info
    python scripts/youface_install.py --auto
    python scripts/youface_install.py --auto --dry-run
    python scripts/youface_install.py cuda@13
    python scripts/youface_install.py --auto --yes --force-reinstall

Para a versão upstream original, use `python install.py <flavor>`.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from youface_install.wrapper import main

if __name__ == "__main__":
    sys.exit(main())
