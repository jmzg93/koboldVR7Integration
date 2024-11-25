from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
  """Configuración inicial desde YAML (si se soporta)."""
  return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
  """Configura la integración desde una entrada de configuración."""
  hass.data.setdefault(DOMAIN, {})
  hass.data[DOMAIN][entry.entry_id] = entry.data

  # Configurar la plataforma vacuum
  await hass.config_entries.async_forward_entry_setup(entry, "vacuum")

  return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
  """Desinstala una entrada de configuración."""
  await hass.config_entries.async_forward_entry_unload(entry, "vacuum")
  hass.data[DOMAIN].pop(entry.entry_id)
  return True