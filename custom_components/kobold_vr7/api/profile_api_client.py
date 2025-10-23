import logging
from typing import Optional

import aiohttp

from ..const import (
    COMPANION_HOST,
    MOBILE_APP_ACCEPT_ENCODING,
    MOBILE_APP_BUILD,
    MOBILE_APP_OS,
    MOBILE_APP_OS_VERSION,
    MOBILE_APP_USER_AGENT,
    MOBILE_APP_VERSION,
)


class ProfileApiClientError(Exception):
    """Error personalizado para el cliente del perfil."""


class ProfileApiClient:
    """Cliente responsable de autenticar al usuario en el servicio Companion."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str = COMPANION_HOST,
        language: Optional[str] = None,
    ) -> None:
        self._session = session
        self._host = host.rstrip("/")
        self._path_login = "/api/v1/profile/login"
        self._language_header = self._format_language(language)
        self._logger = logging.getLogger(__name__)

    async def login(self, id_token: str) -> str:
        """Inicia sesión en el perfil y devuelve el bearer para el WebSocket."""

        url = f"{self._host}{self._path_login}"
        headers = self._build_headers(id_token)

        self._logger.debug(
            "Solicitando token de WebSocket en %s con cabeceras %s",
            url,
            self._sanitize_request_headers(headers),
        )

        try:
            async with self._session.post(url, headers=headers) as response:
                response_text = await response.text()

                response_headers = dict(response.headers)
                self._logger.debug(
                    "Cabeceras de respuesta de Companion: %s",
                    self._sanitize_response_headers(response_headers),
                )

                if response.status != 200:
                    self._logger.error(
                        "Error al autenticar en Companion: %s - %s",
                        response.status,
                        response_text,
                    )
                    raise ProfileApiClientError(
                        f"Error al autenticar en Companion: {response.status}"
                    )

                authorization = response.headers.get("Authorization")
                if not authorization:
                    self._logger.error(
                        "La respuesta de Companion no contiene cabecera Authorization"
                    )
                    raise ProfileApiClientError(
                        "No se recibió cabecera Authorization del servicio Companion"
                    )

                self._logger.debug(
                    "Respuesta de Companion recibida correctamente: %s",
                    response_text,
                )
                self._logger.debug(
                    "Cabecera Authorization recibida: %s",
                    self._sanitize_authorization(authorization),
                )
                return authorization
        except aiohttp.ClientError as error:
            self._logger.error("Error de red al llamar a Companion: %s", error)
            raise ProfileApiClientError("Error de red al contactar Companion") from error

    def _build_headers(self, id_token: str) -> dict:
        """Construye las cabeceras necesarias para la autenticación."""

        return {
            "authorization": f"Bearer {id_token}",
            "accept-language": self._language_header,
            "mobile-app-version": MOBILE_APP_VERSION,
            "mobile-app-build": MOBILE_APP_BUILD,
            "mobile-app-os": MOBILE_APP_OS,
            "mobile-app-os-version": MOBILE_APP_OS_VERSION,
            "accept-encoding": MOBILE_APP_ACCEPT_ENCODING,
            "user-agent": MOBILE_APP_USER_AGENT,
        }

    def _format_language(self, language: Optional[str]) -> str:
        """Normaliza el idioma en el formato esperado por la API."""

        if not language:
            return "es-ES"

        language = language.replace("_", "-")
        if "-" in language:
            parts = language.split("-")
            return f"{parts[0].lower()}-{parts[-1].upper()}"

        if len(language) == 2:
            return f"{language.lower()}-{language.upper()}"

        return language

    def _sanitize_request_headers(self, headers: dict) -> dict:
        """Oculta información sensible de las cabeceras antes de registrarlas."""

        sanitized = headers.copy()
        sanitized["authorization"] = self._sanitize_authorization(
            sanitized.get("authorization")
        )
        return sanitized

    def _sanitize_response_headers(self, headers: dict) -> dict:
        """Oculta el token de la cabecera Authorization de la respuesta."""

        sanitized = headers.copy()
        if "Authorization" in sanitized:
            sanitized["Authorization"] = self._sanitize_authorization(
                sanitized.get("Authorization")
            )
        return sanitized

    @staticmethod
    def _sanitize_authorization(value: Optional[str]) -> Optional[str]:
        """Devuelve el token parcialmente oculto para los logs."""

        if not value:
            return value

        token = value.replace("Bearer ", "")
        if len(token) <= 12:
            return value

        return f"Bearer {token[:6]}...{token[-4:]}"
