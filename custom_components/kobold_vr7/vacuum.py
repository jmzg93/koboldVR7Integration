import asyncio
import logging
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
    VacuumActivity,
)

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .service.model.map_with_zones import MapWithZones
from .service.websocket_service import WebSocketService
from .const import DOMAIN, CONF_EMAIL, CONF_ID_TOKEN
from .service.robot_service import RobotsService
from .api.robots_api_client import RobotsApiClient
from .api.websocket_client import KoboldWebSocketClient
from .const import ORBITAL_HOST

_LOGGER = logging.getLogger(__name__)


SERVICE_CLEAN_ZONE = 'clean_zone'
SERVICE_CLEAN_MAP = 'clean_map'


async def async_setup_entry(hass, entry, async_add_entities):
    """Configura la entidad de aspiradora basada en una entrada de configuración."""
    data = hass.data[DOMAIN][entry.entry_id]
    email = data[CONF_EMAIL]
    id_token = data[CONF_ID_TOKEN]

    # Usar la función importada directamente
    session = async_get_clientsession(hass)
    robots_api_client = RobotsApiClient(
        session, token=id_token, host=ORBITAL_HOST
    )
    robots_service = RobotsService(robots_api_client)

    # Obtener los robots
    robots = await robots_service.get_all_robots(id_token)

    entities = []

    for robot in robots:
        map_with_zones_list = []  # Lista para almacenar MapWithZones (específica para cada robot)
        
        # Intentamos obtener mapas, pero continuamos incluso si no hay ninguno
        maps = await robots_service.get_robot_map(id_token, robot.id)
        
        if maps:
            for robot_map in maps:
                # Obtener las zonas para cada mapa
                try:
                    zones = await robots_service.get_zones_by_floor_plan(id_token, robot_map.floorplan_uuid)
                    # Crear el objeto MapWithZones y agregarlo a la lista
                    map_with_zones = MapWithZones(map=robot_map, zones=zones)
                    map_with_zones_list.append(map_with_zones)
                except Exception as e:
                    _LOGGER.warning(f"Error getting zones for map {robot_map.floorplan_uuid}: {e}")
                    # Agregar el mapa sin zonas
                    map_with_zones = MapWithZones(map=robot_map, zones=None)
                    map_with_zones_list.append(map_with_zones)
        else:
            _LOGGER.info(f"No maps found for robot {robot.id}, continuing without maps")
            
        # Siempre añadimos la entidad, incluso sin mapas o zonas
        entities.append(KoboldVacuumEntity(
            hass, robot, robots_service, id_token, map_with_zones_list))

    async_add_entities(entities, update_before_add=True)

    # Registrar servicios personalizados después de haber añadido las entidades
    try:
        platform = entity_platform.async_get_current_platform()
        
        # Modificamos la forma de registrar servicios para evitar problemas de esquema
        platform.async_register_entity_service(
            SERVICE_CLEAN_ZONE,
            {
                vol.Required('zone_uuid'): cv.string,
            },
            'async_clean_zone'
        )

        platform.async_register_entity_service(
            SERVICE_CLEAN_MAP,
            {
                vol.Required('map_uuid'): cv.string,
            },
            'async_clean_map'
        )
        _LOGGER.debug("Successfully registered custom vacuum services")
    except Exception as e:
        _LOGGER.error(f"Error registering custom services: {e}")


