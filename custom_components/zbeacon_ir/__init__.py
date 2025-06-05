from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
	DOMAIN, 
    PLATFORMS,
)

from .mqtt import MQTTClient

_LOGGING = logging.getLogger( __name__ )

async def async_setup_entry( hass: HomeAssistant, entry: ConfigEntry ) -> bool:

    hass.data.setdefault( DOMAIN, {} )

    mqtt_exists = False

    for config_entry in hass.config_entries.async_entries():

        if config_entry.domain == "mqtt":

            mqtt_exists = True

            break

    if not mqtt_exists:

        _LOGGING.warning( "MQTT Integration Is Not Configured." )

        from homeassistant.components import persistent_notification

        persistent_notification.async_create(
            hass,
            (
                "ZbeaconIR Integration requires the **MQTT integration** to be configured "
                "before it can be set up. Please add the MQTT integration from "
                "Settings -> Devices & Services -> Add Integration first."
            ),
            "ZbeaconIR Integration Setup Failed: MQTT Required",
            f"{DOMAIN}_mqtt_required",
        )

        return False

    _LOGGING.info( f"Create Entry {entry.entry_id}" )

    hass.data[ DOMAIN ][ entry.entry_id ] = {}

    _LOGGING.info( f"Load Profile {DOMAIN}_{entry.entry_id}" )

    store = Store( hass, 1, f"{DOMAIN}_{entry.entry_id}" )

    cache = await store.async_load()

    if cache is None: cache = {}

    await store.async_save( cache )

    hass.data[ DOMAIN ][ entry.entry_id ][ "store" ] = store
    hass.data[ DOMAIN ][ entry.entry_id ][ "cache" ] = cache

    await hass.config_entries.async_forward_entry_setups( entry, PLATFORMS )

    mqtt_client = MQTTClient( hass, entry )

    await mqtt_client.async_init()

    hass.data[ DOMAIN ][ entry.entry_id ][ "mqtt" ] = mqtt_client

    return True

async def async_unload_entry( hass: HomeAssistant, entry: ConfigEntry ) -> bool:

    _LOGGING.warning( f"Unload Entry {entry.entry_id}" )

    store = hass.data.get( DOMAIN, {} ).get( entry.entry_id, {} ).get( "store" )

    if store:

        _LOGGING.warning( f"Remove Profile {DOMAIN}_{entry.entry_id}" )

        await store.async_remove()

    if entry.entry_id in hass.data.get( DOMAIN, {} ):

        signal = hass.data[ DOMAIN ][ entry.entry_id ].setdefault( "signal", {} )

        for k, v in signal.items():

            _LOGGING.debug( f"Clean Signal Slot {k}" )

            v()

        hass.data[ DOMAIN ].pop( entry.entry_id )

    await hass.config_entries.async_unload_platforms( entry, PLATFORMS )

    return True
