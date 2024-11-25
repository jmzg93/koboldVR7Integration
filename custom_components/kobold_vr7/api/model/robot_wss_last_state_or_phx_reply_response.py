from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class AutonomyStates:
  active_cleaning_after_suspended: int
  active_cleaning_session: int
  cleaning_start: int
  docking: int
  docking_for_suspended: int
  docking_successful: int
  docking_successful_suspended: int
  docking_verify_base: int
  started_on_base: bool
  suspended_charging_start: int
  undocking: int
  undocking_after_suspended: int

@dataclass
class AvailableCommands:
  cancel: bool
  extract: bool
  pause: bool
  resume: bool
  return_to_base: bool
  start: bool

@dataclass
class CleaningCenter:
  bag_status: Optional[str]
  base_error: Optional[str]
  state: Optional[str]

@dataclass
class Details:
  base_type: str
  charge: int
  is_charging: bool
  is_docked: bool
  is_quickboost: bool
  quickboost_estimate: int

@dataclass
class Error:
  code: str
  severity: str

@dataclass
class ResponseBody:
  action: str
  autonomy_states: AutonomyStates
  available_commands: AvailableCommands
  cleaning_center: CleaningCenter
  details: Details
  errors: Optional[List[Error]]
  state: str

@dataclass
class WebSocketResponse:
  status: str
  response: Dict[str, any]