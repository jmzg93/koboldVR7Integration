import logging
from typing import Optional

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
      logging.error("Failed to %s identifier %s", action_description, identifier, exc_info=True)
      raise UserDataServiceException("Failed to " + action_description % identifier) from e
    else:
      logging.error("Failed to %s", action_description, exc_info=True)
      raise UserDataServiceException("Failed to " + action_description) from e


class RobotsService:
  def __init__(self, robots_api_client):
    self.robots_api_client = robots_api_client

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

  async def get_robot_map(self, token, robot_id) -> Optional[RobotMapResponse]:
    """
    Obtiene el primer mapa de la lista de mapas para el robot especificado.

    Args:
        token (str): Token de autenticación.
        robot_id (str): ID del robot.

    Returns:
        Optional[RobotMapResponse]: El primer mapa del robot o None si no hay mapas disponibles.
    """
    try:
      maps = await execute(
          self.robots_api_client.get_robot_maps(robot_id),
          "get robot map for robot %s",
          robot_id
      )
      if maps:
        # Verificar que la lista no esté vacía y devolver el primer elemento
        return maps[0]
      else:
        # Retorna None si no hay mapas disponibles
        return None
    except Exception as e:
      _LOGGER.error("Error retrieving robot maps for robot %s: %s", robot_id, e)
      return None

  async def get_recent_cleaning_maps(self, token, robot_id):
    return await execute(
        self.robots_api_client.get_recent_cleaning_maps(robot_id),
        "get recent cleaning maps for robot %s",
        robot_id
    )

  async def get_zones_by_floor_plan(self, token, floorplan_uuid):
    return await execute(
        self.robots_api_client.get_zones_by_floor_plan(floorplan_uuid),
        "get zones by floorplan %s",
        floorplan_uuid
    )

  async def start_cleaning(self, token, robot_id, default_map):
    global floor_plan_uuid
    if default_map is not None:
      # Extraemos el floorplan_uuid del default_map
      floor_plan_uuid = default_map.floorplan_uuid if default_map else None


    cleaning_request = CleaningStartRequest(
        runs=[
          Run(
              settings=RunSettings(mode="auto", navigation_mode="normal"),
              map=MapDetails(
                  floorplan_uuid=floor_plan_uuid,
                  zone_uuid=None,
                  nogo_enabled=True
              )
          )
        ]
    )

    # Llamamos al API client con el payload generado
    return await execute(
        self.robots_api_client.start_cleaning(robot_id, cleaning_request),
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

