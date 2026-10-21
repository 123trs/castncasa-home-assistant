"""HTTP endpoints for CastnCasa."""

from __future__ import annotations

from html import escape
from io import BytesIO
import json
from typing import Any

from aiohttp import web
import segno

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import network

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    PAIR_CLAIM_PATH,
    PAIRING_PATH,
    PAIRING_QR_PATH,
    PRESENCE_PATH,
    SCHEDULE_PATH,
    STATE_PATH,
    STATUS_PATH,
)
from .pairing import CastnCasaPairingManager, DeviceAuthError, PairingError
from .protocol import b64url_decode, decrypt_api_body, encrypt_api_body
from .schedule import CastnCasaScheduleStore, ScheduleConflictError, ScheduleValidationError

MAX_SCHEDULE_BODY = 384 * 1024
MAX_PRESENCE_BODY = 16 * 1024


def _sync_urls(hass: HomeAssistant) -> tuple[str | None, str | None]:
    local_url: str | None = None
    remote_url: str | None = None
    try:
        local_url = network.get_url(
            hass,
            allow_internal=True,
            allow_external=False,
            allow_cloud=False,
        ).rstrip("/")
    except Exception:
        pass
    try:
        remote_url = network.get_url(
            hass,
            allow_internal=False,
            allow_external=True,
            allow_cloud=True,
            prefer_external=True,
        ).rstrip("/")
    except Exception:
        pass
    return local_url, remote_url


def _device_auth_headers(request: web.Request) -> tuple[str, str, str, str]:
    return (
        request.headers.get("X-CastnCasa-Device-ID", ""),
        request.headers.get("X-CastnCasa-Timestamp", ""),
        request.headers.get("X-CastnCasa-Nonce", ""),
        request.headers.get("X-CastnCasa-Signature", ""),
    )


async def _authenticate(
    manager: CastnCasaPairingManager,
    request: web.Request,
    path: str,
    body: bytes = b"",
) -> tuple[str, dict[str, Any]]:
    device_id, timestamp, nonce, signature = _device_auth_headers(request)
    if not all((device_id, timestamp, nonce, signature)):
        raise DeviceAuthError("missing_auth")
    record = await manager.authenticate_api_request(
        method=request.method,
        path=path,
        device_id=device_id,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        body=body,
    )
    return device_id, record


def _api_key(record: dict[str, Any]) -> bytes:
    return b64url_decode(str(record["api_key"]))


def _decrypt_request_body(
    record: dict[str, Any],
    request: web.Request,
    path: str,
    envelope: bytes,
) -> bytes:
    device_id, timestamp, nonce, _ = _device_auth_headers(request)
    return decrypt_api_body(
        _api_key(record),
        envelope,
        direction="request",
        method=request.method,
        path=path,
        device_id=device_id,
        timestamp=timestamp,
        request_nonce=nonce,
    )


