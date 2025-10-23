import logging
from typing import Dict, Optional

from aiohttp import ClientSession


_DEFAULT_DEVICE_TOKEN = "dUpdkdKaS6u5wptzZkTVH6:APA91bFkznZLRKgzDOi8qnw"


class CompanionApiClient:
    """Cliente HTTP para interactuar con el servicio Companion."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        language: str,
        device_token: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._language = language or "es-ES"
        self._device_token = device_token
        self._logger = logger or logging.getLogger(__name__)

    async def login(self, id_token: str) -> str:
        """Realiza la petición de login y devuelve el Bearer Companion."""
        url = f"{self._base_url}/api/v1/profile/login"
        headers = self._build_headers(id_token)

        self._logger.debug("Solicitando token Companion en %s", url)
        self._logger.debug(
            "Cabeceras de login Companion: %s", self._sanitizar_cabeceras(headers)
        )

        async with self._session.post(url, headers=headers) as response:
            if response.status != 200:
                texto_error = await response.text()
                self._logger.error(
                    "Error al renovar el token Companion: %s %s",
                    response.status,
                    texto_error,
                )
                response.raise_for_status()

            await response.read()

            bearer = response.headers.get("Authorization")
            if not bearer:
                self._logger.error(
                    "Respuesta de Companion sin cabecera Authorization: %s",
                    self._sanitizar_cabeceras(dict(response.headers)),
                )
                raise RuntimeError(
                    "La respuesta de profile/login no incluye Authorization"
                )

            if bearer.lower().startswith("bearer "):
                bearer = bearer.split(" ", 1)[1]

            self._logger.debug(
                "Token Companion obtenido correctamente. Cabeceras respuesta: %s",
                self._sanitizar_cabeceras(dict(response.headers)),
            )
            return bearer

    def _build_headers(self, id_token: str) -> Dict[str, str]:
        """Construye las cabeceras para el login Companion."""
        headers = {
            "Authorization": f"Bearer {id_token}",
            "User-Agent": "okhttp/5.1.0",
            "mobile-app-version": "3.12.1",
            "mobile-app-build": "40408",
            "mobile-app-os": "android",
            "mobile-app-os-version": "11",
            "Accept-Language": self._language,
        }

        if self._device_token:
            headers["x-vrwk-mykobold-device-token"] = self._device_token

        return headers

    @staticmethod
    def _mask_token(valor: str) -> str:
        """Oculta valores sensibles antes de escribirlos en el log."""
        if not valor:
            return valor
        if valor.lower().startswith("bearer "):
            prefijo, token = valor.split(" ", 1)
            return f"{prefijo} {CompanionApiClient._mask_token(token)}"
        if valor.lower().startswith("auth0bearer"):
            prefijo = "Auth0Bearer"
            token = valor[len(prefijo) :]
            token = token.lstrip(" :")
            if not token:
                return prefijo
            return f"{prefijo} {CompanionApiClient._mask_token(token)}"
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


__all__ = ["CompanionApiClient", "_DEFAULT_DEVICE_TOKEN"]

