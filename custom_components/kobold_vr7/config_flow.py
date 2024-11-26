"""
Este módulo maneja el flujo de configuración para la integración Kobold VR7 en Home Assistant.
"""

import voluptuous as vol
import logging
from homeassistant import config_entries
from .const import DOMAIN, CONF_EMAIL, CONF_OTP, CONF_ID_TOKEN, AUTH_HOST
from .service.user_data_service import UserDataService
from .api.user_api_client import UserApiClient

_LOGGER = logging.getLogger(__name__)


class KoboldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Maneja el flujo de configuración para Kobold."""

    VERSION = 1

    def __init__(self):
        self.email = None
        self.id_token = None
        self.user_data_service = None

    async def async_step_user(self, user_input=None):
        """Primer paso en el flujo de configuración: solicitar el correo electrónico."""
        errors = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            await self.async_set_unique_id(self.email)
            self._abort_if_unique_id_configured()

            # Crear instancia de UserDataService
            try:
                session = self.hass.helpers.aiohttp_client.async_get_clientsession()
                user_api_client = UserApiClient(
                    session,
                    host=AUTH_HOST,
                    path_send_otp="/passwordless/start",
                    path_validate_otp="/oauth/token"
                )
                self.user_data_service = UserDataService(user_api_client)

                # Enviar el OTP
                await self.user_data_service.send_otp_mail(self.email)
                return await self.async_step_otp()
            except Exception as e:
                _LOGGER.error("Error al enviar OTP: %s", e)
                errors["base"] = "cannot_send_otp"

        data_schema = vol.Schema({vol.Required(CONF_EMAIL): str})

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_otp(self, user_input=None):
        """Segundo paso: solicitar el código OTP."""
        errors = {}

        if user_input is not None:
            otp = user_input[CONF_OTP]
            try:
                validate_response = await self.user_data_service.validate_otp(self.email, otp)
                self.id_token = validate_response.id_token

                return self.async_create_entry(
                    title=f"Kobold ({self.email})",
                    data={
                        CONF_EMAIL: self.email,
                        CONF_ID_TOKEN: self.id_token
                    }
                )
            except Exception as e:
                _LOGGER.error("Error al validar OTP: %s", e)
                errors["base"] = "invalid_otp"

        data_schema = vol.Schema({vol.Required(CONF_OTP): str})

        return self.async_show_form(step_id="otp", data_schema=data_schema, errors=errors)
