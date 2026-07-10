"""Config flow: single-instance, local push. Discovery happens at runtime."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import udp
from .const import DOMAIN


class AtombergLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atomberg Local."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Atomberg Local", data={})

        # Quick Wi-Fi peek so the user sees it's working (BLE-only fans appear later).
        try:
            found = await udp.async_discover(4.0)
        except OSError:
            found = {}

        return self.async_show_form(
            step_id="user",
            description_placeholders={"count": str(len(found))},
        )
