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

# Bits of an input byte in the 0x84 reply. 0x02 = open, 0x00 = closed
# (verified on inputs 1 and 7 in the 2026-10-15 captures). 0x04 = this input
# raised the alarm (seen in the 2026-11 controlled test: 02 open, 06 open and
# in alarm, 04 closed again but remembered). Other bits are not known yet.
INPUT_OPEN = 0x02
INPUT_ALARM = 0x04

# Input type = Home Assistant device class, so states read "Aperto/Chiuso" or
# "Rilevato/Non rilevato" instead of "Acceso/Spento". Default: opening.
INPUT_TYPES = ("opening", "door", "window", "motion")
DEFAULT_INPUT_TYPE = "opening"


# Predictable entity ids, independent of the (editable) names:
#   alarm_control_panel.elkron_mp500_sistema, binary_sensor.elkron_mp500_ingresso_N
# They are part of the public interface (dashboards, automations): never change them.
ENTITY_PREFIX = "elkron_mp500"
ALARM_ENTITY_ID = f"alarm_control_panel.{ENTITY_PREFIX}_sistema"
ALARM_MEMORY_ENTITY_ID = f"binary_sensor.{ENTITY_PREFIX}_memoria_allarme"
ALARM_EVENT_ENTITY_ID = f"event.{ENTITY_PREFIX}_allarme"

# Event types fired by the event entity.
EVENT_ALARM_TRIGGERED = "alarm_triggered"
EVENT_ALARM_STOPPED = "alarm_stopped"

# Repairs: report a panel that has not answered for this long.
CONNECTION_LOST_AFTER = 300  # seconds
ISSUE_CONNECTION_LOST = "connection_lost"


def input_entity_id(input_id: int) -> str:
    return f"binary_sensor.{ENTITY_PREFIX}_ingresso_{input_id}"
