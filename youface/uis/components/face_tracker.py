from typing import Optional

import gradio

import youface.choices
from youface import state_manager, translator
from youface.common_helper import calculate_float_step
from youface.types import Score
from youface.uis.core import register_ui_component

FACE_TRACKER_SCORE_SLIDER : Optional[gradio.Slider] = None


def render() -> None:
	global FACE_TRACKER_SCORE_SLIDER

	FACE_TRACKER_SCORE_SLIDER = gradio.Slider(
		label = translator.get('uis.face_tracker_score_slider'),
		value = state_manager.get_item('face_tracker_score'),
		step = calculate_float_step(youface.choices.face_tracker_score_range),
		minimum = youface.choices.face_tracker_score_range[0],
		maximum = youface.choices.face_tracker_score_range[-1]
	)
	register_ui_component('face_tracker_score_slider', FACE_TRACKER_SCORE_SLIDER)


def listen() -> None:
	FACE_TRACKER_SCORE_SLIDER.release(update_face_tracker_score, inputs = FACE_TRACKER_SCORE_SLIDER)


def update_face_tracker_score(face_tracker_score : Score) -> None:
	state_manager.set_item('face_tracker_score', face_tracker_score)
