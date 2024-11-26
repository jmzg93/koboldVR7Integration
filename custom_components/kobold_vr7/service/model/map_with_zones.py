from dataclasses import dataclass
from typing import Optional

from ...api.model.robot_map_zones import CleaningTracksResponse
from ...api.model.robot_map_response import RobotMapResponse


@dataclass
class MapWithZones:
    map: Optional[RobotMapResponse] = None  # Valor por defecto como None
    # Valor por defecto como lista vacía
    zones: Optional[CleaningTracksResponse] = None
