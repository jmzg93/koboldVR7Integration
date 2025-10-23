import asyncio
import logging
import json
import uuid
import ssl
import os
from typing import Dict, Optional
from urllib.parse import urlparse
import websockets
from aiohttp import ClientSession, WSMsgType, ClientError, ClientResponseError

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
    code = payload.get("code", 0)
    body = payload.get("body", {})
    runs = []
    for run_data in body.get("runs", []):
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
_DEFAULT_DEVICE_TOKEN = "dUpdkdKaS6u5wptzZkTVH6:APA91bFkznZLRKgzDOi8qnw"

class KoboldWebSocketClient:
    def __init__(self, hass, token, robot_id, entity):
        self.hass = hass
        self._id_token = token
        self.robot_id = robot_id
        self.entity = entity  # Agrega la entidad aquí
        self.websocket = None
        self.connected = False
        self._session = None
        self._companion_token = None
        self._companion_base_url = None

        url_template = os.environ.get(
            "KOBOLD_WS_URL",
            "wss://api-2-prod.companion.kobold.vorwerk.com/api/ws",
        )

        if "{token}" in url_template:
            self._url = url_template.format(token=self._id_token)
        else:
            self._url = url_template

        # Detectamos si seguimos usando el protocolo antiguo de Phoenix
        self._use_phoenix_protocol = "socket/websocket" in self._url

        if self._use_phoenix_protocol:
            if "token=" not in self._url:
                separador = "&" if "?" in self._url else "?"
                self._url = f"{self._url}{separador}token={self._id_token}"
            if "vendor=" not in self._url:
                separador = "&" if "?" in self._url else "?"
                self._url = f"{self._url}{separador}vendor=vorwerk"
            if "vsn=" not in self._url:
                separador = "&" if "?" in self._url else "?"
                self._url = f"{self._url}{separador}vsn=2.0.0"
        else:
            self._companion_base_url = self._derivar_base_http(self._url)

        self._listen_task = None
        self._reconnect_task = None  # Tarea para los intentos de reconexión
        self._should_reconnect = True

    async def connect(self):
        retry_delay = 1  # Comenzar con 1 segundo de retraso
        max_delay = 300  # Retraso máximo de 5 minutos
        while self._should_reconnect:
            try:
                # Usar el contexto SSL global pre-creado
                if self._use_phoenix_protocol:
                    _LOGGER.debug(
                        "Intentando conectar usando protocolo Phoenix en %s",
                        self._url,
                    )
                    self.websocket = await websockets.connect(
                        self._url,
                        ssl=_SSL_CONTEXT,
                    )
                else:
                    if self._session is None or self._session.closed:
                        # Reutilizamos la sesión para evitar fugas de sockets
                        self._session = ClientSession()
                    headers = await self._build_headers()
                    self._log_connection_headers(headers)
                    _LOGGER.debug(
                        "Intentando conectar con Companion en %s",
                        self._url,
                    )
                    self.websocket = await self._session.ws_connect(
                        self._url,
                        ssl=_SSL_CONTEXT,
                        headers=headers,
                    )
                self.connected = True
                if not self._use_phoenix_protocol and self.websocket.response:
                    _LOGGER.debug(
                        "Conexión Companion establecida. Código: %s, cabeceras: %s",
                        self.websocket.response.status,
                        dict(self.websocket.response.headers),
                    )
                else:
                    _LOGGER.debug("Conectado al WebSocket")
                if self._use_phoenix_protocol:
                    await self._join_robot_channel()
                self._listen_task = self.hass.loop.create_task(self._listen())
                break  # Salir del bucle al conectar exitosamente
            except ClientResponseError as e:
                _LOGGER.error(
                    "Error HTTP al conectar al WebSocket Companion: %s %s",
                    e.status,
                    e.message,
                )
                if e.headers:
                    _LOGGER.debug(
                        "Cabeceras de respuesta: %s",
                        self._sanitizar_cabeceras(dict(e.headers)),
                    )
                if e.status == 401:
                    self._companion_token = None
                self.connected = False
                _LOGGER.info("Reconectando en %s segundos...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)
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
            if self._use_phoenix_protocol:
                async for message in self.websocket:
                    await self._handle_message(message)
            else:
                async for ws_message in self.websocket:
                    if ws_message.type == WSMsgType.TEXT:
                        await self._handle_message(ws_message.data)
                    elif ws_message.type == WSMsgType.BINARY:
                        try:
                            texto = ws_message.data.decode("utf-8")
                        except UnicodeDecodeError:
                            _LOGGER.warning("Mensaje binario no decodificable recibido del Companion")
                            continue
                        await self._handle_message(texto)
                    elif ws_message.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                        break
                    elif ws_message.type == WSMsgType.ERROR:
                        raise ws_message.data or RuntimeError("Error en WebSocket Companion")
        except (ConnectionClosed, websockets.exceptions.WebSocketException, ClientError) as e:
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
            finally:
                self.websocket = None
        # Esperar antes de reconectar
        # Puedes ajustar este tiempo según sea necesario
        await asyncio.sleep(5)
        await self.connect()

    async def _handle_message(self, message):
        _LOGGER.debug("Received message: %s", message)

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            _LOGGER.error("Mensaje WebSocket no es JSON válido: %s", message)
            return

        if isinstance(data, list):
            await self._handle_phoenix_message(data)
        elif isinstance(data, dict):
            await self._handle_event_message(data)
        else:
            _LOGGER.debug("Formato de mensaje WebSocket no soportado: %s", type(data))

    async def _handle_phoenix_message(self, data):
        """Maneja mensajes del protocolo antiguo basado en Phoenix."""
        # Verificar que el mensaje es una lista con al menos 5 elementos
        if len(data) < 5:
            _LOGGER.error("Mensaje Phoenix inválido: %s", data)
            return

        topic = data[2]
        event = data[3]
        payload = data[4]

        if topic != f"robots:{self.robot_id}":
            _LOGGER.debug("Mensaje Phoenix ignorado para tópico %s", topic)
            return

        # Manejar el evento phx_reply
        if event == "phx_reply":
            await self._handle_phx_reply(payload)
        elif event == "last_state":
            await self._handle_last_state(payload)
        elif event == "cleaning_state":
            await self._handle_cleaning_state(payload)
        else:
            _LOGGER.debug("Evento Phoenix no manejado: %s", event)

    async def _handle_event_message(self, data):
        """Maneja mensajes del nuevo servicio Companion."""
        event_type = data.get("event_type")
        payload = data.get("payload", {}) or {}

        if not event_type:
            _LOGGER.debug("Mensaje sin tipo de evento: %s", data)
            return

        if event_type == "state_changed":
            await self._handle_companion_state_changed(payload)
        elif event_type == "cleaning_state":
            await self._handle_companion_cleaning_state(payload)
        elif event_type == "service_status":
            _LOGGER.debug("Estado del servicio Companion: %s", payload)
        else:
            _LOGGER.debug("Evento Companion no manejado: %s", event_type)

    async def _handle_companion_state_changed(self, payload):
        """Procesa eventos state_changed del nuevo WebSocket."""
        robot_id = payload.get("robot_id")
        if robot_id and robot_id != self.robot_id:
            _LOGGER.debug("Estado ignorado para robot %s", robot_id)
            return

        state_body = payload.get("state")
        if not state_body:
            _LOGGER.debug("state_changed sin estado: %s", payload)
            return

        try:
            response_body = _parse_response_body(state_body)
            await self.update_entity_state(response_body)
        except Exception as e:
            _LOGGER.error("Error procesando state_changed: %s", e)

    async def _handle_companion_cleaning_state(self, payload):
        """Procesa eventos cleaning_state del nuevo WebSocket."""
        robot_id = payload.get("robot_id")
        if robot_id and robot_id != self.robot_id:
            _LOGGER.debug("Cleaning state ignorado para robot %s", robot_id)
            return

        body = payload.get("body") or payload.get("state")
        if not body:
            _LOGGER.debug("cleaning_state sin body: %s", payload)
            return

        try:
            if "body" in payload:
                payload_a_procesar = payload
            else:
                payload_a_procesar = {"body": body, "code": payload.get("code", 0)}

            cleaning_state_response = _parse_cleaning_state_body(payload_a_procesar)
            await self.update_cleaning_state(cleaning_state_response)
        except Exception as e:
            _LOGGER.error("Error procesando cleaning_state Companion: %s", e)

    async def _build_headers(self):
        """Construye las cabeceras necesarias para el nuevo WebSocket."""
        companion_token = await self._ensure_companion_token()
        headers = {
            "Authorization": f"Bearer {companion_token}",
            "User-Agent": "okhttp/5.1.0",
            "mobile-app-version": "3.12.1",
            "mobile-app-build": "40408",
            "mobile-app-os": "android",
            "mobile-app-os-version": "11",
        }

        language = getattr(self.hass.config, "language", None) or "es-ES"
        headers["Accept-Language"] = language

        return headers

    def _log_connection_headers(self, headers: Dict[str, str]):
        """Registra las cabeceras usadas durante la conexión ocultando datos sensibles."""
        _LOGGER.debug("Cabeceras de conexión: %s", self._sanitizar_cabeceras(headers))

    @staticmethod
    def _mask_token(valor: str) -> str:
        """Oculta la mayor parte de un token para fines de logging."""
        if not valor:
            return valor
        if valor.lower().startswith("bearer "):
            prefijo, token = valor.split(" ", 1)
            return f"{prefijo} {KoboldWebSocketClient._mask_token(token)}"
        if valor.lower().startswith("auth0bearer"):
            prefijo = "Auth0Bearer"
            token = valor[len(prefijo):]
            token = token.lstrip(" :")
            if not token:
                return prefijo
            return f"{prefijo} {KoboldWebSocketClient._mask_token(token)}"
        if len(valor) <= 10:
            return "***"
        return f"{valor[:5]}...{valor[-5:]}"

    def _sanitizar_cabeceras(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Devuelve una copia de las cabeceras con los valores sensibles ofuscados."""
        cabeceras = {}
        for clave, valor in headers.items():
            if clave.lower() == "authorization":
                cabeceras[clave] = self._mask_token(valor)
            else:
                cabeceras[clave] = valor
        return cabeceras

    def _derivar_base_http(self, url: str) -> Optional[str]:
        """Deriva la URL base HTTP/HTTPS a partir de una URL WebSocket."""
        try:
            parsed = urlparse(url)
        except Exception as error:
            _LOGGER.debug("No se pudo parsear la URL del WebSocket: %s", error)
            return None

        if not parsed.scheme or not parsed.hostname:
            return None

        if parsed.scheme not in ("ws", "wss"):
            return None

        esquema_http = "https" if parsed.scheme == "wss" else "http"
        netloc = parsed.hostname
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        return f"{esquema_http}://{netloc}"

    async def _ensure_companion_token(self) -> str:
        """Obtiene un token Companion válido, renovándolo si es necesario."""
        if self._companion_token:
            return self._companion_token

        await self._renovar_companion_token()
        if not self._companion_token:
            raise RuntimeError("No se pudo obtener un token Companion para el WebSocket")
        return self._companion_token

    async def _renovar_companion_token(self):
        """Realiza la llamada al endpoint profile/login para obtener el Bearer del WebSocket."""
        if not self._companion_base_url:
            _LOGGER.debug("Base Companion no disponible; se omite la renovación del token")
            return

        if self._session is None or self._session.closed:
            self._session = ClientSession()

        url = f"{self._companion_base_url}/api/v1/profile/login"
        headers = {
            "Authorization": f"Bearer {self._id_token}",
            "User-Agent": "okhttp/5.1.0",
            "mobile-app-version": "3.12.1",
            "mobile-app-build": "40408",
            "mobile-app-os": "android",
            "mobile-app-os-version": "11",
        }

        language = getattr(self.hass.config, "language", None) or "es-ES"
        headers["Accept-Language"] = language

        device_token = os.environ.get("KOBOLD_DEVICE_TOKEN", _DEFAULT_DEVICE_TOKEN)
        if device_token:
            headers["x-vrwk-mykobold-device-token"] = device_token

        _LOGGER.debug("Solicitando token Companion en %s", url)
        _LOGGER.debug("Cabeceras de login Companion: %s", self._sanitizar_cabeceras(headers))

        try:
            async with self._session.post(url, headers=headers) as response:
                if response.status != 200:
                    texto_error = await response.text()
                    _LOGGER.error(
                        "Error al renovar el token Companion: %s %s",
                        response.status,
                        texto_error,
                    )
                    if response.status == 401:
                        self._companion_token = None
                    response.raise_for_status()
                else:
                    await response.read()

                bearer = response.headers.get("Authorization")
                if not bearer:
                    _LOGGER.error(
                        "Respuesta de Companion sin cabecera Authorization: %s",
                        self._sanitizar_cabeceras(dict(response.headers)),
                    )
                    self._companion_token = None
                    raise RuntimeError(
                        "La respuesta de profile/login no incluye Authorization"
                    )

                if bearer.lower().startswith("bearer "):
                    bearer = bearer.split(" ", 1)[1]

                self._companion_token = bearer
                _LOGGER.debug(
                    "Token Companion obtenido correctamente. Cabeceras respuesta: %s",
                    self._sanitizar_cabeceras(dict(response.headers)),
                )
        except ClientResponseError as error:
            if error.status == 401:
                self._companion_token = None
            raise

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
            self.websocket = None
        if self._listen_task:
            self._listen_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
        self.connected = False
