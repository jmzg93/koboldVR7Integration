"""Sensores auxiliares para la integración Kobold VR7."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.icon import icon_for_battery_level

from .api.robots_api_client import RobotsApiClient
from .const import CONF_ID_TOKEN, DOMAIN, ORBITAL_HOST, SIGNAL_ROBOT_BATTERY
from .service.robot_service import RobotsService

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Configura los sensores asociados a una entrada de la integración."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    config = entry_data["config"]
    runtime = entry_data.setdefault("runtime", {})

    id_token = config[CONF_ID_TOKEN]

    robots_service: RobotsService | None = runtime.get("robots_service")
    if not robots_service:
        session = async_get_clientsession(hass)
        robots_api_client = RobotsApiClient(session, token=id_token, host=ORBITAL_HOST)
        robots_service = RobotsService(robots_api_client)
        runtime["robots_service"] = robots_service

    robots_state: dict[str, dict[str, Any]] = runtime.setdefault("robots", {})

    if not robots_state:
        robots = await robots_service.get_all_robots(id_token)
        for robot in robots:
            estado_robot = robots_state.setdefault(robot.id, {})
            estado_robot["robot"] = robot
            estado_robot.setdefault("battery_level", None)
            estado_robot.setdefault("is_charging", False)

    sensores = []
    for robot_id, estado_robot in robots_state.items():
        robot = estado_robot.get("robot")
        if robot is None:
            _LOGGER.debug("Omitiendo sensor de batería para robot %s sin datos", robot_id)
            continue
        sensores.append(
            KoboldBatterySensor(hass, robot, estado_robot)
        )

    if sensores:
        async_add_entities(sensores)


class KoboldBatterySensor(SensorEntity):
    """Sensor de batería separado para los robots Kobold."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, robot, estado_robot: dict[str, Any]):
        """Inicializa el sensor de batería."""
        self.hass = hass
        self._robot = robot
        self._robot_state = estado_robot
        self._is_charging = estado_robot.get("is_charging", False)

        self._attr_unique_id = f"{robot.id}_battery"
        # Nombre del sensor sin repetir el nombre del robot porque Home Assistant
        # añadirá automáticamente el nombre del dispositivo cuando
        # ``_attr_has_entity_name`` es verdadero.
        self._attr_name = "Batería"
        self._attr_native_value = estado_robot.get("battery_level")

        self._actualizar_icono()

    async def async_added_to_hass(self):
        """Se suscribe a las actualizaciones del robot al añadirse al sistema."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_ROBOT_BATTERY}_{self._robot.id}",
                self._procesar_actualizacion_bateria,
            )
        )

    def _procesar_actualizacion_bateria(self, nivel: int | None, cargando: bool):
        """Programa una actualización segura para el hilo principal."""
        self.hass.loop.call_soon_threadsafe(
            self._actualizar_estado_desde_evento,
            nivel,
            cargando,
        )

    @callback
    def _actualizar_estado_desde_evento(
        self, nivel: int | None, cargando: bool
    ) -> None:
        """Actualiza el estado de la batería en el bucle de eventos."""
        self._robot_state["battery_level"] = nivel
        self._robot_state["is_charging"] = cargando
        self._attr_native_value = nivel
        self._is_charging = cargando
        self._actualizar_icono()
        self.async_write_ha_state()

    def _actualizar_icono(self):
        """Establece el icono adecuado según el estado de la batería."""
        nivel = self._attr_native_value
        if nivel is None:
            self._attr_icon = "mdi:battery-unknown"
        elif self._is_charging:
            self._attr_icon = "mdi:battery-charging"
        else:
            self._attr_icon = icon_for_battery_level(nivel)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Devuelve atributos adicionales del sensor."""
        return {"cargando": self._is_charging}

    @property
    def device_info(self) -> DeviceInfo:
        """Enlaza el sensor con el dispositivo principal de la aspiradora."""
        identificador = self._robot.serial or self._robot.id
        fabricante = getattr(self._robot, 'vendor', None) or "Kobold"
        return DeviceInfo(
            identifiers={(DOMAIN, identificador)},
            manufacturer=fabricante,
            model=getattr(self._robot, 'model_name', None),
            name=self._robot.name,
            sw_version=getattr(self._robot, 'firmware', None),
        )
