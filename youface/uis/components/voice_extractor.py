from typing import List, Optional

import gradio

import youface.choices
from youface import state_manager, translator, voice_extractor
from youface.filesystem import is_video
from youface.types import VoiceExtractorModel
from youface.uis.core import get_ui_component, get_ui_components, register_ui_component

VOICE_EXTRACTOR_MODEL_DROPDOWN : Optional[gradio.Dropdown] = None


def render() -> None:
	global VOICE_EXTRACTOR_MODEL_DROPDOWN

	has_lip_syncer = 'lip_syncer' in state_manager.get_item('processors')
	VOICE_EXTRACTOR_MODEL_DROPDOWN = gradio.Dropdown(
		label = translator.get('uis.voice_extractor_model_dropdown'),
		choices = youface.choices.voice_extractor_models,
		value = state_manager.get_item('voice_extractor_model'),
		visible = is_video(state_manager.get_item('target_path')) and has_lip_syncer
	)
	register_ui_component('voice_extractor_model_dropdown', VOICE_EXTRACTOR_MODEL_DROPDOWN)


def listen() -> None:
	VOICE_EXTRACTOR_MODEL_DROPDOWN.change(update_voice_extractor_model, inputs = VOICE_EXTRACTOR_MODEL_DROPDOWN, outputs = VOICE_EXTRACTOR_MODEL_DROPDOWN)

	processors_checkbox_group = get_ui_component('processors_checkbox_group')
	if processors_checkbox_group:
		processors_checkbox_group.change(remote_update, inputs = processors_checkbox_group, outputs = VOICE_EXTRACTOR_MODEL_DROPDOWN)

		for ui_component in get_ui_components(
		[
			'target_image',
			'target_video'
		]):
			for method in [ 'change', 'clear' ]:
				getattr(ui_component, method)(remote_update, inputs = processors_checkbox_group, outputs = VOICE_EXTRACTOR_MODEL_DROPDOWN)


def remote_update(processors : List[str]) -> gradio.Dropdown:
	has_lip_syncer = 'lip_syncer' in processors
	if is_video(state_manager.get_item('target_path')) and has_lip_syncer:
		return gradio.Dropdown(visible = True)
	return gradio.Dropdown(visible = False)


def update_voice_extractor_model(voice_extractor_model : VoiceExtractorModel) -> gradio.Dropdown:
	voice_extractor.clear_inference_pool()
	state_manager.set_item('voice_extractor_model', voice_extractor_model)

	if voice_extractor.pre_check():
		gradio.Dropdown(value = state_manager.get_item('voice_extractor_model'))
	return gradio.Dropdown()
