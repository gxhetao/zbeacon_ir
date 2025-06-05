from __future__ import annotations

import logging

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from homeassistant.components.climate import (
	ClimateEntity,
	ClimateEntityFeature,
	HVACMode,
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

			CustomClimate( hass, entry, uuid, f"{uuid}_irhvac", "climate_irhvac" )
		] )

	signal[ "climate" ] = async_dispatcher_connect( hass, ZBEACON_IR_EVENT_DEVICE_NEW, async_discover )

	async_add_entities( [] )

class CustomClimate( ClimateEntity ):

	_attr_fan_modes = [
		"auto",
		"low",
		"medium",
		"high"
	]

	_attr_has_entity_name = True

	_attr_hvac_modes = [
		HVACMode.AUTO,
		HVACMode.OFF,
		HVACMode.COOL,
		HVACMode.HEAT,
		HVACMode.DRY,
		HVACMode.FAN_ONLY
	]

	_attr_icon = "mdi:remote"

	_attr_swing_horizontal_modes = [
		"on",
		"off"
	]

	_attr_swing_modes = [
		"on",
		"off"
	]

	_attr_max_temp  = 30.0
	_attr_min_temp  = 16.0
	_attr_precision = 1.0

	_attr_target_temperature      = 26.0
	_attr_target_temperature_low  = 16.0
	_attr_target_temperature_high = 30.0
	_attr_target_temperature_step = 1.0

	_attr_temperature_unit = UnitOfTemperature.CELSIUS

	___hvac_mode_map = {
		"off":        HVACMode.OFF,
		"stop":       HVACMode.OFF,
		"auto":       HVACMode.AUTO,
		"automatic":  HVACMode.AUTO,
		"cool":       HVACMode.COOL,
		"cooling":    HVACMode.COOL,
		"heat":       HVACMode.HEAT,
		"heating":    HVACMode.HEAT,
		"dry":        HVACMode.DRY,
		"drying":     HVACMode.DRY,
		"dehumidify": HVACMode.DRY,
		"fan":        HVACMode.FAN_ONLY,
		"fanonly":    HVACMode.FAN_ONLY,
		"fan_only":   HVACMode.FAN_ONLY,
	}

	__fan_mode_map = {
		"auto":      "auto",
		"automatic": "auto",
		"1":         "low",
		"min":       "low",
		"minimum":   "low",
		"lowest":    "low",
		"2":         "low",
		"low":       "low",
		"3":         "medium",
		"mid":       "medium",
		"med":       "medium",
		"medium":    "medium",
		"4":         "high",
		"hi":        "high",
		"high":      "high",
		"5":         "high",
		"max":       "high",
		"maximum":   "high",
		"highest":   "high",
	}

	def __init__( self, hass: HomeAssistant, entry: ConfigEntry, uuid: str, unique_id: str, translation_key: str ):

		self.hass  = hass
		self.entry = entry
		self.uuid  = uuid

		self._attr_unique_id = unique_id

		self._attr_available = False

		self.translation_key = translation_key

		self._attr_hvac_mode = HVACMode.AUTO

		self._attr_fan_mode = "auto"

		self._attr_supported_features = (
			ClimateEntityFeature.TARGET_TEMPERATURE |
			ClimateEntityFeature.TARGET_TEMPERATURE_RANGE |
			ClimateEntityFeature.FAN_MODE
		)

		self._attr_device_info = DeviceInfo(
			connections = { ( CONNECTION_NETWORK_MAC, uuid ) },
			identifiers = { ( DOMAIN, uuid ) },
		)

		mqtt = hass.data[ DOMAIN ][ entry.entry_id ][ "mqtt" ]

		conf = mqtt.find_device( uuid )

		if isinstance( conf, dict ):

			irhvac = conf.get( "irhvac" )

			if isinstance( irhvac, dict ):

				self._attr_available = True

				power = irhvac.get( "Power", "Off" ).lower()

				self._attr_target_temperature = irhvac.get( "Temp" )

				if power == "off" or power == "no" or power == "false" or power == '0':

					self._attr_hvac_mode = HVACMode.OFF
				else:
					self._attr_hvac_mode = self.__to_attr_hvac_mode( irhvac.get( "Mode" ) )

				self._attr_fan_mode = self.__to_attr_fan_mode( irhvac.get( "FanSpeed" ) )

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

	async def async_set_fan_mode( self, mode: str ) -> None:

		mqtt = self.hass.data[ DOMAIN ][ self.entry.entry_id ][ "mqtt" ]

		conf = mqtt.find_device( self.uuid ).get( "irhvac" )

		if not isinstance( conf, dict ): return

		conf[ "FanSpeed" ] = mode

		# await mqtt.async_cache_dumps()

		if self.__to_attr_hvac_mode( conf[ "Mode" ] ) != HVACMode.OFF:

			await mqtt.async_cmnd_irhvac( self.uuid )

		self._attr_fan_mode = mode

		self.async_write_ha_state()

	async def async_set_hvac_mode( self, mode: HVACMode ) -> None:

		mqtt = self.hass.data[ DOMAIN ][ self.entry.entry_id ][ "mqtt" ]

		conf = mqtt.find_device( self.uuid ).get( "irhvac" )

		if not isinstance( conf, dict ): return

		if mode == HVACMode.OFF:

			conf[ "Power" ] = "Off"
			conf[ "Mode"  ] = "Off"
		else:
			conf[ "Power" ] = "On"

			if mode == HVACMode.AUTO:
				conf[ "Mode" ] = "Auto"
			elif mode == HVACMode.COOL:
				conf[ "Mode" ] = "Cool"
			elif mode == HVACMode.DRY:
				conf[ "Mode" ] = "Dry"
			elif mode == HVACMode.FAN_ONLY:
				conf[ "Mode" ] = "Fan"
			elif mode == HVACMode.HEAT:
				conf[ "Mode" ] = "Heat"

		# await mqtt.async_cache_dumps()

		await mqtt.async_cmnd_irhvac( self.uuid )

		self._attr_hvac_mode = mode

		self.async_write_ha_state()

	async def async_set_temperature( self, **kwargs: Any) -> None:

		temp = int( kwargs.get( ATTR_TEMPERATURE ) )

		mqtt = self.hass.data[ DOMAIN ][ self.entry.entry_id ][ "mqtt" ]

		conf = mqtt.find_device( self.uuid ).get( "irhvac" )

		if not isinstance( conf, dict ): return

		conf[ "Celsius" ] = "On"
		conf[ "Temp"    ] = temp

		# await mqtt.async_cache_dumps()

		if self.__to_attr_hvac_mode( conf[ "Mode" ] ) != HVACMode.OFF:

			await mqtt.async_cmnd_irhvac( self.uuid )

		self._attr_target_temperature = temp

		self.async_write_ha_state()

	def __to_attr_hvac_mode( self, mode: str ):

		if not isinstance( mode, str ):

			return HVACMode.OFF

		return self.___hvac_mode_map.get( mode.lower(), HVACMode.OFF )

	def __to_attr_fan_mode( self, mode: str ):

		if not isinstance( mode, str ):

			return "auto"

		return self.__fan_mode_map.get( mode.lower(), "auto" )

	@callback
	def __async_device_event( self, name: str, data ) -> None:

		if name == "LWT":

			mqtt = self.hass.data[ DOMAIN ][ self.entry.entry_id ][ "mqtt" ]

			conf = mqtt.find_device( self.uuid )

			if data == "Online":

				self._attr_available = ( "irhvac" in conf )
			else:
				self._attr_available = False

			self.async_write_ha_state()

		elif name == "SET":

			self._attr_available = True

			power = data.get( "Power", "Off" ).lower()

			self._attr_target_temperature = data.get( "Temp" )

			if power == "off" or power == "no" or power == "false" or power == '0':

				self._attr_hvac_mode = HVACMode.OFF
			else:
				self._attr_hvac_mode = self.__to_attr_hvac_mode( data.get( "Mode" ) )

			self._attr_fan_mode = self.__to_attr_fan_mode( data.get( "FanSpeed" ) )

			self.async_write_ha_state()
