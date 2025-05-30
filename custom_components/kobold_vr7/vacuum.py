import asyncio
import logging
from typing import AnyStr, Any

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
                vol.Required('zones_uuid'): cv.string,
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
        attributes: dict[str, Any] = {}

        if self.map_with_zones_list:
            # 1) map_names: map_id → map_name
            attributes['maps'] = {}
            # 2) zones: map_name → lista de zonas
            attributes['zones'] = {}

            for mwz in self.map_with_zones_list:
                mapa = mwz.map
                # solo si existe floorplan_uuid y nombre
                if not (mapa and hasattr(mapa, 'floorplan_uuid') and getattr(mapa, 'name', None)):
                    continue

                map_id = mapa.floorplan_uuid
                map_name = mapa.name

                # 1) relleno map_names
                attributes['maps'][map_id] = map_name

                # 2) relleno zones bajo map_name
                zone_list: list[dict[str, Any]] = []
                for zone in getattr(mwz, 'zones', []) or []:
                    z = {'zone_uuid': zone.track_uuid}
                    if hasattr(zone, 'name'):
                        z['name'] = zone.name
                    zone_list.append(z)

                attributes['zones'][map_name] = zone_list

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



    async def async_clean_zone(self, zones_uuid):
        """Inicia la limpieza de una o varias zonas específicas."""
        if self.available_commands and self.available_commands.start:
            # Convertir zone_uuid en una lista si es un string
            zone_uuids = [zones_uuid.strip() for zones_uuid in zones_uuid.split(',')] if isinstance(zones_uuid, str) else [zones_uuid]
            
            # Verificar que tenemos al menos una zona
            if not zone_uuids:
                _LOGGER.error("No se especificó ninguna zona para limpiar")
                return
                
            # Buscar las zonas y verificar que pertenezcan al mismo mapa
            found_zones = []
            parent_map = None
            
            for map_with_zones in self.map_with_zones_list:
                if not map_with_zones.zones:
                    continue
                    
                # Verificamos las zonas de este mapa
                for zone in map_with_zones.zones:
                    if zone.track_uuid in zone_uuids:
                        if parent_map is None:
                            # Primera zona encontrada, establecemos el mapa padre
                            parent_map = map_with_zones.map
                            found_zones.append(zone)
                        elif parent_map.floorplan_uuid == map_with_zones.map.floorplan_uuid:
                            # La zona es del mismo mapa, la agregamos
                            found_zones.append(zone)
                        else:
                            # La zona pertenece a otro mapa, lo reportamos como error
                            _LOGGER.error(
                                f"La zona {zone.track_uuid} pertenece a un mapa diferente. "
                                f"Todas las zonas deben pertenecer al mismo mapa."
                            )
            
            # Verificar si encontramos al menos una zona
            if not found_zones:
                _LOGGER.warning(f"No se encontraron las zonas con UUID: {zone_uuids}")
                return
                
            # Verificar si hay zonas que no se encontraron
            found_uuids = [zone.track_uuid for zone in found_zones]
            missing_uuids = [uuid for uuid in zone_uuids if uuid not in found_uuids]
            if missing_uuids:
                _LOGGER.warning(f"No se encontraron las siguientes zonas: {missing_uuids}")
            
            # Iniciar la limpieza con las zonas encontradas
            if parent_map and found_zones:
                _LOGGER.info(f"Iniciando limpieza de {len(found_zones)} zonas en el mapa {parent_map.name}")
                await self._robots_service.start_cleaning(
                    self._id_token, self._robot.id, self.fan_speed, 
                    MapWithZones(map=parent_map, zones=found_zones)
                )
        else:
            _LOGGER.warning("El comando de inicio no está disponible para el robot.")


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
                    self._id_token, self._robot.id, self.fan_speed, MapWithZones(map=selected_map_with_zones.map, zones=None)
                )
            else:
                _LOGGER.warning(f"Map with UUID {map_uuid} not found.")
        else:
            _LOGGER.warning("Start command is not available for the robot.")