def _encrypted_json_response(
    record: dict[str, Any],
    request: web.Request,
    path: str,
    payload: dict[str, Any],
    *,
    status: int = 200,
) -> web.Response:
    device_id, timestamp, nonce, _ = _device_auth_headers(request)
    plaintext = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    encrypted = encrypt_api_body(
        _api_key(record),
        plaintext,
        direction="response",
        method=request.method,
        path=path,
        device_id=device_id,
        timestamp=timestamp,
        request_nonce=nonce,
    )
    return web.Response(
        body=encrypted,
        status=status,
        content_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


class CastnCasaPairingPageView(HomeAssistantView):
    """Short-lived page showing the CastnCasa pairing QR code."""

    url = PAIRING_PATH
    name = "api:castncasa:pairing_page"
    requires_auth = False

    def __init__(self, manager: CastnCasaPairingManager) -> None:
        self.manager = manager

    async def get(self, request: web.Request, pairing_id: str) -> web.Response:
        secret = request.query.get("secret", "")
        try:
            session = self.manager.get_pairing(pairing_id, secret)
        except PairingError:
            return web.Response(
                status=410,
                text="CastnCasa-Pairing ist ungültig oder abgelaufen.",
                content_type="text/plain",
                headers={"Cache-Control": "no-store"},
            )

        qr = segno.make(session.pair_uri, error="m")
        output = BytesIO()
        qr.save(output, kind="svg", scale=7, border=2, xmldecl=False)
        svg = output.getvalue().decode("utf-8")
        pair_uri = escape(session.pair_uri, quote=True)
        expires = escape(session.expires_at.isoformat())

        html = f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>CastnCasa koppeln</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#f5f7fb;color:#172033;margin:0;padding:24px}}
main{{max-width:520px;margin:0 auto;background:white;border-radius:22px;padding:24px;box-shadow:0 10px 35px #0001}}
h1{{margin-top:0}} .qr{{display:flex;justify-content:center;margin:24px 0}} .qr svg{{max-width:100%;height:auto}}
a.button{{display:block;text-align:center;padding:14px 16px;border-radius:12px;background:#1769e0;color:white;text-decoration:none;font-weight:700}}
small{{color:#657087}}
</style>
</head>
<body><main>
<h1>CastnCasa koppeln</h1>
<p>Öffne CastnCasa und scanne diesen QR-Code. Der Code ist einmalig und nur fünf Minuten gültig.</p>
<div class="qr">{svg}</div>
<a class="button" href="{pair_uri}">CastnCasa auf diesem Gerät öffnen</a>
<p><small>Gültig bis: {expires}</small></p>
</main></body></html>"""
        return web.Response(
            text=html,
            content_type="text/html",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
            },
        )


class CastnCasaPairingQrView(HomeAssistantView):
    """Short-lived SVG QR code for the CastnCasa options flow."""

    url = PAIRING_QR_PATH
    name = "api:castncasa:pairing_qr"
    requires_auth = False

    def __init__(self, manager: CastnCasaPairingManager) -> None:
        self.manager = manager

    async def get(self, request: web.Request, pairing_id: str) -> web.Response:
        secret = request.query.get("secret", "")
        try:
            session = self.manager.get_pairing(pairing_id, secret)
        except PairingError:
            return web.Response(
                status=410,
                text="CastnCasa-Pairing ist ungültig oder abgelaufen.",
                content_type="text/plain",
                headers={"Cache-Control": "no-store"},
            )

        qr = segno.make(session.pair_uri, error="m")
        output = BytesIO()
        qr.save(output, kind="svg", scale=7, border=2, xmldecl=False)
        return web.Response(
            body=output.getvalue(),
            content_type="image/svg+xml",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )


class CastnCasaPairClaimView(HomeAssistantView):
    """Exchange a one-time pairing proof for an encrypted device token."""

    url = PAIR_CLAIM_PATH
    name = "api:castncasa:pair_claim"
    requires_auth = False

    def __init__(self, manager: CastnCasaPairingManager) -> None:
        self.manager = manager

    async def post(self, request: web.Request) -> web.Response:
        try:
            data: dict[str, Any] = await request.json()
        except (json.JSONDecodeError, ValueError):
            return web.json_response({"error": "invalid_json"}, status=400)

        required = (
            "pairing_id",
            "device_id",
            "device_name",
            "app_version",
            "client_nonce",
            "proof",
        )
        if any(not isinstance(data.get(field), str) or not data[field] for field in required):
            return web.json_response({"error": "invalid_request"}, status=400)
        if any("\n" in data[field] or "\r" in data[field] for field in required):
            return web.json_response({"error": "invalid_request"}, status=400)
        if (
            len(data["pairing_id"]) > 96
            or len(data["device_id"]) > 80
            or len(data["device_name"]) > 80
            or len(data["app_version"]) > 32
            or len(data["client_nonce"]) > 128
            or len(data["proof"]) > 128
        ):
            return web.json_response({"error": "invalid_request"}, status=400)

        try:
            result = await self.manager.claim_pairing(
                pairing_id=data["pairing_id"],
                device_id=data["device_id"],
                device_name=data["device_name"],
                app_version=data["app_version"],
                client_nonce=data["client_nonce"],
                proof=data["proof"],
            )
        except PairingError:
            return web.json_response({"error": "pairing_failed"}, status=401)

        resident_id = str(result.get("resident_id") or data["device_id"])
        return web.json_response(
            {
                "ok": True,
                "device_id": data["device_id"],
                "resident_id": resident_id,
                "resident_relinked": resident_id != data["device_id"],
                **result,
            },
            headers={"Cache-Control": "no-store"},
        )


class CastnCasaStatusView(HomeAssistantView):
    """Validate the signed CastnCasa device API transport."""

    url = STATUS_PATH
    name = "api:castncasa:status"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, manager: CastnCasaPairingManager) -> None:
        self.hass = hass
        self.manager = manager

    async def get(self, request: web.Request) -> web.Response:
        try:
            device_id, record = await _authenticate(self.manager, request, STATUS_PATH)
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)
        local_url, remote_url = _sync_urls(self.hass)
        return web.json_response(
            {
                "ok": True,
                "service": "CastnCasa Home Assistant",
                "api": 1,
                "encrypted_schedule": True,
                "device_id": device_id,
                "device_name": record.get("device_name", "CastnCasa"),
                "sync": {
                    "mode": "dual",
                    "remote_url": remote_url,
                    "local_url": local_url,
                    "remote_configured": remote_url is not None,
                    "offline_queue_supported": True,
                    "schedule_revisioning": True,
                },
                "presence": {
                    "endpoint": PRESENCE_PATH,
                    "calendar_independent": True,
                    "priority": "actual_presence_first",
                },
            },
            headers={"Cache-Control": "no-store"},
        )


class CastnCasaScheduleView(HomeAssistantView):
    """Read or replace the authenticated device's encrypted resident schedule."""

    url = SCHEDULE_PATH
    name = "api:castncasa:schedule"
    requires_auth = False

    def __init__(self, manager: CastnCasaPairingManager, schedule: CastnCasaScheduleStore) -> None:
        self.manager = manager
        self.schedule = schedule

    async def get(self, request: web.Request) -> web.Response:
        try:
            device_id, record = await _authenticate(self.manager, request, SCHEDULE_PATH)
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)
        resident_id = str(record.get("resident_id") or device_id)
        return _encrypted_json_response(
            record,
            request,
            SCHEDULE_PATH,
            {"ok": True, "api_version": 1, **self.schedule.resident_payload(resident_id)},
        )

    async def put(self, request: web.Request) -> web.Response:
        envelope = await request.read()
        if len(envelope) > MAX_SCHEDULE_BODY:
            return web.json_response({"error": "request_too_large"}, status=413)
        try:
            device_id, record = await _authenticate(
                self.manager, request, SCHEDULE_PATH, envelope
            )
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)

        try:
            plaintext = _decrypt_request_body(record, request, SCHEDULE_PATH, envelope)
            data = json.loads(plaintext)
        except Exception:
            return _encrypted_json_response(
                record,
                request,
                SCHEDULE_PATH,
                {"error": "invalid_encrypted_body"},
                status=400,
            )
        if not isinstance(data, dict):
            return _encrypted_json_response(
                record,
                request,
                SCHEDULE_PATH,
                {"error": "invalid_request"},
                status=400,
            )
        resident_id = str(record.get("resident_id") or device_id)
        try:
            result = await self.schedule.async_replace_resident(resident_id, data)
        except ScheduleConflictError:
            return _encrypted_json_response(
                record,
                request,
                SCHEDULE_PATH,
                {"error": "revision_conflict", **self.schedule.resident_payload(resident_id)},
                status=409,
            )
        except ScheduleValidationError as err:
            return _encrypted_json_response(
                record,
                request,
                SCHEDULE_PATH,
                {"error": str(err)},
                status=400,
            )
        return _encrypted_json_response(
            record,
            request,
            SCHEDULE_PATH,
            {"ok": True, "api_version": 1, **result},
        )

    async def delete(self, request: web.Request) -> web.Response:
        """Unpair this device and remove its resident schedule."""
        try:
            device_id, record = await _authenticate(self.manager, request, SCHEDULE_PATH)
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)

        resident_id = str(record.get("resident_id") or device_id)
        resident_removed = await self.schedule.async_remove_resident(resident_id)
        device_revoked = await self.manager.revoke_device(device_id)
        return _encrypted_json_response(
            record,
            request,
            SCHEDULE_PATH,
            {
                "ok": True,
                "api_version": 1,
                "resident_removed": resident_removed,
                "device_revoked": device_revoked,
            },
        )


class CastnCasaPresenceView(HomeAssistantView):
    """Read/update resident presence independently from calendar sync."""

    url = PRESENCE_PATH
    name = "api:castncasa:presence"
    requires_auth = False

    def __init__(self, manager: CastnCasaPairingManager) -> None:
        self.manager = manager

    async def get(self, request: web.Request) -> web.Response:
        try:
            device_id, record = await _authenticate(self.manager, request, PRESENCE_PATH)
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)
        return _encrypted_json_response(
            record,
            request,
            PRESENCE_PATH,
            {"ok": True, "api_version": 1, **self.manager.device_metadata(device_id)},
        )

    async def put(self, request: web.Request) -> web.Response:
        envelope = await request.read()
        if len(envelope) > MAX_PRESENCE_BODY:
            return web.json_response({"error": "request_too_large"}, status=413)
        try:
            device_id, record = await _authenticate(
                self.manager, request, PRESENCE_PATH, envelope
            )
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)

        try:
            plaintext = _decrypt_request_body(record, request, PRESENCE_PATH, envelope)
            data = json.loads(plaintext)
        except Exception:
            return _encrypted_json_response(
                record,
                request,
                PRESENCE_PATH,
                {"error": "invalid_encrypted_body"},
                status=400,
            )
        if not isinstance(data, dict):
            return _encrypted_json_response(
                record, request, PRESENCE_PATH, {"error": "invalid_request"}, status=400
            )
        state = str(data.get("state", "")).strip().lower()
        source = str(data.get("source", "app")).strip()[:32] or "app"
        try:
            metadata = await self.manager.async_update_presence(device_id, state, source)
        except (DeviceAuthError, ValueError) as err:
            return _encrypted_json_response(
                record, request, PRESENCE_PATH, {"error": str(err)}, status=400
            )
        return _encrypted_json_response(
            record,
            request,
            PRESENCE_PATH,
            {"ok": True, "api_version": 1, **metadata},
        )


class CastnCasaStateView(HomeAssistantView):
    """Return encrypted household forecast state to an authenticated device."""

    url = STATE_PATH
    name = "api:castncasa:state"
    requires_auth = False

    def __init__(
        self, hass: HomeAssistant, manager: CastnCasaPairingManager, schedule: CastnCasaScheduleStore
    ) -> None:
        self.hass = hass
        self.manager = manager
        self.schedule = schedule

    async def get(self, request: web.Request) -> web.Response:
        try:
            _device_id, record = await _authenticate(self.manager, request, STATE_PATH)
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)
        coordinator = self.hass.data.get(DOMAIN, {}).get(DATA_COORDINATOR)
        payload = coordinator.data if coordinator is not None else self.schedule.state_snapshot()
        return _encrypted_json_response(
            record,
            request,
            STATE_PATH,
            payload,
        )
