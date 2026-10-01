#!/usr/bin/env python3
import os
import sys

# YouFace patch: se o Python ativo é o do sistema e existe um .venv local
# (criado por install.py --use-venv), re-executa este entry-point dentro do
# venv antes de qualquer import pesado. O try/except ImportError mantém o
# arquivo tolerante a merges upstream parciais onde scripts/youface_venv.py
# ainda não foi portado — nesse caso cai no comportamento original do
# upstream (rodar com system Python e falhar com ModuleNotFoundError se
# faltar dep).
_ROOT = os.path.dirname(os.path.abspath(__file__))
try:
	sys.path.insert(0, os.path.join(_ROOT, "scripts"))
	from youface_venv import maybe_relaunch_in_venv
	maybe_relaunch_in_venv(_ROOT)
except ImportError:
	pass

if _ROOT not in sys.path:
	sys.path.insert(0, _ROOT)

os.environ['OMP_NUM_THREADS'] = '1'

from youface import conda, core

if __name__ == '__main__':
	from youface.app_context import set_app_context
	set_app_context('cli')
	conda.setup()
	core.cli()
