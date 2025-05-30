from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class MapDetails:
    floorplan_uuid: str
    zone_uuid: Optional[str] = None  # Puede ser None si no es necesario
    nogo_enabled: Optional[bool] = None

    def to_dict(self) -> dict:
        """Convierte la clase MapDetails en un diccionario."""
        return asdict(self)


@dataclass
class RunSettings:
    """Posibles valores son eco, turbo o auto"""
    mode: str
    navigation_mode: str

    def to_dict(self) -> dict:
        """Convierte la clase RunSettings en un diccionario."""
        return asdict(self)


class Run:
    def __init__(self, settings: RunSettings, map: MapDetails = None):
        self.settings = settings
        self.map = map

    def to_dict(self) -> dict:
        """Convierte la clase Run en un diccionario."""
        return {
            "settings": self.settings.to_dict(),  # Convierte RunSettings
            "map": self.map.to_dict() if self.map else None,  # Convierte MapDetails si existe
        }


@dataclass
class CleaningStartRequest:
    runs: List[Run]

    def to_dict(self) -> dict:
        """Convierte la clase CleaningStartRequest en un diccionario."""
        return {
            "runs": [run.to_dict() for run in self.runs]  # Convierte cada Run
        }
