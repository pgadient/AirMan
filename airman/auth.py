"""Password, session and login rate limiting.

Passwords are stored as scrypt hashes, session tokens only as SHA-256 hashes,
so the data directory never contains anything that can be used directly.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import hmac
import secrets
import time
from pathlib import Path

from .config import read_json, write_json_atomic

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SESSION_TTL = 365 * 24 * 3600  # stay logged in on the phone for a year
MAX_SESSIONS = 50


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=128 * 1024 * 1024, dklen=32
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        actual = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p))
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._auth_file = data_dir / "auth.json"
        self._sessions_file = data_dir / "sessions.json"
        self._auth: dict = read_json(self._auth_file, {})
        self._sessions: dict[str, float] = read_json(self._sessions_file, {})

    @property
    def has_password(self) -> bool:
        return bool(self._auth.get("password_hash"))

    def set_password(self, password: str) -> None:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        self._auth["password_hash"] = hash_password(password)
        write_json_atomic(self._auth_file, self._auth, private=True)
        # A new password logs out every device.
        self._sessions = {}
        write_json_atomic(self._sessions_file, self._sessions, private=True)

    def check_password(self, password: str) -> bool:
        stored = self._auth.get("password_hash")
        if not stored:
            return False
        return verify_password(password, stored)

    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions = {h: exp for h, exp in self._sessions.items() if exp > now}
        if len(self._sessions) >= MAX_SESSIONS:
            oldest = min(self._sessions, key=self._sessions.__getitem__)
            del self._sessions[oldest]
        self._sessions[_token_hash(token)] = now + SESSION_TTL
        write_json_atomic(self._sessions_file, self._sessions, private=True)
        return token

    def validate_session(self, token: str | None) -> bool:
        if not token or len(token) > 100:
            return False
        expiry = self._sessions.get(_token_hash(token))
        return expiry is not None and expiry > time.time()

    def revoke_session(self, token: str | None) -> None:
        if token and self._sessions.pop(_token_hash(token), None) is not None:
            write_json_atomic(self._sessions_file, self._sessions, private=True)


def _client_key(ip: str) -> str:
    """IPv6 clients can pick many addresses; treat a whole /64 as one client."""
    try:
        address = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return ip
    if address.version == 6:
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


class LoginLimiter:
    """Locks out a client after repeated wrong passwords (exponential back-off).

    An attempt counts as failed as soon as it starts, so many parallel requests
    can not slip past the lock while the slow password check is running. A
    global budget also slows down guessing spread over many addresses.
    """

    FREE_ATTEMPTS = 5
    GLOBAL_WINDOW = 600.0
    GLOBAL_LIMIT = 30  # failed attempts from all clients per window
    GLOBAL_LOCK = 60.0

    def __init__(self) -> None:
        self._failures: dict[str, tuple[int, float]] = {}
        self._recent: list[float] = []
        self._global_until = 0.0

    def retry_after(self, ip: str) -> float:
        _, locked_until = self._failures.get(_client_key(ip), (0, 0.0))
        return max(0.0, locked_until - time.time(), self._global_until - time.time())

    def attempt(self, ip: str) -> None:
        """Count an attempt as failed up front; succeeded() takes it back."""
        key = _client_key(ip)
        now = time.time()
        count, _ = self._failures.get(key, (0, 0.0))
        count += 1
        lock = 0.0
        if count >= self.FREE_ATTEMPTS:
            lock = min(3600.0, 30.0 * 2 ** (count - self.FREE_ATTEMPTS))
        self._failures[key] = (count, now + lock)
        self._recent = [t for t in self._recent if now - t < self.GLOBAL_WINDOW] + [now]
        if len(self._recent) >= self.GLOBAL_LIMIT:
            self._global_until = now + self.GLOBAL_LOCK

    # Kept for callers that report a failure after the fact.
    failed = attempt

    def succeeded(self, ip: str) -> None:
        self._failures.pop(_client_key(ip), None)
        if self._recent:
            self._recent.pop()
