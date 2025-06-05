from __future__ import annotations

import json
import time
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from homeassistant.components import mqtt
from homeassistant.components.mqtt import (
	async_prepare_subscribe_topics,
	async_subscribe_topics,
	async_unsubscribe_topics,
)

from .const import (
	DOMAIN,
	TASMOTA_DISCOVERY_TOPIC,
	ZBEACON_IR_EVENT_DEVICE_NEW,
	ZBEACON_IR_EVENT_DEVICE_MSG,
)

_LOGGING = logging.getLogger( __name__ )

class MQTTClient:

	def __init__( self, hass: HomeAssistant, entry: ConfigEntry ):

		self.hass  = hass
		self.entry = entry

		self._store = hass.data[ DOMAIN ][ entry.entry_id ][ "store" ]
		self._cache = hass.data[ DOMAIN ][ entry.entry_id ][ "cache" ]

		self._sub_state = None

		self._devices = {}

		for device in self._cache.values():

			device[ "LWT" ] = None

			self._devices[ device.get( "uuid"  ) ] = device
			self._devices[ device.get( "topic" ) ] = device

	async def async_init( self ) -> None:

		_LOGGING.info( "MQTT Subscribe Topics" )

		topics = {

			"tasmota_discovery": {
				"topic": TASMOTA_DISCOVERY_TOPIC,
				"msg_callback": self.__on_discovery,
				"qos": 0,
				"event_loop_safe": True
			},
			"tasmota_stat": {
				"topic": "stat/#",
				"msg_callback": self.__on_tasmota_stat,
				"qos": 0,
				"event_loop_safe": True
			},
			"tasmota_tele": {
				"topic": "tele/#",
				"msg_callback": self.__on_tasmota_tele,
				"qos": 0,
				"event_loop_safe": True
			}
		}

		self._sub_state = await self._subscribe_topics( self._sub_state, topics )

		self.entry.async_on_unload( self.async_shutdown )

	async def async_cache_dumps( self ) -> None:

		_LOGGING.info( f"Update Profile {DOMAIN}_{self.entry.entry_id}" )

		await self._store.async_save( self._cache )

	async def async_cmnd_irhvac( self, uuid, qos: int | None = None, retain: bool | None = None ) -> None:

		device = self._devices.get( uuid )

		if not isinstance( device, dict ): return

		topic = device.get( "topic" )

		if not isinstance( topic, str ): return

		# payload = device.get( "irhvac" )

		# if not isinstance( payload, dict ): return

		irhvac = device.get( "irhvac" )

		payload = {
			"Vendor":   irhvac[ "Vendor"   ],
			"Power":    irhvac[ "Power"    ],
			"Mode":     irhvac[ "Mode"     ],
			"FanSpeed": irhvac[ "FanSpeed" ],
			"Celsius":  irhvac[ "Celsius"  ],
			"Temp":     irhvac[ "Temp"     ],
		}

		await mqtt.async_publish( self.hass, f"cmnd/{topic}/IRHVAC", json.dumps( payload ), qos, retain )

	async def async_command( self, uuid: str, cmnd: str, payload: mqtt.PublishPayloadType, qos: int | None = None, retain: bool | None = None ) -> None:

		device = self._devices.get( uuid )

		if not isinstance( device, dict ): return

		topic = device.get( "topic" )

		if not isinstance( topic, str ): return

		await mqtt.async_publish( self.hass, f"cmnd/{topic}/{cmnd}", payload, qos, retain )

	async def async_publish( self, topic: str, payload: mqtt.PublishPayloadType, qos: int | None = None, retain: bool | None = None ) -> None:

		await mqtt.async_publish( self.hass, topic, payload, qos, retain )

	async def async_shutdown( self ) -> bool:

		if self._sub_state:

			_LOGGING.warning( "MQTT Unsubscribe Topics" )

			async_unsubscribe_topics( self.hass, self._sub_state )

			self._sub_state = None

		return True

	def find_device( self, uuid ):

		return self._devices.get( uuid )

	def remove_device( self, uuid ):

		device = self._devices.get( uuid )

		if device is None: return False

		uuid = device[ "uuid"  ]
		name = device[ "topic" ]

		self.hass.async_create_task( self.async_command( uuid, "Reset", "1" ) )

		self.hass.async_create_task( self.async_publish( f"tasmota/discovery/{uuid}/config", None, None, True ) )

		self._cache.pop( uuid, None )

		self._devices.pop( uuid, None )
		self._devices.pop( name, None )

		self.hass.async_create_task( self.async_cache_dumps() )

		return True

	async def _subscribe_topics( self, sub_state, topics ):

		prepared_sub_state = async_prepare_subscribe_topics( self.hass, sub_state, topics )

		await async_subscribe_topics( self.hass, prepared_sub_state )

		return prepared_sub_state

	async def __async_device_create( self, conf: dict ):

		device_registry = dr.async_get( self.hass )

		device_registry.async_get_or_create(
			config_entry_id   = self.entry.entry_id,
			configuration_url = f"http://{conf.get( 'ip' )}/",
			connections       = { ( dr.CONNECTION_NETWORK_MAC, conf.get( "mac" ) ) },
			identifiers       = { ( DOMAIN, conf.get( "mac" ) ) },
			manufacturer      = "Zbeacon",
			model             = conf.get( "md" ),
			name              = conf.get( "hn" ),
			sw_version        = conf.get( "sw" ),
		)

		async_dispatcher_send( self.hass, ZBEACON_IR_EVENT_DEVICE_NEW, conf )

	@callback
	def __on_discovery( self, msg: mqtt.ReceivePayloadType ) -> None:

		if not msg.payload: return

		payload = json.loads( msg.payload )

		if not isinstance( payload, dict ): return

		uuid  = payload.get( "mac"  )
		topic = payload.get( "t"    )
		model = payload.get( "md"   )

		if ( uuid is None ) or ( topic is None ) or ( model is None ) or model != "Athom lR Remote": return

		device = self._cache.get( uuid )

		if device is None:

			_LOGGING.info( f"Device Discovery {uuid}" )

			status = self._devices.get( topic, {} ).get( "LWT" )

			device = { "uuid": uuid, "topic": topic, "LWT": status }

			self._cache[ uuid ] = device

			self._devices[ uuid  ] = device
			self._devices[ topic ] = device

			self.hass.async_create_task( self.async_cache_dumps() )

		self.hass.async_create_task( self.__async_device_create( payload ) )

	@callback
	def __on_tasmota_stat( self, msg: mqtt.ReceivePayloadType ) -> None:

		topic = None

		payload = None

		try:
			topic = msg.topic.split( '/' )

			payload = json.loads( msg.payload )

		except:
			payload = msg.payload

		device = self._devices.get( topic[ 1 ] )

		if not isinstance( device, dict ):

			return

		uuid = device.get( "uuid" )

		if topic[ 2 ] == "RESULT" and isinstance( payload, dict ):

			irhvac = payload.get( "IRHVAC" )

			if not isinstance( irhvac, dict ): return

			device[ "irhvac" ] = irhvac

			self.hass.async_create_task( self.async_cache_dumps() )

			async_dispatcher_send( self.hass, f"{ZBEACON_IR_EVENT_DEVICE_MSG}_{uuid}", "SET", irhvac )

	@callback
	def __on_tasmota_tele( self, msg: mqtt.ReceivePayloadType ) -> None:

		topic = None

		payload = None

		try:
			topic = msg.topic.split( '/' )

			payload = json.loads( msg.payload )

		except:
			payload = msg.payload

		device = self._devices.get( topic[ 1 ] )

		if not isinstance( device, dict ):

			if topic[ 2 ] == "LWT":

				self._devices[ topic[ 1 ] ] = { "LWT": payload }

			return

		uuid = device.get( "uuid" )

		if topic[ 2 ] == "LWT":

			if not isinstance( uuid, str ):

				device[ "LWT" ] = payload

			elif device[ "LWT" ] != payload:

				device[ "LWT" ] = payload

				self.hass.async_create_task( self.async_cache_dumps() )

				async_dispatcher_send( self.hass, f"{ZBEACON_IR_EVENT_DEVICE_MSG}_{uuid}", "LWT", payload )

		elif topic[ 2 ] == "RESULT" and isinstance( payload, dict ):

			irhvac = payload.get( "IrReceived", {} ).get( "IRHVAC" )

			if not isinstance( irhvac, dict ): return

			permits = self.hass.data[ DOMAIN ][ self.entry.entry_id ].get( "permits", {} )

			timestamp = permits.get( uuid )

			if not isinstance( timestamp, int ): return

			if int( time.time() ) - timestamp > 60: return

			del permits[ uuid ]

			device[ "irhvac" ] = irhvac

			self.hass.async_create_task( self.async_cache_dumps() )

			self.hass.async_create_task( self.async_cmnd_irhvac( uuid ) )

			async_dispatcher_send( self.hass, f"{ZBEACON_IR_EVENT_DEVICE_MSG}_{uuid}", "SET", irhvac )
