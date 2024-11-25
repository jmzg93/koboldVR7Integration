from dataclasses import dataclass
from typing import Optional

@dataclass
class RobotResponse:
  id: str
  name: str
  serial: str
  user_id: str
  timezone: str
  vendor: str
  firmware: str
  model_name: str
  birth_date: str
  mac_address: Optional[str] = None  # Si puede ser None, usa Optional