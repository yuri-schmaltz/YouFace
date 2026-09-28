#!/usr/bin/env python3

import os
import sys

os.environ['SYSTEM_VERSION_COMPAT'] = '0'


def _is_smart_flag(argv):
	"""Return True se argv contém flags do wrapper inteligente."""
	smart_flags = {'--auto', '--info', '--dry-run', '--fix-cuda', '--yes', '-y'}
	return any(arg in smart_flags for arg in argv)


if __name__ == '__main__':
	if _is_smart_flag(sys.argv[1:]):
		# Despacha para o wrapper inteligente mantendo o upstream installer intacto.
		from scripts.youface_install import wrapper
		sys.exit(wrapper.main(sys.argv[1:]))
	else:
		# Caminho legacy — passa direto para o upstream.
		from facefusion import installer
		installer.cli()
