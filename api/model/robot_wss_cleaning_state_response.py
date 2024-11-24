from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class RunSettings:
  mode: str
  navigation_mode: str

@dataclass
class RunStats:
  area: float
  pickup_count: int

@dataclass
class RunTiming:
  charging: int
  end: str
  error: int
  paused: int
  start: str

@dataclass
class Run:
  settings: RunSettings
  state: str
  stats: RunStats
  timing: RunTiming
  track_name: Optional[str]
  track_uuid: Optional[str]

@dataclass
class CleaningStateBody:
  ability: str
  cleaning_type: str
  floorplan_uuid: Optional[str]
  runs: List[Run]
  started_by: str
  timing: RunTiming

@dataclass
class CleaningStateResponse:
  code: int
  body: CleaningStateBody