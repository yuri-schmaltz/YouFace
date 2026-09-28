from typing import Optional

METADATA =\
{
	'name': 'FaceFusion',
	'description': 'Industry leading face manipulation platform',
	'version': '3.9.0-my.1',
	'license': 'OpenRAIL-AS',
	'author': 'Henry Ruhs',
	'url': 'https://facefusion.io'
}


def get(key : str) -> Optional[str]:
	return METADATA.get(key)
