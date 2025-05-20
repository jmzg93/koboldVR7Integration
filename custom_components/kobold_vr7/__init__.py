"""
Este módulo inicializa la integración Kobold VR7 en Home Assistant.

Proporciona métodos para configurar y desinstalar la integración.
"""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["vacuum"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configura la integración desde una entrada de configuración."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Usar async_forward_entry_setups en lugar de async_forward_entry_setup
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.debug(f"Successfully loaded {DOMAIN} integration")
        return True
    except Exception as e:
        _LOGGER.error(f"Error setting up {DOMAIN} integration: {e}")
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Desinstala una entrada de configuración."""
    try:
        unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if unloaded:
            hass.data[DOMAIN].pop(entry.entry_id)
        return unloaded
    except Exception as e:
        _LOGGER.error(f"Error unloading {DOMAIN} integration: {e}")
        return False