class KoboldVacuumEntity(StateVacuumEntity):
    """Representa una aspiradora Kobold."""

    def __init__(self, hass, robot, robots_service, id_token, map_with_zones_list):
        self.hass = hass
        # Almacena los mapas y zonas del robot
        self.map_with_zones_list = map_with_zones_list
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
            | VacuumEntityFeature.STOP
            # | VacuumEntityFeature.CLEAN_SPOT
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.LOCATE
            | VacuumEntityFeature.MAP
        )

        # Por defecto, establecemos la actividad como IDLE
        self._attr_activity = VacuumActivity.IDLE
        self._attr_battery_level = None
        self._attr_status = None

        self._attr_fan_speed_list = ['auto', 'eco', 'turbo']
        self._attr_fan_speed = 'auto'

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
    def activity(self):
        """Devuelve la actividad actual de la aspiradora usando VacuumActivity."""
        return self._attr_activity

    @property
    def battery_level(self):
        """Devuelve el nivel de batería de la aspiradora."""
        return self._attr_battery_level

    @property
    def status(self):
        """Devuelve el estado detallado de la aspiradora."""
        if self._attr_activity == VacuumActivity.CLEANING and self.available_commands and self.available_commands.pause:
            return "Pausar"
        elif self._attr_activity == VacuumActivity.PAUSED and self.available_commands and self.available_commands.return_to_base:
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
    def fan_speed(self):
        """Devuelve los comandos disponibles para el robot."""
        return getattr(self, "_attr_fan_speed", 'auto')

    @property
    def bag_status(self):
        """Devuelve el estado de la bolsa de la aspiradora."""
        return getattr(self, "_attr_bag_status", None)

    @property
    def battery_icon(self):
        """Devuelve el icono de la batería según el estado de carga."""
        if self._attr_battery_level is not None:
            # Si el robot está cargando, usar un icono diferente
            # Esto debe derivarse de los datos WebSocket
            if getattr(self, "_is_charging", False):
                return "mdi:battery-charging"
            # De lo contrario, usar el icono predeterminado basado en el nivel de batería
            return icon_for_battery_level(self._attr_battery_level)
        return "mdi:battery-unknown"

    @property
    def extra_state_attributes(self):
        """Devuelve los atributos de estado adicionales de la aspiradora."""
        attributes = {}
        # Agregar información de mapas y zonas
        if self.map_with_zones_list:
            attributes['maps'] = [
                map_with_zones.map.floorplan_uuid for map_with_zones in self.map_with_zones_list]
            attributes['zones'] = {
                map_with_zones.map.floorplan_uuid: [
                    {'zone_uuid': zone.track_uuid, 'name': zone.name}
                    for zone in map_with_zones.zones
                ] for map_with_zones in self.map_with_zones_list
            }
        return attributes

    async def async_start(self):
        """Inicia o reanuda la limpieza sin mapas (limpieza general)."""
        if self.available_commands:
            if self.available_commands.start:
                # Iniciar limpieza sin un mapa específico (pasando None)
                await self._robots_service.start_cleaning(
                    self._id_token, self._robot.id, self.fan_speed, None
                )
            elif self.available_commands.resume:
                await self._robots_service.resume_cleaning(
                    self._id_token, self._robot.serial
                )
        else:
            _LOGGER.warning("Start command is not available for the robot.")

    async def async_locate(self):
        """Buscar el robot."""
        await self._robots_service.find_me(self._id_token, self._robot.serial)

    # async def async_clean_spot(self):
    #  _LOGGER.info("Start command is not available for the robot.")

    async def async_set_fan_speed(self, fan_speed: str):
        self._attr_fan_speed = fan_speed

    async def async_stop(self):
        """Detiene la limpieza."""
        if self.available_commands and self.available_commands.pause:
            await self._robots_service.pause_cleaning(self._id_token, self._robot.serial)
        else:
            _LOGGER.warning("Pause command is not available for the robot.")

    async def async_pause(self):
        """Pausa la limpieza."""
        if self.available_commands and self.available_commands.pause:
            await self._robots_service.pause_cleaning(self._id_token, self._robot.serial)
        else:
            _LOGGER.warning("Pause command is not available for the robot.")

    async def async_return_to_base(self, **kwargs):
        """Envía la aspiradora a la base."""
        if self.available_commands:
            if self.available_commands.return_to_base:
                await self._robots_service.send_to_base(self._id_token, self._robot.serial)
            elif self.available_commands.pause:
                await self._robots_service.pause_cleaning(self._id_token, self._robot.serial)
                await asyncio.sleep(2)
                await self._robots_service.send_to_base(self._id_token, self._robot.serial)
            else:
                _LOGGER.warning(
                    "Return to base command is not available for the robot.")
        else:
            _LOGGER.warning(
                "Return to base command is not available for the robot.")

    async def async_clean_zone(self, zone_uuid):
        """Inicia la limpieza de una zona específica."""
        if self.available_commands and self.available_commands.start:
            # Buscar el mapa y la zona correspondiente al zone_uuid
            for map_with_zones in self.map_with_zones_list:
                for zone in map_with_zones.zones:
                    if zone.track_uuid == zone_uuid:
                        # Iniciar la limpieza usando el mapa y la zona
                        await self._robots_service.start_cleaning(
                            self._id_token, self._robot.id, map_with_zones.map, [
                                zone]
                        )
                        return
            _LOGGER.warning(f"Zone with UUID {zone_uuid} not found.")
        else:
            _LOGGER.warning("Start command is not available for the robot.")

    async def async_clean_map(self, map_uuid):
        """Inicia la limpieza de un mapa específico."""
        if self.available_commands and self.available_commands.start:
            # Buscar el mapa correspondiente al map_uuid
            selected_map_with_zones = None
            
            for map_with_zones in self.map_with_zones_list:
                if map_with_zones.map.floorplan_uuid == map_uuid:
                    selected_map_with_zones = map_with_zones
                    break
                    
            if selected_map_with_zones:
                _LOGGER.info(f"Iniciando limpieza con mapa específico: {map_uuid}")
                # Iniciar la limpieza usando el mapa seleccionado
                await self._robots_service.start_cleaning(
                    self._id_token, self._robot.id, self.fan_speed, selected_map_with_zones
                )
            else:
                _LOGGER.warning(f"Map with UUID {map_uuid} not found.")
        else:
            _LOGGER.warning("Start command is not available for the robot.")
