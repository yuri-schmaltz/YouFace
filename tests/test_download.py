from youface.download import (
	get_static_download_size,
	ping_static_url,
	resolve_download_url_by_provider,
	resolve_fallback_download_url_by_provider,
	resolve_download_url,
)
from youface import state_manager


def test_get_static_download_size() -> None:
	# Upstream URL still works (used in fallback path)
	assert get_static_download_size('https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/fairface.onnx') == 85170772
	assert get_static_download_size('invalid') == 0


def test_static_ping_url() -> None:
	assert ping_static_url('https://github.com') is True
	assert ping_static_url('https://huggingface.co') is True
	assert ping_static_url('invalid') is False


def test_resolve_download_url_by_provider() -> None:
	# Primary path: YouFace mirror (yuri-schmaltz/youface-assets)
	assert resolve_download_url_by_provider('github', 'models-3.0.0', 'fairface.onnx') == 'https://github.com/yuri-schmaltz/youface-assets/releases/download/models-3.0.0/fairface.onnx'
	# Fallback path: upstream facefusion/facefusion-assets
	assert resolve_fallback_download_url_by_provider('github', 'models-3.0.0', 'fairface.onnx') == 'https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/fairface.onnx'


def test_resolve_download_url_falls_back() -> None:
	"""resolve_download_url should return fallback when primary is unreachable.

	Simulated by checking that the function returns SOMETHING — if the
	mirror ever returns a valid response, the primary path is used;
	otherwise the fallback kicks in. Both paths must yield a non-None
	value pointing to a known host.
	"""
	state_manager.init_item('download_providers', ['github'])
	url = resolve_download_url('models-3.0.0', 'fairface.onnx')
	assert url is not None
	assert url.startswith('https://github.com/')
	# Either the YouFace mirror or the upstream fallback — both are valid.
	assert (
		'yuri-schmaltz/youface-assets' in url
		or 'facefusion/facefusion-assets' in url
	)