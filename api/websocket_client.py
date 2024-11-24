import asyncio
import logging
from typing import Dict

import websockets
from websockets.exceptions import ConnectionClosed
import json
import uuid

from .model.robot_wss_cleaning_state_response import CleaningStateResponse, \
  RunSettings, RunStats, RunTiming, Run, CleaningStateBody
from .model.robot_wss_last_state_or_phx_reply_response import AutonomyStates, AvailableCommands, \
  CleaningCenter, Details, Error, ResponseBody

from homeassistant.components.vacuum import (
  STATE_CLEANING,
  STATE_DOCKED,
  STATE_IDLE,
  STATE_PAUSED,
  STATE_RETURNING,
)

_LOGGER = logging.getLogger(__name__)

class KoboldWebSocketClient:
  def __init__(self, hass, token, robot_id, entity):
    self.hass = hass
    self.token = token
    self.robot_id = robot_id
    self.entity = entity  # Agrega la entidad aquí
    self.websocket = None
    self.connected = False
    self._url = f"wss://orbital.ksecosys.com/socket/websocket?vsn=2.0.0&token={self.token}&vendor=vorwerk"
    self._listen_task = None

  async def connect(self):
    try:
      self.websocket = await websockets.connect(self._url)
      self.connected = True
      _LOGGER.debug("Connected to WebSocket")
      await self._join_robot_channel()
      self._listen_task = self.hass.loop.create_task(self._listen())
    except Exception as e:
      _LOGGER.error("Error connecting to WebSocket: %s", e)
      self.connected = False

  async def _join_robot_channel(self):
    # Enviar mensaje para unirse al canal del robot
    join_msg = [
      "6",
      "6",
      f"robots:{self.robot_id}",
      "phx_join",
      {}
    ]
    await self.websocket.send(json.dumps(join_msg))

    unique_request_id = str(uuid.uuid4())
    # Enviar mensaje para solicitar el último estado
    last_state_msg = [
      "6",
      "8",
      f"robots:{self.robot_id}",
      "last_state",
      {"request_id": unique_request_id}
    ]
    await self.websocket.send(json.dumps(last_state_msg))

  async def _listen(self):
    try:
      async for message in self.websocket:
        await self._handle_message(message)
    except ConnectionClosed:
      _LOGGER.warning("WebSocket connection closed")
      self.connected = False
      # Intentar reconectar
      await self.connect()

  async def _handle_message(self, message):
    _LOGGER.debug("Received message: %s", message)
    data = json.loads(message)

    # Verificar que el mensaje es una lista con al menos 5 elementos
    if isinstance(data, list) and len(data) >= 5:
      topic = data[2]
      event = data[3]
      payload = data[4]

      # Manejar el evento phx_reply
      if event == "phx_reply":
        await self._handle_phx_reply(payload)
      elif event == "last_state":
        await self._handle_last_state(payload)
      elif event == "cleaning_state":
        await self._handle_cleaning_state(payload)
      else:
        _LOGGER.debug("Unhandled event: %s", event)
    else:
      _LOGGER.error("Invalid message format")


  async def _handle_phx_reply(self, payload):
    if "response" in payload and "body" in payload["response"]:
      response = payload["response"]
      body = response["body"]
      try:
        response_body = self._parse_response_body(body)
        await self.update_entity_state(response_body)
      except Exception as e:
        _LOGGER.error("Error parsing phx_reply response body: %s", e)
    else:
      _LOGGER.debug("phx_reply without body")

  async def _handle_last_state(self, payload):
    if "body" in payload:
      body = payload["body"]
      try:
        response_body = self._parse_response_body(body)
        await self.update_entity_state(response_body)
      except Exception as e:
        _LOGGER.error("Error parsing last_state body: %s", e)
    else:
      _LOGGER.debug("last_state without body")

  async def _handle_cleaning_state(self, payload):
    if "body" in payload:
      body = payload["body"]
      try:
        cleaning_state_response = self._parse_cleaning_state_body(payload)
        await self.update_cleaning_state(cleaning_state_response)
      except Exception as e:
        _LOGGER.error("Error parsing cleaning_state body: %s", e)
    else:
      _LOGGER.debug("cleaning_state without body")


  def _parse_response_body(self, body: Dict) -> ResponseBody:
    autonomy_states = AutonomyStates(**body["autonomy_states"])
    available_commands = AvailableCommands(**body["available_commands"])
    cleaning_center = CleaningCenter(**body["cleaning_center"])
    details = Details(**body["details"])
    errors = None
    if body.get("errors"):
      errors = [Error(**error) for error in body["errors"]]

    response_body = ResponseBody(
        action=body["action"],
        autonomy_states=autonomy_states,
        available_commands=available_commands,
        cleaning_center=cleaning_center,
        details=details,
        errors=errors,
        state=body["state"]
    )
    return response_body

  def _parse_cleaning_state_body(self, payload: Dict) -> CleaningStateResponse:
    code = payload["code"]
    body = payload["body"]
    runs = []
    for run_data in body["runs"]:
      settings = RunSettings(**run_data["settings"])
      stats = RunStats(**run_data["stats"])
      timing = RunTiming(**run_data["timing"])
      run = Run(
          settings=settings,
          state=run_data["state"],
          stats=stats,
          timing=timing,
          track_name=run_data.get("track_name"),
          track_uuid=run_data.get("track_uuid")
      )
      runs.append(run)

    timing = RunTiming(**body["timing"])

    cleaning_state_body = CleaningStateBody(
        ability=body["ability"],
        cleaning_type=body["cleaning_type"],
        floorplan_uuid=body.get("floorplan_uuid"),
        runs=runs,
        started_by=body["started_by"],
        timing=timing
    )

    return CleaningStateResponse(code=code, body=cleaning_state_body)




  async def update_entity_state(self, response_body: ResponseBody):
    """Actualiza el estado de la entidad basado en los datos de ResponseBody."""
    action = response_body.action
    state = response_body.state

    if state == "busy" and action == "cleaning":
      ha_state = STATE_CLEANING
    elif state == "idle":
      ha_state = STATE_IDLE
    elif action == "cleaning" and state == "paused":
      ha_state = STATE_PAUSED
    elif action == "cleaning" and state == "docked":
      ha_state = STATE_DOCKED
    else:
      ha_state = STATE_IDLE

    # Actualizar la entidad
    self.entity._attr_state = ha_state
    self.entity._attr_battery_level = response_body.details.charge
    self.entity._attr_status = action

    # Confirmar los cambios de estado a Home Assistant
    self.entity.async_write_ha_state()
    _LOGGER.debug("Entity state updated in Home Assistant with state: %s", ha_state)

  async def disconnect(self):
    if self.websocket:
      await self.websocket.close()
    if self._listen_task:
      self._listen_task.cancel()
    self.connected = False