import random
from typing import Optional

import gradio

from youface import metadata, translator

METADATA_BUTTON : Optional[gradio.Button] = None
ACTION_BUTTON : Optional[gradio.Button] = None


def render() -> None:
	global METADATA_BUTTON
	global ACTION_BUTTON

	action = random.choice(
	[
		{
			'translator': translator.get('about.fund'),
			'url': 'https://fund.youface.io'
		},
		{
			'translator': translator.get('about.subscribe'),
			'url': 'https://subscribe.youface.io'
		},
		{
			'translator': translator.get('about.join'),
			'url': 'https://join.youface.io'
		}
	])

	METADATA_BUTTON = gradio.Button(
		value = metadata.get('name') + ' ' + metadata.get('version'),
		variant = 'primary',
		link = metadata.get('url')
	)
	ACTION_BUTTON = gradio.Button(
		value = action.get('translator'),
		link = action.get('url'),
		size = 'sm'
	)
