"""Constants for foxess_modbus."""
# Base component constants
NAME = "foxess_modbus"
DOMAIN = "foxess_modbus"
DOMAIN_DATA = f"{DOMAIN}_data"

ISSUE_URL = "https://github.com/nathanmarlor/foxess_modbus/issues"

# Icons
ICON = "mdi:format-quote-close"

# Platforms
SENSOR = "sensor"
BINARY_SENSOR = "binary_sensor"
SELECT = "select"
NUMBER = "number"
PLATFORMS = [SENSOR, BINARY_SENSOR, SELECT, NUMBER]
ATTR_ENTRY_TYPE = "entry_type"

# Modbus Options
FRIENDLY_NAME = "friendly_name"
MODBUS_SLAVE = "modbus_slave"
MODBUS_DEVICE = "modbus_device"
MODBUS_TYPE = "modbus_type"
MODBUS_SERIAL_BAUD = "modbus_serial_baud"
POLL_RATE = "poll_rate"
MAX_READ = "max_read"

INVERTER_MODEL = "inverter_model"
INVERTER_BASE = "inverter_base"
INVERTER_CONN = "inverter_conn"
INVERTERS = "inverters"

CONFIG_SAVE_TIME = "save_time"

HOST = "host"
TCP = "TCP"
UDP = "UDP"
SERIAL = "SERIAL"

CONTROLLER = "controllers"
CONFIG = "config"
INVERTER = "inverter"
CONNECTION = "connection"
MODBUS = "modbus"

ENERGY_DASHBOARD = "energy_dashboard"

# Defaults
DEFAULT_NAME = DOMAIN

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
