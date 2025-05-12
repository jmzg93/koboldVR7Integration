"""
Este módulo inicializa la integración Kobold VR7 en Home Assistant.

Proporciona métodos para configurar y desinstalar la integración.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .service.websocket_service import WebSocketService
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configura la integración desde una entrada de configuración."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Usar async_forward_entry_setups en lugar de async_forward_entry_setup
    await hass.config_entries.async_forward_entry_setups(entry, ["vacuum"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Desinstala una entrada de configuración."""
    await hass.config_entries.async_unload_platforms(entry, ["vacuum"])
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
