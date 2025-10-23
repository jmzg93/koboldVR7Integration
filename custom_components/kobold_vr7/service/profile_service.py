import logging

from ..api.profile_api_client import ProfileApiClient, ProfileApiClientError


class ProfileServiceError(Exception):
    """Error personalizado para el servicio de perfil."""


class ProfileService:
    """Servicio de alto nivel para gestionar la autenticación con Companion."""

    def __init__(self, profile_api_client: ProfileApiClient) -> None:
        self._client = profile_api_client
        self._logger = logging.getLogger(__name__)

    async def login(self, id_token: str) -> str:
        """Obtiene el bearer necesario para conectar con el WebSocket."""

        try:
            self._logger.debug("Solicitando bearer para el WebSocket")
            return await self._client.login(id_token)
        except ProfileApiClientError as error:
            self._logger.error("Error en ProfileService al solicitar bearer: %s", error)
            raise ProfileServiceError("No se pudo obtener el bearer para el WebSocket") from error
