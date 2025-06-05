from __future__ import annotations

import time
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from homeassistant.components.button import (
	ButtonEntity,
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

			ResetButton( hass, entry, uuid, f"{uuid}_reset", "button_reset" ),

			CustomButton( hass, entry, uuid, f"{uuid}_permit", "button_permit" ),
		] )

	signal[ "button" ] = async_dispatcher_connect( hass, ZBEACON_IR_EVENT_DEVICE_NEW, async_discover )

	async_add_entities( [] )

class CustomButton( ButtonEntity ):

	_attr_entity_category = EntityCategory.CONFIG

	_attr_has_entity_name = True

	_attr_icon = "mdi:remote-tv"

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

	def press( self ) -> None:

		conf = self.hass.data[ DOMAIN ][ self.entry.entry_id ].setdefault( "permits", {} )

		conf[ self.uuid ] = int( time.time() )

		_LOGGING.info( f"{self.uuid} Start binding ..." )

	@callback
	def __async_device_event( self, name: str, data ) -> None:

		if name == "LWT":

			self._attr_available = ( data == "Online" )

			self.async_write_ha_state()

class ResetButton( ButtonEntity ):

	_attr_entity_category = EntityCategory.DIAGNOSTIC

	_attr_has_entity_name = True

	_attr_icon = "mdi:delete"

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

	async def async_press( self ) -> None:

		ent_reg = er.async_get( self.hass )
		dev_reg = dr.async_get( self.hass )

		mqtt = self.hass.data[ DOMAIN ][ self.entry.entry_id ][ "mqtt" ]

		entity_entry = ent_reg.async_get( self.entity_id )

		devid = entity_entry.device_id

		if mqtt.remove_device( self.uuid ):

			dev_reg.async_remove_device( devid )

	@callback
	def __async_device_event( self, name: str, data ) -> None:

		if name == "LWT":

			self._attr_available = ( data == "Online" )

			self.async_write_ha_state()
