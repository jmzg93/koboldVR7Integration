import asyncio
import logging
import json
import uuid
import ssl
import os
from typing import Dict
import websockets
from websockets.client import connect as websockets_connect

from websockets.exceptions import ConnectionClosed
from .model.robot_wss_cleaning_state_response import CleaningStateResponse, \
    RunSettings, RunStats, RunTiming, Run, CleaningStateBody
from .model.robot_wss_last_state_or_phx_reply_response import AutonomyStates, AvailableCommands, \
    CleaningCenter, Details, Error, ResponseBody

from homeassistant.components.vacuum import VacuumActivity
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import DOMAIN, SIGNAL_ROBOT_BATTERY

_LOGGER = logging.getLogger(__name__)


def _parse_response_body(body: Dict) -> ResponseBody:
    """Parsea el cuerpo de la respuesta en un objeto ResponseBody."""
    autonomy_states_data = body.get("autonomy_states")
    autonomy_states = None
    if autonomy_states_data:  # Solo inicializa si autonomy_states no está vacío
        autonomy_states = AutonomyStates(**autonomy_states_data)

    # Valores por defecto para available_commands en caso de que falten
    available_commands_default = {
        "cancel": False,
        "extract": False,
        "pause": False,
        "resume": False,
        "return_to_base": False,
        "start": False
    }
    
    # Combinar valores por defecto con los recibidos (los recibidos tienen prioridad)
    available_commands_data = {**available_commands_default, **body.get("available_commands", {})}
    
    available_commands = AvailableCommands(**available_commands_data)

    # Añadir valores por defecto para cleaning_center para evitar el error de falta de parámetros
    cleaning_center_default = {
        "bag_status": None,
        "base_error": None,
        "state": None
    }
    
    # Combinar valores por defecto con los recibidos
    cleaning_center_data = {**cleaning_center_default, **body.get("cleaning_center", {})}
    
    cleaning_center = CleaningCenter(**cleaning_center_data)

    details = Details(
        **body.get("details", {})
    )

    errors = None
    if body.get("errors"):
        errors = [Error(**error) for error in body["errors"]]

    response_body = ResponseBody(
        action=body.get("action"),
        autonomy_states=autonomy_states,
        available_commands=available_commands,
        cleaning_center=cleaning_center,
        details=details,
        errors=errors,
        state=body.get("state")
    )
    return response_body


def _parse_cleaning_state_body(payload: Dict) -> CleaningStateResponse:
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


