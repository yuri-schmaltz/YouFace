#!/usr/bin/env python3

import os
import sys

os.environ['SYSTEM_VERSION_COMPAT'] = '0'


def _is_smart_flag(argv):
	"""Return True se argv contém flags do wrapper inteligente."""
	smart_flags = {'--auto', '--info', '--dry-run', '--fix-cuda', '--yes', '-y',
	               '--break-system-packages', '--use-venv'}
	return any(arg in smart_flags for arg in argv)


if __name__ == '__main__':
	args = sys.argv[1:]

	if not args:
		# ZERO ARGS — o usuário quer que tudo aconteça. Roda o caminho
		# inteligente com defaults seguros: auto-detect flavor + venv isolado
		# + sem confirmação. Equivalente a `python install.py --auto --use-venv --yes`.
		from scripts.youface_install import wrapper
		sys.exit(wrapper.main(['--auto', '--use-venv', '--yes']))
	elif _is_smart_flag(args):
		# Despacha para o wrapper inteligente mantendo o upstream installer intacto.
		from scripts.youface_install import wrapper
		sys.exit(wrapper.main(args))
	else:
		# Caminho legacy — passa direto para o upstream.
		from youface import installer
		installer.cli()
