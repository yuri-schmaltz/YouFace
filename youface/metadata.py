from typing import Optional

METADATA =\
{
	'name': 'YouFace',
	'description': 'Industry leading face manipulation platform',
	'version': '3.9.1-my.2',
	'license': 'OpenRAIL-AS',
	'author': 'Henry Ruhs',
	'url': 'https://youface.io'
}


def get(key : str) -> Optional[str]:
	return METADATA.get(key)
