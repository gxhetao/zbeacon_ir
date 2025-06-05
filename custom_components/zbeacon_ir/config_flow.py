from __future__ import annotations

import logging

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

_LOGGING = logging.getLogger( __name__ )

class FlowHandler( ConfigFlow, domain = DOMAIN ):

    VERSION = 1

    def __init__( self ) -> None:

        _LOGGING.debug( "ConfigFlow Initialize" )

    async def async_step_user( self, user_input: dict[ str, Any ] | None = None ) -> ConfigFlowResult:

        if self._async_current_entries():

            return self.async_abort( reason = "single_instance_allowed" )

        return self.async_create_entry( title = "ZbeaconIR", data = {} )
