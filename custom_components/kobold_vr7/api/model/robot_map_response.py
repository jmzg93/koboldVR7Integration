from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MapDimensions:
    height: int
    width: int
    resolution: int


@dataclass
class Position:
    dir: float
    x: int
    y: int


@dataclass
class RobotPosition:
    base: Position
    pos: Position


@dataclass
class CropDimensions:
    bottom: int
    left: int
    right: int
    top: int
    scale: float


@dataclass
class MapColors:
    coverage: str
    uncertain: str
    floor: str
    walls: str
    tof: str


@dataclass
class RobotMapResponse:
    default: bool
    name: str
    original: MapDimensions
    inserted_at: str
    updated_at: str
    floorplan_uuid: str
    promotable: bool
    promoted_at: Optional[str]
    rank_uuid: str
    started_by: str
    robot: RobotPosition
    real_crop: CropDimensions
    rank_crop: CropDimensions    
    processed_real_binary: str
    processed_rank_binary: str
    map_colors: MapColors
    processed_thumb_rank_binary: str = field(default=None, repr=False)  # No aparecerá en logs
    last_modified_at: Optional[str] = None
    map_versions_count: Optional[int] = None
