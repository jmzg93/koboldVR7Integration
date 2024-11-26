from dataclasses import dataclass
from typing import List


@dataclass
class Timing:
    charging: int
    end: str
    error: int
    paused: int
    start: str


@dataclass
class Settings:
    mode: str
    navigation_mode: str


@dataclass
class Stats:
    area: float
    pickup_count: int


@dataclass
class Run:
    settings: Settings
    state: str
    stats: Stats
    timing: Timing
    track_name: str
    track_uuid: str


@dataclass
class CleaningShowResponse:
    ability: str
    cleaning_type: str
    floorplan_uuid: str
    runs: List[Run]
    started_by: str
    timing: Timing
