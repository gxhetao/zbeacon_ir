
from homeassistant.const import Platform

DOMAIN = "zbeacon_ir"

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SENSOR,
]

TASMOTA_DISCOVERY_TOPIC = "tasmota/discovery/+/config"

ZBEACON_IR_EVENT_DEVICE_MSG = "zbeacon_ir_device_msg"
ZBEACON_IR_EVENT_DEVICE_NEW = "zbeacon_ir_device_new"
