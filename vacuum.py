import logging
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.components.vacuum import (
  StateVacuumEntity,
  VacuumEntityFeature,
  STATE_CLEANING,
  STATE_DOCKED,
  STATE_IDLE,
  STATE_PAUSED,
  STATE_RETURNING,
)

from .service.websocket_service import WebSocketService
from .const import DOMAIN, CONF_EMAIL, CONF_ID_TOKEN
from .service.robot_service import RobotsService
from .api.robots_api_client import RobotsApiClient
from .api.websocket_client import KoboldWebSocketClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
  """Configura la entidad de aspiradora basada en una entrada de configuración."""
  data = hass.data[DOMAIN][entry.entry_id]
  email = data[CONF_EMAIL]
  id_token = data[CONF_ID_TOKEN]

  session = hass.helpers.aiohttp_client.async_get_clientsession()
  robots_api_client = RobotsApiClient(
      session, token=id_token, host="https://orbital.ksecosys.com"
  )
  robots_service = RobotsService(robots_api_client)

  # Obtener los robots
  robots = await robots_service.get_all_robots(id_token)

  entities = []
  for robot in robots:
    map = await robots_service.get_robot_map(id_token, robot.id)
    entities.append(KoboldVacuumEntity(hass, robot, robots_service, id_token, map))

  async_add_entities(entities, update_before_add=True)

class KoboldVacuumEntity(StateVacuumEntity):
  """Representa una aspiradora Kobold."""

  def __init__(self, hass, robot, robots_service, id_token, default_map):
    self.hass = hass
    self.default_map = default_map
    self._robot = robot
    self._robots_service = robots_service
    self._id_token = id_token
    self._attr_name = robot.name
    self._attr_unique_id = robot.id
    self._attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATUS
    )

    self._attr_state = STATE_IDLE
    self._attr_battery_level = None
    self._attr_status = None

    # Inicializar el servicio WebSocket y pasar self como entidad

    self.websocket_service = WebSocketService(
        KoboldWebSocketClient(hass, id_token, robot.id, self)
    )


  async def async_added_to_hass(self):
    """Se llama cuando la entidad ha sido agregada a hass."""
    # Llamar al método de la clase base
    await super().async_added_to_hass()
    # Iniciar el cliente WebSocket
    self.hass.loop.create_task(self.websocket_service.start())

  async def async_will_remove_from_hass(self):
    """Se llama cuando la entidad está a punto de ser removida."""
    await self.websocket_service.stop()
    await super().async_will_remove_from_hass()

  @property
  def state(self):
    """Devuelve el estado actual de la aspiradora."""
    return self._attr_state

  @property
  def battery_level(self):
    """Devuelve el nivel de batería de la aspiradora."""
    return self._attr_battery_level

  @property
  def status(self):
    """Devuelve el estado detallado de la aspiradora."""
    if self._attr_state == STATE_CLEANING and self.available_commands.pause:
      return "Pausar"
    elif self._attr_state == STATE_PAUSED and self.available_commands.return_to_base:
      return "Enviar a la Base"
    return self._attr_status

  @property
  def icon(self):
    """Define el icono predeterminado de la aspiradora."""
    return "mdi:robot-vacuum-variant"

  @property
  def available_commands(self):
    """Devuelve los comandos disponibles para el robot."""
    return getattr(self, "_attr_available_commands", None)

  @property
  def bag_status(self):
    """Devuelve el estado de la bolsa de la aspiradora."""
    return getattr(self, "_attr_bag_status", None)

  @property
  def battery_icon(self):
    """Devuelve el icono de la batería según el estado de carga."""
    if self._attr_battery_level is not None:
      # Si el robot está cargando, usar un icono diferente
      if getattr(self, "_is_charging", False):  # Esto debe derivarse de los datos WebSocket
        return "mdi:battery-charging"
      # De lo contrario, usar el icono predeterminado basado en el nivel de batería
      return icon_for_battery_level(self._attr_battery_level)
    return "mdi:battery-unknown"


  async def async_start(self):
    """Inicia o reanuda la limpieza."""
    if self.available_commands and (self.available_commands.start or self.available_commands.resume):
      await self._robots_service.start_cleaning(
          self._id_token, self._robot.id, self.default_map
      )
    else:
      _LOGGER.warning("Start command is not available for the robot.")

  async def async_pause(self):
    """Pausa la limpieza."""
    if self.available_commands and self.available_commands.pause:
      await self._robots_service.pause_cleaning(self._id_token, self._robot.serial)
    else:
      _LOGGER.warning("Pause command is not available for the robot.")

  async def async_return_to_base(self, **kwargs):
    """Envía la aspiradora a la base."""
    if self.available_commands and self.available_commands.return_to_base:
      await self._robots_service.send_to_base(self._id_token, self._robot.serial)
    else:
      _LOGGER.warning("Return to base command is not available for the robot.")

async def async_update(self):
  """Actualiza el estado de la aspiradora."""
  try:
    status = await self._robots_service.get_status(self._id_token, self._robot.serial)
    # Actualiza self._state según el status recibido
    if status:
      self._battery_level = status.get("battery_level", self._battery_level)
      self._status = status.get("status", self._status)
      robot_state = status.get("state", "idle")

      if robot_state == "cleaning":
        self._state = STATE_CLEANING
      elif robot_state == "paused":
        self._state = STATE_PAUSED
      elif robot_state == "docked":
        self._state = STATE_DOCKED
      elif robot_state == "returning":
        self._state = STATE_RETURNING
      else:
        self._state = STATE_IDLE
    else:
      self._state = STATE_IDLE
  except Exception as e:
    if "503" in str(e):
      _LOGGER.debug("Robot is not in a state to provide status. Skipping update.")
    else:
      _LOGGER.warning("Failed to update status via API: %s", e)