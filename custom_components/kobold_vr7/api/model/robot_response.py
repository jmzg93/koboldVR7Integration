from dataclasses import dataclass, fields
from typing import Any, Dict, Optional


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RobotResponse":
        valid_fields = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in valid_fields})
