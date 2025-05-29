import logging
from typing import Optional, List

from ..api.model.register_device_response import RegisterDeviceResponse
from ..api.model.robot_map_zones import CleaningTracksResponse
from ..api.model.cleaning_start_request import RunSettings, MapDetails, Run
from ..api.model.cleaning_start_request import CleaningStartRequest
from ..api.model.robot_map_response import RobotMapResponse

_LOGGER = logging.getLogger(__name__)


class UserDataServiceException(Exception):
    pass


async def execute(action_coro, action_description, identifier):
    try:
        if identifier is not None:
            logging.debug(action_description, identifier)
        else:
            logging.debug(action_description)
        return await action_coro
    except Exception as e:
        if identifier is not None:
            logging.error("Failed to %s identifier %s",
                          action_description, identifier, exc_info=True)
            raise UserDataServiceException(
                "Failed to " + action_description % identifier) from e

        logging.error("Failed to %s", action_description, exc_info=True)
        raise UserDataServiceException(
            "Failed to " + action_description) from e


class RobotsService:
    def __init__(self, robots_api_client):
        self.robots_api_client = robots_api_client

    async def register_device(self, token) -> RegisterDeviceResponse:
        return await execute(
            self.robots_api_client.register_device(),
            "register device",
            None
        )

    async def get_all_robots(self, token):
        return await execute(
            self.robots_api_client.get_user_robots(),
            "get all robots",
            None
        )

    async def get_cleaning_mode_by_robot_id(self, token, robot_id):
        return await execute(
            self.robots_api_client.get_cleaning_modes(robot_id),
            "get cleaning modes for robot %s",
            robot_id
        )

    async def get_robot_map(self, token, robot_id) -> Optional[List[RobotMapResponse]]:
        return await execute(
            self.robots_api_client.get_robot_maps(robot_id),
            "get robot map for robot %s",
            robot_id
        )

    async def get_recent_cleaning_maps(self, token, robot_id):
        return await execute(
            self.robots_api_client.get_recent_cleaning_maps(robot_id),
            "get recent cleaning maps for robot %s",
            robot_id
        )

    async def get_zones_by_floor_plan(self, token, floorplan_uuid) -> Optional[List[CleaningTracksResponse]]:
        return await execute(
            self.robots_api_client.get_zones_by_floor_plan(floorplan_uuid),
            "get zones by floorplan %s",
            floorplan_uuid
        )

    async def start_cleaning(self, token, robot_id, fan_speed, map_with_zone):
        # Manejo específico para cuando no hay mapas (map_with_zone es None)
        if map_with_zone is None:
            # Para robots sin mapa, enviamos la propiedad 'map' como null
            runs = [
                {
                    "settings": {
                        "mode": fan_speed,
                        "navigation_mode": "normal"
                    },
                    "map": None
                }
            ]
            
            # Crear la solicitud de limpieza directamente como un diccionario
            cleaning_request = {"runs": runs, "ability": "cleaning.start"}
            
            # Enviar la solicitud
            return await execute(
                self.robots_api_client.start_cleaning(
                    robot_id, cleaning_request),
                "start cleaning for robot %s",
                robot_id
            )
        
        # Continúa con el caso original cuando hay mapas

        else:
            # Extraemos el floorplan_uuid del mapa
            floor_plan_uuid = (
                map_with_zone.map.floorplan_uuid
                if map_with_zone.map and hasattr(map_with_zone.map, 'floorplan_uuid')
                else None
            )

            # Si no hay floorplan_uuid, no podemos continuar
            if floor_plan_uuid is None:
                raise UserDataServiceException(
                    f"Cannot start cleaning: no floorplan_uuid available for robot {robot_id}"
                )

            runs = []

            # Si tenemos zonas, creamos un Run por cada zona
            if hasattr(map_with_zone, 'zones') and map_with_zone.zones:
                for zone in map_with_zone.zones:
                    run = {
                        "settings": {
                            "mode": fan_speed,
                            "navigation_mode": "normal"
                        },
                        "map": {
                            "floorplan_uuid": floor_plan_uuid,
                            "zone_uuid": zone.track_uuid,
                            "nogo_enabled": True
                        }
                    }
                    runs.append(run)
            else:
                # Si no tenemos zonas, creamos un Run con el mapa pero sin zona específica
                runs = [
                    {
                        "settings": {
                            "mode": fan_speed,
                            "navigation_mode": "normal"
                        },
                        "map": {
                            "floorplan_uuid": floor_plan_uuid,
                            "zone_uuid": None,
                            "nogo_enabled": True
                        }
                    }
                ]
            
            # Crear la solicitud de limpieza directamente como un diccionario
            cleaning_request = {"runs": runs, "ability": "cleaning.start"}

            
            # Enviar la solicitud
            return await execute(
                self.robots_api_client.start_cleaning(
                    robot_id, cleaning_request),
                "start cleaning for robot %s",
                robot_id
            )

    async def send_to_base(self, token, robot_id):
        return await execute(
            self.robots_api_client.send_to_base(robot_id),
            "send to base for robot %s",
            robot_id
        )

    async def pause_cleaning(self, token, robot_id):
        return await execute(
            self.robots_api_client.pause_cleaning(robot_id),
            "pause cleaning for robot %s",
            robot_id
        )

    async def get_status(self, token, robot_id):
        return await execute(
            self.robots_api_client.show_cleaning(robot_id),
            "get status for robot %s",
            robot_id
        )

    async def resume_cleaning(self, token, robot_id):
        return await execute(
            self.robots_api_client.resume_clean(robot_id),
            "resume cleaning for robot %s",
            robot_id
        )

    async def find_me(self, token, robot_id):
        return await execute(
            self.robots_api_client.find_me(robot_id),
            "resume cleaning for robot %s",
            robot_id
        )
