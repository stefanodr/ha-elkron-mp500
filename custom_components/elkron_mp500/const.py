DOMAIN = "elkron_mp500"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_NAMES = "names"
CONF_TYPES = "types"
CONF_STRUCTURE = "structure"
CONF_WEB_USER = "web_user"
CONF_WEB_PASSWORD = "web_password"
CONF_REFRESH = "refresh_structure"
CONF_DISARM_CODE = "disarm_code"
CONF_CLEAR_DISARM_CODE = "clear_disarm_code"
CONF_DISARM_SALT = "disarm_code_salt"
CONF_DISARM_HASH = "disarm_code_hash"
CONF_PLANT_ID = "plant_id"
CONF_TECH_CODE = "tech_code"

from .protocol import DEFAULT_PLANT_ID, DEFAULT_TECH_CODE  # noqa: E402,F401

DEFAULT_HOST = ""
DEFAULT_PORT = 5555
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 300
MAX_NAMED_INPUTS = 16

# Value of an input byte in the 0x84 reply: 0x02 = open, 0x00 = closed
# (verified on inputs 1 and 7 in the 2026-10-15 captures).
INPUT_OPEN = 0x02

# Input type = Home Assistant device class, so states read "Aperto/Chiuso" or
# "Rilevato/Non rilevato" instead of "Acceso/Spento". Default: opening.
INPUT_TYPES = ("opening", "door", "window", "motion")
DEFAULT_INPUT_TYPE = "opening"


# Predictable entity ids, independent of the (editable) names:
#   alarm_control_panel.elkron_mp500_sistema, binary_sensor.elkron_mp500_ingresso_N
# They are part of the public interface (dashboards, automations): never change them.
ENTITY_PREFIX = "elkron_mp500"
ALARM_ENTITY_ID = f"alarm_control_panel.{ENTITY_PREFIX}_sistema"


def input_entity_id(input_id: int) -> str:
    return f"binary_sensor.{ENTITY_PREFIX}_ingresso_{input_id}"
