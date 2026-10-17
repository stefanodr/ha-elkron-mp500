"""Optional Home Assistant side code asked before disarming.

The panel's TCP disarm command carries no user code, so the check is done here:
it stops an unwanted disarm from the dashboard, scripts or voice assistants. It
is a software gate, not the panel's own protection. Only a salted hash of the
code is stored, never the code itself.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time

CODE_LENGTH = 6
PBKDF2_ROUNDS = 120_000
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


def valid_code(code: str | None) -> bool:
    return bool(re.fullmatch(rf"\d{{{CODE_LENGTH}}}", code or ""))


def hash_code(code: str, salt: bytes | None = None) -> tuple[str, str]:
    """Return (salt_hex, hash_hex)."""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def verify_code(code: str | None, salt_hex: str, hash_hex: str) -> bool:
    if not valid_code(code):
        return False
    _, digest = hash_code(code, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest, hash_hex)


class AttemptLimiter:
    """Block the disarm for a while after too many wrong codes in a row."""

    def __init__(self, max_attempts: int = MAX_ATTEMPTS, lockout: int = LOCKOUT_SECONDS) -> None:
        self.max_attempts = max_attempts
        self.lockout = lockout
        self._failures = 0
        self._locked_until = 0.0

    def seconds_locked(self) -> int:
        remaining = self._locked_until - time.monotonic()
        return int(remaining) + 1 if remaining > 0 else 0

    def failed(self) -> None:
        self._failures += 1
        if self._failures >= self.max_attempts:
            self._failures = 0
            self._locked_until = time.monotonic() + self.lockout

    def succeeded(self) -> None:
        self._failures = 0
        self._locked_until = 0.0
