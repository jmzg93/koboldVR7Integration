from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Shape:
  coordinates: List[List[int]]  # Una lista de puntos [x, y]

@dataclass
class CleaningTracksResponse:
  track_uuid: str
  name: str
  icon_id: str
  type: str  # Por ejemplo, "cleaning"
  shapes: List[Shape]  # Lista de formas que representa las áreas de limpieza
  binary: str  # Datos binarios del mapa codificados en base64
  cleaning_mode: str  # Por ejemplo, "auto"
  inserted_at: str  # Fecha en formato ISO 8601
  updated_at: str  # Fecha en formato ISO 8601