import asyncio
import logging
import json
import uuid
import ssl
from typing import Any, Awaitable, Callable, Dict, Optional

import aiohttp
from .model.robot_wss_cleaning_state_response import CleaningStateResponse, \
    RunSettings, RunStats, RunTiming, Run, CleaningStateBody
from .model.robot_wss_last_state_or_phx_reply_response import AutonomyStates, AvailableCommands, \
    CleaningCenter, Details, Error, ResponseBody

from homeassistant.components.vacuum import VacuumActivity
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import (
    DOMAIN,
    SIGNAL_ROBOT_BATTERY,
    COMPANION_WS_URL,
    MOBILE_APP_ACCEPT_ENCODING,
    MOBILE_APP_BUILD,
    MOBILE_APP_OS,
    MOBILE_APP_OS_VERSION,
    MOBILE_APP_USER_AGENT,
    MOBILE_APP_VERSION,
    ERROR_CODE_DESCRIPTIONS,
)

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


_RUN_TIMING_DEFAULTS = {
    "charging": 0,
    "end": "",
    "error": 0,
    "paused": 0,
    "start": "",
}


def _parse_cleaning_state_body(payload: Dict) -> CleaningStateResponse:
    """Normaliza la estructura de los mensajes cleaning_state."""

    # Los eventos JSON planos incluyen la información en "state"
    # mientras que los mensajes Phoenix la envían en "body" junto al código.
    body_source = payload.get("body") or payload.get("state") or {}
    code = payload.get("code", 200)

    runs = []
    for run_data in body_source.get("runs", []) or []:
        settings_data = run_data.get("settings", {})
        settings = RunSettings(
            mode=settings_data.get("mode", ""),
            navigation_mode=settings_data.get("navigation_mode", ""),
        )
        stats_data = run_data.get("stats", {})
        stats = RunStats(
            area=stats_data.get("area", 0.0),
            pickup_count=stats_data.get("pickup_count", 0),
        )
        timing = RunTiming(**{**_RUN_TIMING_DEFAULTS, **(run_data.get("timing") or {})})
        run = Run(
            settings=settings,
            state=run_data.get("state", ""),
            stats=stats,
            timing=timing,
            track_name=run_data.get("track_name"),
            track_uuid=run_data.get("track_uuid"),
        )
        runs.append(run)

    timing = RunTiming(**{**_RUN_TIMING_DEFAULTS, **(body_source.get("timing") or {})})

    cleaning_state_body = CleaningStateBody(
        ability=body_source.get("ability", ""),
        cleaning_type=body_source.get("cleaning_type", ""),
        floorplan_uuid=body_source.get("floorplan_uuid"),
        runs=runs,
        started_by=body_source.get("started_by", ""),
        timing=timing,
    )

    return CleaningStateResponse(code=code, body=cleaning_state_body)


# Crear un contexto SSL una sola vez para toda la aplicación
# Esta operación bloqueante se realiza al importar el módulo, no dentro del bucle de eventos
_SSL_CONTEXT = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

# Conjuntos y traducciones para mapear acciones a actividades y estados legibles
_CLEANING_ACTIONS = {
    "cleaning",
    "fast_mapping",
    "mapping",
    "map_creation",
    "spot_cleaning",
}

_RETURNING_ACTIONS = {
    "docking",
    "returning",
    "going_home",
}

_ACTION_STATUS_TRANSLATIONS = {
    "cleaning": "Limpiando",
    "fast_mapping": "Mapeando el hogar",
    "mapping": "Mapeando el hogar",
    "map_creation": "Mapeando el hogar",
    "spot_cleaning": "Limpieza puntual",
    "docking": "Regresando a la base",
    "returning": "Regresando a la base",
    "going_home": "Regresando a la base",
}

_STATE_STATUS_TRANSLATIONS = {
    "busy": "Ocupado",
    "idle": "Inactivo",
    "paused": "Pausado",
    "error": "Error",
    "charging": "Cargando",
}


