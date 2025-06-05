from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from homeassistant.components.sensor import (
	SensorEntity,
)

from .const import (
	DOMAIN,
	ZBEACON_IR_EVENT_DEVICE_NEW,
	ZBEACON_IR_EVENT_DEVICE_MSG,
)

_LOGGING = logging.getLogger( __name__ )

async def async_setup_entry( hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback ) -> None:

	signal = hass.data[ DOMAIN ][ entry.entry_id ].setdefault( "signal", {} )

	@callback
	def async_discover( conf ):

		uuid = conf.get( "mac" )

		async_add_entities( [

			CustomSensor( hass, entry, uuid, f"{uuid}_vendor", "sensor_vendor" )
		] )

	signal[ "sensor" ] = async_dispatcher_connect( hass, ZBEACON_IR_EVENT_DEVICE_NEW, async_discover )

	async_add_entities( [] )

class CustomSensor( SensorEntity ):

	_attr_entity_category = EntityCategory.DIAGNOSTIC

	_attr_has_entity_name = True

	_attr_icon = "mdi:factory"

	def __init__( self, hass: HomeAssistant, entry: ConfigEntry, uuid: str, unique_id: str, translation_key: str ):

		self.hass  = hass
		self.entry = entry
		self.uuid  = uuid

		self._attr_unique_id = unique_id

		self._attr_available = False

		self.translation_key = translation_key

		self._attr_device_info = DeviceInfo(
			connections = { ( CONNECTION_NETWORK_MAC, uuid ) },
			identifiers = { ( DOMAIN, uuid ) },
		)

		mqtt = hass.data[ DOMAIN ][ entry.entry_id ][ "mqtt" ]

		conf = mqtt.find_device( uuid )

		if isinstance( conf, dict ):

			self._attr_available = ( conf[ "LWT" ] == "Online" )

			irhvac = conf.get( "irhvac" )

			if isinstance( irhvac, dict ): self._attr_native_value = irhvac[ "Vendor" ]

	async def async_added_to_hass( self ) -> None:

		self._event_signal = async_dispatcher_connect(
			self.hass,
			f"{ZBEACON_IR_EVENT_DEVICE_MSG}_{self.uuid}",
			self.__async_device_event
		)

		_LOGGING.debug( f"async_added_to_hass( {self._attr_unique_id} )" )

	async def async_will_remove_from_hass( self ) -> None:

		if self._event_signal: self._event_signal()

		_LOGGING.debug( f"async_will_remove_from_hass( {self._attr_unique_id} )" )

	@callback
	def __async_device_event( self, name: str, data ) -> None:

		if name == "LWT":

			self._attr_available = ( data == "Online" )

			self.async_write_ha_state()

		elif name == "SET":

			mqtt = self.hass.data[ DOMAIN ][ self.entry.entry_id ][ "mqtt" ]

			conf = mqtt.find_device( self.uuid )

			if isinstance( conf, dict ):

				irhvac = conf.get( "irhvac" )

				if isinstance( irhvac, dict ):
					
					self._attr_native_value = irhvac[ "Vendor" ]

					self.async_write_ha_state()
