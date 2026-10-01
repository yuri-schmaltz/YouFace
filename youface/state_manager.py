import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Union

from youface.app_context import detect_app_context
from youface.processors.types import ProcessorState, ProcessorStateKey, ProcessorStateSet
from youface.types import State, StateKey, StateSet

_STATE_LOCK = threading.RLock()

STATE_SET : Union[StateSet, ProcessorStateSet] =\
{
	'cli': {}, #type:ignore[assignment]
	'ui': {} #type:ignore[assignment]
}


def get_state() -> Union[State, ProcessorState]:
	with _STATE_LOCK:
		app_context = detect_app_context()
		return STATE_SET.get(app_context)


def sync_state() -> None:
	with _STATE_LOCK:
		STATE_SET['cli'] = STATE_SET.get('ui') #type:ignore[assignment]


def init_item(key : Union[StateKey, ProcessorStateKey], value : Any) -> None:
	with _STATE_LOCK:
		STATE_SET['cli'][key] = value #type:ignore[literal-required]
		STATE_SET['ui'][key] = value #type:ignore[literal-required]


def get_item(key : Union[StateKey, ProcessorStateKey]) -> Any:
	with _STATE_LOCK:
		state = get_state()
		if state is not None:
			return state.get(key) #type:ignore[literal-required]
		return None


def set_item(key : Union[StateKey, ProcessorStateKey], value : Any) -> None:
	with _STATE_LOCK:
		app_context = detect_app_context()
		if app_context in STATE_SET:
			STATE_SET[app_context][key] = value #type:ignore[literal-required]


def sync_item(key : Union[StateKey, ProcessorStateKey]) -> None:
	with _STATE_LOCK:
		STATE_SET['cli'][key] = STATE_SET.get('ui').get(key) #type:ignore[literal-required]


def clear_item(key : Union[StateKey, ProcessorStateKey]) -> None:
	set_item(key, None)


@contextmanager
def temporary_state(overrides: Dict[Union[StateKey, ProcessorStateKey], Any]) -> Iterator[None]:
	"""
	Thread-safe context manager to temporarily apply configuration overrides,
	restoring previous values on exit even if an exception occurs.
	"""
	with _STATE_LOCK:
		original_values: Dict[Union[StateKey, ProcessorStateKey], Any] = {}
		for key in overrides:
			original_values[key] = get_item(key)
		try:
			for key, val in overrides.items():
				set_item(key, val)
			yield
		finally:
			for key, val in original_values.items():
				set_item(key, val)