# Crear un contexto SSL una sola vez para toda la aplicación
# Esta operación bloqueante se realiza al importar el módulo, no dentro del bucle de eventos
_SSL_CONTEXT = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

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
        self._reconnect_task = None  # Tarea para los intentos de reconexión
        self._should_reconnect = True

    async def connect(self):
        retry_delay = 1  # Comenzar con 1 segundo de retraso
        max_delay = 300  # Retraso máximo de 5 minutos
        while self._should_reconnect:
            try:
                # Usar el contexto SSL global pre-creado
                self.websocket = await websockets.connect(
                    self._url,
                    ssl=_SSL_CONTEXT
                )
                self.connected = True
                _LOGGER.debug("Conectado al WebSocket")
                await self._join_robot_channel()
                self._listen_task = self.hass.loop.create_task(self._listen())
                break  # Salir del bucle al conectar exitosamente
            except Exception as e:
                _LOGGER.error("Error al conectar al WebSocket: %s", e)
                self.connected = False
                # Esperar antes de reintentar
                _LOGGER.info("Reconectando en %s segundos...", retry_delay)
                await asyncio.sleep(retry_delay)
                # Backoff exponencial
                retry_delay = min(retry_delay * 2, max_delay)

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
        except (ConnectionClosed, websockets.exceptions.WebSocketException) as e:
            _LOGGER.warning("Conexión WebSocket cerrada: %s", e)
            self.connected = False
            # Iniciar intento de reconexión si no se está reconectando ya
            if self._should_reconnect:
                if self._reconnect_task is None or self._reconnect_task.done():
                    self._reconnect_task = self.hass.loop.create_task(
                        self._reconnect())
        except Exception as e:
            _LOGGER.error("Error en _listen: %s", e)
            self.connected = False
            # Iniciar intento de reconexión si no se está reconectando ya
            if self._should_reconnect:
                if self._reconnect_task is None or self._reconnect_task.done():
                    self._reconnect_task = self.hass.loop.create_task(
                        self._reconnect())

    async def _reconnect(self):
        """Intentar reconectar el WebSocket."""
        _LOGGER.info("Intentando reconectar el WebSocket...")
        # Cerrar el WebSocket actual si no está ya cerrado
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        # Esperar antes de reconectar
        # Puedes ajustar este tiempo según sea necesario
        await asyncio.sleep(5)
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
                response_body = _parse_response_body(body)
                await self.update_entity_state(response_body)
            except Exception as e:
                _LOGGER.error("Error parsing phx_reply response body: %s", e)
        else:
            _LOGGER.debug("phx_reply without body")

    async def _handle_last_state(self, payload):
        if "body" in payload:
            body = payload["body"]
            try:
                response_body = _parse_response_body(body)
                await self.update_entity_state(response_body)
            except Exception as e:
                _LOGGER.error("Error parsing last_state body: %s", e)
        else:
            _LOGGER.debug("last_state without body")

    async def _handle_cleaning_state(self, payload):
        if "body" in payload:
            body = payload["body"]
            try:
                cleaning_state_response = _parse_cleaning_state_body(payload)
                await self.update_cleaning_state(cleaning_state_response)
            except Exception as e:
                _LOGGER.error("Error parsing cleaning_state body: %s", e)
        else:
            _LOGGER.debug("cleaning_state without body")

    async def update_cleaning_state(self, cleaning_state_response: CleaningStateResponse):
        """Actualiza la entidad con información detallada de la limpieza."""
        # Por ejemplo, puedes actualizar atributos personalizados
        # cleaning_body = cleaning_state_response.body
        # Supongamos que quieres actualizar el área limpiada
        # total_area = sum(run.stats.area for run in cleaning_body.runs)
        # self.entity._attr_cleaned_area = total_area

        # Otros atributos pueden ser actualizados aquí

        # Confirmar los cambios
        # self.entity.async_write_ha_state()
        # _LOGGER.debug("Entity cleaning progress updated. Cleaned area: %s", total_area)

    async def update_entity_state(self, response_body: ResponseBody):
        """Actualiza el estado de la entidad basado en los datos de ResponseBody."""
        action = response_body.action
        state = response_body.state
        available_commands = response_body.available_commands
        details = response_body.details
        errors = response_body.errors

        # Actualizar el estado usando VacuumActivity
        if state == "busy" and action == "cleaning":
            ha_activity = VacuumActivity.CLEANING
        elif state == "idle" and details and details.is_docked:
            ha_activity = VacuumActivity.DOCKED
        elif action == "cleaning" and state == "paused":
            ha_activity = VacuumActivity.PAUSED
        elif action == "docking":
            ha_activity = VacuumActivity.RETURNING
        elif errors:
            ha_activity = VacuumActivity.ERROR
        else:
            ha_activity = VacuumActivity.IDLE

        # Actualizar la entidad
        self.entity._attr_activity = ha_activity
        self.entity._attr_status = action

        # Guardar estado de la bolsa
        if response_body.cleaning_center and response_body.cleaning_center.bag_status:
            self.entity._attr_bag_status = response_body.cleaning_center.bag_status

        # Guardar available_commands si no es None
        if available_commands is not None:
            self.entity._attr_available_commands = available_commands
            _LOGGER.debug("Available commands updated: %s", available_commands)

        # Determinar y almacenar el estado de la batería
        details = response_body.details
        battery_level = getattr(details, "charge", None)
        is_charging = getattr(details, "is_charging", False)
        self.entity._is_charging = is_charging

        entry_data = self.entity.hass.data[DOMAIN][self.entity._entry_id]
        runtime = entry_data.setdefault("runtime", {})
        robots_state = runtime.setdefault("robots", {})
        robot_state = robots_state.setdefault(self.entity._robot.id, {"robot": self.entity._robot})
        robot_state["robot"] = self.entity._robot
        robot_state["battery_level"] = battery_level
        robot_state["is_charging"] = is_charging

        async_dispatcher_send(
            self.entity.hass,
            f"{SIGNAL_ROBOT_BATTERY}_{self.entity._robot.id}",
            battery_level,
            is_charging,
        )

        # Confirmar los cambios de estado a Home Assistant
        self.entity.async_write_ha_state()
        _LOGGER.debug(
            "Entity state updated in Home Assistant with activity: %s", ha_activity)

    async def disconnect(self):
        self._should_reconnect = False  # Detener intentos de reconexión
        if self.websocket:
            await self.websocket.close()
        if self._listen_task:
            self._listen_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        self.connected = False
