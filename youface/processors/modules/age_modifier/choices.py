from typing import List, Sequence, get_args

from youface.common_helper import create_int_range
from youface.processors.modules.age_modifier.types import AgeModifierModel

age_modifier_models : List[AgeModifierModel] = list(get_args(AgeModifierModel))

age_modifier_direction_range : Sequence[int] = create_int_range(-100, 100, 1)
