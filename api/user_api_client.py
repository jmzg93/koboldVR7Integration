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
  ):
    self._session = session
    self.host = host
    self.path_send_otp = path_send_otp
    self.path_validate_otp = path_validate_otp
    self._logger = logging.getLogger(__name__)
    self.client_id = "FPSBig7ePFvAE6q99cEDROM8gYUTygkD"

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
    payload = {
      "client_id": self.client_id,
      "scope": "openid profile email",
      "username": email,
      "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
      "otp": otp,
      "realm": "email",
      "platform": "android",
      "locale": "es",
      "source": "vorwerk_auth0_international",
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
      else:
        error_text = await response.text()
        self._logger.error(
            "Request failed: %s %s", response.status, error_text
        )
        response.raise_for_status()

  def _create_headers(self) -> Dict[str, str]:
    return {
      "Content-Type": "application/json",
      "Accept-Language": "es-ES",
      "User-Agent": "okhttp/4.12.0",
    }