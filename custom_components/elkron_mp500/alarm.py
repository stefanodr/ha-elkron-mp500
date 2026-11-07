"""Alarm detection from the input bytes of the 0x84 reply."""
from __future__ import annotations

from .const import INPUT_ALARM
from .protocol import STATE_ARMED


class AlarmTracker:
    """Work out which inputs raised the alarm from the panel readings.

    The panel sets bit 0x04 on the input that triggered the alarm and keeps it
    (as a memory) after the input closes. If that memory also survives the next
    arming, it must not look like a new alarm: the bits already set at the
    moment of arming are ignored until they clear.
    """

    def __init__(self) -> None:
        self._armed: bool | None = None
        self._stale: set[int] = set()

    def update(self, inputs: list[int], global_state: bytes) -> dict:
        armed = global_state[:2] == STATE_ARMED
        flagged = {i for i, value in enumerate(inputs, 1) if value & INPUT_ALARM}
        if armed and self._armed is False:
            # Disarmed -> armed: memory left over from before is not a new alarm.
            self._stale = set(flagged)
        elif not armed:
            self._stale = set()
        self._stale &= flagged  # a bit that cleared is no longer stale
        self._armed = armed
        active = sorted(flagged - self._stale) if armed else []
        return {
            "alarm_inputs": active,
            "triggered": bool(active),
            "alarm_memory": sorted(flagged),
        }
