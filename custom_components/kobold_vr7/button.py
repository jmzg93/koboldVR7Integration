"""Button entities for the Kobold VR7 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .api.model.robot_response import RobotResponse
from .api.robots_api_client import RobotsApiClient
from .const import (
    CONF_ID_TOKEN,
    DOMAIN,
    ORBITAL_HOST,
)
from .service.robot_service import RobotsService, UserDataServiceException


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the buttons."""
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
            robot_state = robots_state.setdefault(robot.id, {})
            robot_state["robot"] = robot

    buttons = [
        KoboldEmptyDustContainerButton(
            robot_state["robot"], robot_state, robots_service, id_token
        )
        for robot_state in robots_state.values()
        if robot_state.get("robot") is not None
    ]
    if buttons:
        async_add_entities(buttons)


class KoboldEmptyDustContainerButton(ButtonEntity):
    """Button that empties the robot dust container."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Empty dust container"
    _attr_icon = "mdi:delete-empty"

    def __init__(
        self,
        robot: RobotResponse,
        robot_state: dict[str, Any],
        robots_service: RobotsService,
        id_token: str,
    ) -> None:
        """Initialize the button."""
        self._robot = robot
        self._robot_state = robot_state
        self._robots_service = robots_service
        self._id_token = id_token
        self._attr_unique_id = f"{robot.id}_empty_dust_container"

    async def async_press(self) -> None:
        """Start emptying the dust container."""
        commands = self._robot_state.get("available_commands")
        if not (commands and commands.extract):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="extraction_not_available"
            )
        try:
            await self._robots_service.start_extraction(
                self._id_token, self._robot.serial
            )
        except UserDataServiceException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="extraction_failed"
            ) from err

    @property
    def device_info(self) -> DeviceInfo:
        """Attach the button to the vacuum device."""
        identifier = self._robot.serial or self._robot.id
        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=getattr(self._robot, "vendor", None) or "Kobold",
            model=getattr(self._robot, "model_name", None),
            name=self._robot.name,
            sw_version=getattr(self._robot, "firmware", None),
        )
