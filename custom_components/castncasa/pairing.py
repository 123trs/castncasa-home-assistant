"""Pairing and device authentication for CastnCasa."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Any
from urllib.parse import urlencode

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    API_CLOCK_SKEW_SECONDS,
    API_NONCE_TTL_SECONDS,
    PAIRING_MAX_ATTEMPTS,
    PAIRING_TTL_SECONDS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .protocol import (
    api_signature,
    b64url,
    b64url_decode,
    derive_api_key,
    encrypt_device_token,
    pairing_proof,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class PairingSession:
    pairing_id: str
    secret: bytes
    base_url: str
    created_at: datetime
    expires_at: datetime
    attempts: int = 0

    @property
    def secret_text(self) -> str:
        return b64url(self.secret)

    @property
    def pair_uri(self) -> str:
        query = urlencode(
            {
                "v": "1",
                "ha": self.base_url,
                "id": self.pairing_id,
                "secret": self.secret_text,
            }
        )
        return f"castncasa://pair?{query}"

    @property
    def pairing_page_url(self) -> str:
        return (
            f"{self.base_url.rstrip('/')}/api/castncasa/pairing/{self.pairing_id}"
            f"?secret={self.secret_text}"
        )

    @property
    def pairing_qr_url(self) -> str:
        return (
            f"{self.base_url.rstrip('/')}/api/castncasa/pairing/{self.pairing_id}/qr.svg"
            f"?secret={self.secret_text}"
        )


class PairingError(Exception):
    """Raised for invalid or expired pairing requests."""


class DeviceAuthError(Exception):
    """Raised for invalid API authentication."""


class CastnCasaPairingManager:
    """Manage one-time pairings and paired devices."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._devices: dict[str, dict[str, Any]] = {}
        self._pairings: dict[str, PairingSession] = {}
        self._nonces: dict[str, dict[str, datetime]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        devices = data.get("devices", {})
        if isinstance(devices, dict):
            self._devices = devices

    async def _async_save(self) -> None:
        await self._store.async_save({"devices": self._devices})

    def _cleanup_pairings(self) -> None:
        now = _utcnow()
        for key in [key for key, value in self._pairings.items() if value.expires_at <= now]:
            self._pairings.pop(key, None)

    def create_pairing(self, base_url: str) -> PairingSession:
        self._cleanup_pairings()
        now = _utcnow()
        session = PairingSession(
            pairing_id=b64url(secrets.token_bytes(18)),
            secret=secrets.token_bytes(32),
            base_url=base_url.rstrip("/"),
            created_at=now,
            expires_at=now + timedelta(seconds=PAIRING_TTL_SECONDS),
        )
        self._pairings[session.pairing_id] = session
        return session

    def get_pairing(self, pairing_id: str, secret_text: str) -> PairingSession:
        self._cleanup_pairings()
        session = self._pairings.get(pairing_id)
        if session is None:
            raise PairingError("pairing_not_found")
        try:
            supplied = b64url_decode(secret_text)
        except Exception as err:
            raise PairingError("invalid_secret") from err
        if not hmac.compare_digest(session.secret, supplied):
            self._register_failed_attempt(session)
            raise PairingError("invalid_secret")
        return session

    async def claim_pairing(
        self,
        *,
        pairing_id: str,
        device_id: str,
        device_name: str,
        app_version: str,
        client_nonce: str,
        proof: str,
    ) -> dict[str, str]:
        self._cleanup_pairings()
        session = self._pairings.get(pairing_id)
        if session is None:
            raise PairingError("pairing_not_found")

        expected_proof = pairing_proof(
            session.secret,
            pairing_id,
            device_id,
            device_name,
            app_version,
            client_nonce,
        )
        if not hmac.compare_digest(expected_proof, proof):
            self._register_failed_attempt(session)
            raise PairingError("invalid_proof")

        try:
            client_nonce_bytes = b64url_decode(client_nonce)
        except Exception as err:
            raise PairingError("invalid_nonce") from err
        if len(client_nonce_bytes) < 12:
            raise PairingError("invalid_nonce")

        token = secrets.token_bytes(32)
        encrypted_token, tag = encrypt_device_token(
            session.secret,
            token,
            pairing_id,
            device_id,
            client_nonce,
        )
        token_hash = hashlib.sha256(token).hexdigest()
        api_key = derive_api_key(token)

        now = _utcnow().isoformat()
        self._devices[device_id] = {
            "device_id": device_id,
            "device_name": device_name[:80],
            "app_version": app_version[:32],
            "created_at": now,
            "last_seen": now,
            "token_hash": token_hash,
            "api_key": b64url(api_key),
        }
        await self._async_save()
        self._pairings.pop(pairing_id, None)

        return {
            "encrypted_token": encrypted_token,
            "tag": tag,
            "token_format": "castncasa-device-v1",
        }

    def _register_failed_attempt(self, session: PairingSession) -> None:
        session.attempts += 1
        if session.attempts >= PAIRING_MAX_ATTEMPTS:
            self._pairings.pop(session.pairing_id, None)

    async def revoke_device(self, device_id: str) -> bool:
        if self._devices.pop(device_id, None) is None:
            return False
        self._nonces.pop(device_id, None)
        await self._async_save()
        return True

    def list_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "device_id": item.get("device_id", device_id),
                "device_name": item.get("device_name", "CastnCasa"),
                "app_version": item.get("app_version", ""),
                "created_at": item.get("created_at"),
                "last_seen": item.get("last_seen"),
            }
            for device_id, item in sorted(self._devices.items())
        ]

    async def authenticate_api_request(
        self,
        *,
        method: str,
        path: str,
        device_id: str,
        timestamp: str,
        nonce: str,
        signature: str,
        body: bytes,
    ) -> dict[str, Any]:
        record = self._devices.get(device_id)
        if record is None:
            raise DeviceAuthError("unknown_device")

        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError) as err:
            raise DeviceAuthError("invalid_timestamp") from err
        if abs(int(_utcnow().timestamp()) - timestamp_value) > API_CLOCK_SKEW_SECONDS:
            raise DeviceAuthError("timestamp_out_of_range")

        self._cleanup_nonces(device_id)
        nonces = self._nonces.setdefault(device_id, {})
        if nonce in nonces:
            raise DeviceAuthError("replayed_nonce")
        try:
            nonce_bytes = b64url_decode(nonce)
        except Exception as err:
            raise DeviceAuthError("invalid_nonce") from err
        if len(nonce_bytes) < 12:
            raise DeviceAuthError("invalid_nonce")

        try:
            api_key = b64url_decode(str(record["api_key"]))
        except Exception as err:
            raise DeviceAuthError("invalid_device_record") from err
        expected = api_signature(
            api_key,
            method,
            path,
            device_id,
            timestamp,
            nonce,
            body,
        )
        if not hmac.compare_digest(expected, signature):
            raise DeviceAuthError("invalid_signature")

        nonces[nonce] = _utcnow()
        record["last_seen"] = _utcnow().isoformat()
        await self._async_save()
        return record

    def _cleanup_nonces(self, device_id: str) -> None:
        cutoff = _utcnow() - timedelta(seconds=API_NONCE_TTL_SECONDS)
        bucket = self._nonces.get(device_id)
        if not bucket:
            return
        for value in [value for value, seen_at in bucket.items() if seen_at < cutoff]:
            bucket.pop(value, None)
