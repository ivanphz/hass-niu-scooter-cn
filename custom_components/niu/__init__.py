"""The NIU integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import NiuDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type MyConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold runtime data."""

    coordinator: DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Set up NIU integration from a config entry."""

    coordinator = NiuDataCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    if coordinator.last_update_success is False:
        raise ConfigEntryNotReady

    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    config_entry.runtime_data = RuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # 释放 requests.Session 的连接池，避免反复重载时泄漏 socket
    if unload_ok:
        runtime = getattr(config_entry, "runtime_data", None)
        if runtime is not None:
            await hass.async_add_executor_job(runtime.coordinator.api.close)

    return unload_ok
