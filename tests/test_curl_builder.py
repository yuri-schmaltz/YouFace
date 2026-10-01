from shutil import which

from youface import metadata
from youface.curl_builder import chain, ping, run, set_timeout


def test_run() -> None:
	user_agent = metadata.get('name') + '/' + metadata.get('version')

	assert run([]) == [ which('curl'), '--user-agent', user_agent, '--location', '--silent', '--ssl-no-revoke' ]


def test_chain() -> None:
	assert chain(
		ping(metadata.get('url')),
		set_timeout(5)
	) == [ '-I', metadata.get('url'), '--connect-timeout', '5' ]
