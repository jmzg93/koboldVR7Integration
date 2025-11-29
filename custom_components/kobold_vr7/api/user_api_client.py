import logging
from typing import Any, Dict, Optional

import aiohttp

from .model.validate_otp_response import ValidateOtpResponse


class UserApiClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        path_send_otp: str,
        path_validate_otp: str,
        language: str = "es",  # Parámetro adicional para el idioma
    ):
        self._session = session
        self.host = host
        self.path_send_otp = path_send_otp
        self.path_validate_otp = path_validate_otp
        self._logger = logging.getLogger(__name__)
        self.client_id = "FPSBig7ePFvAE6q99cEDROM8gYUTygkD"
        self.language = language  # Guardamos el idioma como propiedad

    async def request_otp(self, email: str) -> Any:
        url = self.host + self.path_send_otp
        payload = {
            "client_id": self.client_id,
            "email": email,
            "send": "code",
            "connection": "email",
        }
        return await self._make_request("POST", url, json=payload)

    async def validate_otp(self, email: str, otp: str) -> ValidateOtpResponse:
        url = self.host + self.path_validate_otp
        # fix source for the german market
        if self.lanugage != "de":
            source = "vorwerk_auth0_international"
        else:
            source = "vorwerk_auth0"
        payload = {
            "client_id": self.client_id,
            "scope": "openid profile email",
            "username": email,
            "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
            "otp": otp,
            "realm": "email",
            "platform": "android",
            "locale": self.language,  # Usando el idioma configurado
            "source": source,
        }
        response = await self._make_request("POST", url, json=payload)
        return ValidateOtpResponse(**response)

    async def _make_request(
        self, method: str, url: str, json: Optional[Dict[str, Any]] = None
    ) -> Any:
        headers = self._create_headers()
        self._logger.debug(
            "Making %s request to %s with payload %s", method, url, json
        )
        async with self._session.request(method, url, json=json, headers=headers) as response:
            if response.status == 200:
                self._logger.debug("Received response: %s", response)
                return await response.json()

            error_text = await response.text()
            self._logger.error(
                "Request failed: %s %s", response.status, error_text
            )
            response.raise_for_status()

    def _create_headers(self) -> Dict[str, str]:
        # Usamos el formato correcto para Accept-Language basado en el idioma configurado
        language_code = self.language
        # Si el idioma tiene formato simple (ej. "es"), lo convertimos a formato completo ("es-ES")
        if len(language_code) == 2:
            language_header = f"{language_code}-{language_code.upper()}"
        else:
            language_header = language_code
            
        return {
            "Content-Type": "application/json",
            "Accept-Language": language_header,
            "User-Agent": "okhttp/4.12.0",
        }