def _normalize_action(action: Optional[str]) -> str:
    """Devuelve la acción normalizada en minúsculas y sin valores irrelevantes."""

    if not action:
        return ""

    normalizada = action.strip().lower()
    if normalizada == "invalid":
        return ""

    return normalizada

class KoboldWebSocketClient:
    def __init__(
        self,
        hass,
        session: aiohttp.ClientSession,
        id_token: str,
        robot_id: str,
        entity,
        profile_login: Callable[[str], Awaitable[str]],
        language: Optional[str] = None,
    ):
        self.hass = hass
        self._session = session
        self._id_token = id_token
        self.robot_id = robot_id
        self.entity = entity  # Agrega la entidad aquí
        self.websocket = None
        self.connected = False
        self._url = COMPANION_WS_URL
        self._listen_task = None
        self._reconnect_task = None  # Tarea para los intentos de reconexión
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        self._profile_login = profile_login
        self._language_header = self._format_language(language)
        self._authorization_header: Optional[str] = None
        self._ref_counter = 0
        self._join_ref: Optional[str] = None
        self._heartbeat_interval = 30  # Intervalo en segundos entre heartbeats

    async def connect(self):
        retry_delay = 1  # Comenzar con 1 segundo de retraso
        max_delay = 300  # Retraso máximo de 5 minutos
        while self._should_reconnect:
            try:
                self._authorization_header = None
                self._authorization_header = await self._profile_login(self._id_token)
                _LOGGER.debug(
                    "Bearer recuperado para el WebSocket: %s",
                    self._sanitize_headers({"Authorization": self._authorization_header})
                    .get("Authorization"),
                )
                headers = self._build_connection_headers()

                _LOGGER.debug(
                    "Intentando conectar al WebSocket %s con cabeceras %s",
                    self._url,
                    self._sanitize_headers(headers),
                )

                # Usar el contexto SSL global pre-creado
                self.websocket = await self._session.ws_connect(
                    self._url,
                    ssl=_SSL_CONTEXT,
                    headers=headers,
                    autoping=True,
                )
                self.connected = True
                response_headers = {}
                websocket_headers = getattr(self.websocket, "headers", None)
                if websocket_headers is not None:
                    response_headers = dict(websocket_headers)
                _LOGGER.debug(
                    "Conectado al WebSocket. Cabeceras de respuesta: %s",
                    self._sanitize_headers(response_headers),
                )
                await self._join_robot_channel()
                self._start_heartbeat()
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

    def _build_connection_headers(self) -> Dict[str, str]:
        """Genera las cabeceras necesarias para el WebSocket."""

        if not self._authorization_header:
            raise RuntimeError("No se pudo generar la cabecera Authorization para el WebSocket")

        return {
            "Authorization": self._authorization_header,
            "Accept-Language": self._language_header,
            "mobile-app-version": MOBILE_APP_VERSION,
            "mobile-app-build": MOBILE_APP_BUILD,
            "mobile-app-os": MOBILE_APP_OS,
            "mobile-app-os-version": MOBILE_APP_OS_VERSION,
            "Accept-Encoding": MOBILE_APP_ACCEPT_ENCODING,
            "User-Agent": MOBILE_APP_USER_AGENT,
        }

    def _format_language(self, language: Optional[str]) -> str:
        """Normaliza el idioma en el formato esperado."""

        if not language:
            return "es-ES"

        language = language.replace("_", "-")
        if "-" in language:
            parts = language.split("-")
            return f"{parts[0].lower()}-{parts[-1].upper()}"

        if len(language) == 2:
            return f"{language.lower()}-{language.upper()}"

        return language

    async def _join_robot_channel(self):
        # Enviar mensaje para unirse al canal del robot
        self._ref_counter = 0
        self._join_ref = self._next_ref()
        join_msg = [
            self._join_ref,
            self._next_ref(),
            f"robots:{self.robot_id}",
            "phx_join",
            {}
        ]
        payload = json.dumps(join_msg)
        _LOGGER.debug("Enviando mensaje de unión al canal: %s", payload)
        await self.websocket.send_str(payload)

        unique_request_id = str(uuid.uuid4())
        # Enviar mensaje para solicitar el último estado
        last_state_msg = [
            self._join_ref,
            self._next_ref(),
            f"robots:{self.robot_id}",
            "last_state",
            {"request_id": unique_request_id}
        ]
        last_state_payload = json.dumps(last_state_msg)
        _LOGGER.debug("Solicitando último estado del robot: %s", last_state_payload)
        await self.websocket.send_str(last_state_payload)

    def _start_heartbeat(self) -> None:
        """Inicia el envío periódico de heartbeats Phoenix."""

        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def _heartbeat_loop():
            try:
                while self.connected and self.websocket and not self.websocket.closed:
                    await asyncio.sleep(self._heartbeat_interval)
                    await self._send_heartbeat()
            except asyncio.CancelledError:
                _LOGGER.debug("Tarea de heartbeat cancelada")
                raise
            except Exception as error:
                _LOGGER.warning("Error enviando heartbeat: %s", error)

        self._heartbeat_task = self.hass.loop.create_task(_heartbeat_loop())

    async def _send_heartbeat(self) -> None:
        """Envía un heartbeat Phoenix para mantener la conexión viva."""

        if not self.websocket or self.websocket.closed:
            return

        heartbeat_msg = [
            None,
            self._next_ref(),
            "phoenix",
            "heartbeat",
            {},
        ]
        payload = json.dumps(heartbeat_msg)
        _LOGGER.debug("Enviando heartbeat: %s", payload)
        await self.websocket.send_str(payload)

    async def _listen(self):
        try:
            async for message in self.websocket:
                if message.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(message.data)
                elif message.type == aiohttp.WSMsgType.BINARY:
                    _LOGGER.debug(
                        "Mensaje binario recibido (%s bytes)", len(message.data)
                    )
                elif message.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error(
                        "Error en el WebSocket: %s", self.websocket.exception()
                    )
                    break
                elif message.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    _LOGGER.info("El servidor cerró la conexión WebSocket")
                    break
                else:
                    _LOGGER.debug("Mensaje WebSocket no manejado: %s", message.type)
        except aiohttp.ClientError as e:
            _LOGGER.warning("Conexión WebSocket cerrada con error de cliente: %s", e)
        except asyncio.CancelledError:
            _LOGGER.debug("Escucha del WebSocket cancelada")
            raise
        except Exception as e:
            _LOGGER.error("Error en _listen: %s", e)
        finally:
            self.connected = False
            await self._stop_heartbeat()
            if self._should_reconnect:
                self._schedule_reconnect()

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

    def _schedule_reconnect(self) -> None:
        """Programa un intento de reconexión si no existe uno activo."""

        if not self._should_reconnect:
            return

        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self.hass.loop.create_task(self._reconnect())

    async def _handle_message(self, message):
        _LOGGER.debug("Received message: %s", message)
        data = json.loads(message)

        if isinstance(data, list):
            await self._handle_phoenix_message(data)
            return

        if isinstance(data, dict):
            await self._handle_event_message(data)
            return

        _LOGGER.error("Formato de mensaje desconocido: %s", type(data))

    async def _handle_phoenix_message(self, data: list) -> None:
        """Gestiona mensajes en formato Phoenix."""

        if len(data) < 5:
            _LOGGER.error("Mensaje Phoenix incompleto: %s", data)
            return

        topic = data[2]
        event = data[3]
        payload = data[4]

        if event == "phx_reply":
            await self._handle_phx_reply(payload)
        elif event == "last_state":
            await self._handle_last_state(payload)
        elif event == "cleaning_state":
            await self._handle_cleaning_state(payload)
        else:
            _LOGGER.debug("Evento Phoenix no manejado en %s: %s", topic, event)

    async def _handle_event_message(self, data: Dict[str, Any]) -> None:
        """Gestiona mensajes en formato JSON plano enviados por Companion."""

        event_type = data.get("event_type")
        payload = data.get("payload")

        if not event_type:
            _LOGGER.debug("Mensaje sin tipo de evento: %s", data)
            return

        if event_type == "service_status":
            _LOGGER.debug("Estado del servicio recibido: %s", payload)
            return

        if event_type == "state_changed":
            await self._handle_state_changed_event(payload)
            return

        if event_type == "cleaning_state":
            await self._handle_cleaning_state_event(payload)
            return

        _LOGGER.debug("Evento no manejado: %s", event_type)

    async def _handle_state_changed_event(self, payload: Optional[Dict[str, Any]]) -> None:
        """Convierte los eventos de cambio de estado en actualizaciones de entidad."""

        if not payload or "state" not in payload:
            _LOGGER.debug("Evento state_changed sin cuerpo válido: %s", payload)
            return

        try:
            response_body = _parse_response_body(payload["state"])
            await self.update_entity_state(response_body)
        except Exception as error:
            _LOGGER.error("Error procesando state_changed: %s", error)

    async def _handle_cleaning_state_event(self, payload: Optional[Dict[str, Any]]) -> None:
        """Procesa eventos cleaning_state enviados como JSON plano."""

        if not payload:
            _LOGGER.debug("Evento cleaning_state sin contenido: %s", payload)
            return

        try:
            cleaning_state_response = _parse_cleaning_state_body(payload)
            await self.update_cleaning_state(cleaning_state_response)
        except Exception as error:
            _LOGGER.error("Error procesando cleaning_state: %s", error)

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
        action_original = response_body.action
        state = response_body.state
        available_commands = response_body.available_commands
        details = response_body.details
        errors = response_body.errors

        accion_normalizada = _normalize_action(action_original)
        # Conservamos la última acción válida para reutilizarla cuando Companion envía valores vacíos
        if accion_normalizada:
            self.entity._ultima_accion = accion_normalizada
            self.entity._ultima_accion_original = action_original
        else:
            accion_normalizada = getattr(self.entity, "_ultima_accion", "")
            if not action_original:
                action_original = getattr(self.entity, "_ultima_accion_original", None)

        actividad_previa = getattr(self.entity, "_attr_activity", VacuumActivity.IDLE)
        ha_activity = self._map_activity(
            state,
            accion_normalizada,
            errors,
            details,
            actividad_previa,
        )

        # Actualizar la entidad
        self.entity._attr_activity = ha_activity
        status_text = self._build_status_text(action_original, accion_normalizada, state)

        _LOGGER.debug(
            "Acción evaluada: %s (normalizada: %s), estado bruto: %s, actividad previa: %s, actividad resultante: %s",
            action_original or "(vacía)",
            accion_normalizada or "(vacía)",
            state,
            actividad_previa,
            ha_activity,
        )

        # Guardar estado de la bolsa
        if response_body.cleaning_center and response_body.cleaning_center.bag_status:
            self.entity._attr_bag_status = response_body.cleaning_center.bag_status

        # Guardar available_commands si no es None
        if available_commands is not None:
            self.entity._attr_available_commands = available_commands
            _LOGGER.debug("Available commands updated: %s", available_commands)

        if errors:
            errores_legibles: list[str] = []
            errores_detallados: list[dict[str, str]] = []
            for error in errors:
                descripcion = self._describe_error(error)
                severidad_legible = self._map_severity(error.severity)
                errores_legibles.append(descripcion)
                detalle_error = {
                    "codigo": error.code,
                    "descripcion": descripcion,
                }
                if severidad_legible:
                    detalle_error["severidad"] = severidad_legible
                errores_detallados.append(detalle_error)
            status_text = errores_legibles[0]
            self.entity._ultimo_error = errores_legibles[0]
            self.entity._errores_detallados = errores_detallados
        else:
            self.entity._ultimo_error = None
            self.entity._errores_detallados = []

        # Determinar y almacenar el estado de la batería
        details = response_body.details
        battery_level = getattr(details, "charge", None)
        is_charging = getattr(details, "is_charging", False)
        self.entity._is_charging = is_charging

        self.entity._attr_status = status_text

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
        await self._stop_heartbeat()
        self.connected = False

    async def _stop_heartbeat(self) -> None:
        """Detiene la tarea de heartbeats si está activa."""

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self._heartbeat_task = None

    def _describe_error(self, error: Error) -> str:
        """Convierte un código de error en una descripción legible."""

        descripcion = ERROR_CODE_DESCRIPTIONS.get(error.code)
        if not descripcion:
            descripcion = error.code.replace("_", " ").capitalize()

        if error.severity:
            severidad_legible = self._map_severity(error.severity)
            if severidad_legible:
                return f"{descripcion} (severidad: {severidad_legible})"
            return descripcion

        return descripcion

    @staticmethod
    def _map_severity(severity: Optional[str]) -> Optional[str]:
        """Traduce la severidad del error a español."""

        if severity is None:
            return None

        return {
            "error": "error",
            "warning": "advertencia",
            "info": "información",
        }.get(severity, severity)

    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Oculta información sensible antes de registrar cabeceras."""

        sanitized = dict(headers)
        authorization = sanitized.get("Authorization")
        if authorization:
            sanitized["Authorization"] = self._mask_token(authorization)
        return sanitized

    @staticmethod
    def _mask_token(value: str) -> str:
        """Devuelve el token parcialmente oculto para los logs."""

        token = value.replace("Bearer ", "")
        if len(token) <= 12:
            return value

        return f"Bearer {token[:6]}...{token[-4:]}"

    def _next_ref(self) -> str:
        """Genera un identificador incremental para los mensajes Phoenix."""

        self._ref_counter += 1
        return str(self._ref_counter)

    def _map_activity(
        self,
        state: Optional[str],
        accion_normalizada: str,
        errors: Optional[list[Error]],
        details: Optional[Details],
        actividad_previa: VacuumActivity,
    ) -> VacuumActivity:
        """Determina la actividad de la entidad con lógica adicional para mapeos."""

        if errors:
            return VacuumActivity.ERROR

        if accion_normalizada in _CLEANING_ACTIONS:
            return VacuumActivity.CLEANING

        if accion_normalizada in _RETURNING_ACTIONS:
            return VacuumActivity.RETURNING

        if state == "idle" and details and getattr(details, "is_docked", False):
            return VacuumActivity.DOCKED

        if state == "paused":
            return VacuumActivity.PAUSED

        if state == "busy":
            if actividad_previa in (
                VacuumActivity.CLEANING,
                VacuumActivity.RETURNING,
            ):
                return actividad_previa
            if accion_normalizada:
                return VacuumActivity.CLEANING
            return actividad_previa or VacuumActivity.IDLE

        if state == "idle":
            return VacuumActivity.IDLE

        return actividad_previa or VacuumActivity.IDLE

    def _build_status_text(
        self,
        accion_original: Optional[str],
        accion_normalizada: str,
        state: Optional[str],
    ) -> str:
        """Genera un texto de estado en español a partir de la acción o estado."""

        if accion_normalizada and accion_normalizada in _ACTION_STATUS_TRANSLATIONS:
            return _ACTION_STATUS_TRANSLATIONS[accion_normalizada]

        if state and state in _STATE_STATUS_TRANSLATIONS:
            return _STATE_STATUS_TRANSLATIONS[state]

        if accion_original:
            return accion_original.replace("_", " ").capitalize()

        if accion_normalizada:
            return accion_normalizada.replace("_", " ").capitalize()

        if state:
            return state.replace("_", " ").capitalize()

        return "desconocido"
