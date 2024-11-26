from dataclasses import dataclass
from typing import List


@dataclass
class CleaningModesResponse:
    max_floorplans: int
    max_cleaning_zones: int
    max_cleanable_zones: int
    max_no_go_zones: int
    extra_care_navigation: bool
    vacuuming_modes: List[str]
    reminders_enabled: bool
    object_avoidance: bool
    backup_and_restore: bool
    area_configuration: bool
    overhang_detection: bool
