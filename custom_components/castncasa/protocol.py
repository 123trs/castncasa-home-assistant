"""Pure cryptographic protocol helpers for CastnCasa pairing/API v1."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def pairing_proof_payload(
    pairing_id: str,
    device_id: str,
    device_name: str,
    app_version: str,
    client_nonce: str,
) -> bytes:
    return (
        "castncasa-pair-v1\n"
        f"{pairing_id}\n{device_id}\n{device_name}\n{app_version}\n{client_nonce}"
    ).encode()


def pairing_proof(
    secret: bytes,
    pairing_id: str,
    device_id: str,
    device_name: str,
    app_version: str,
    client_nonce: str,
) -> str:
    payload = pairing_proof_payload(
        pairing_id, device_id, device_name, app_version, client_nonce
    )
    return b64url(hmac.new(secret, payload, hashlib.sha256).digest())


def encrypt_device_token(
    secret: bytes,
    token: bytes,
    pairing_id: str,
    device_id: str,
    client_nonce: str,
) -> tuple[str, str]:
    if len(token) != 32:
        raise ValueError("device token must be 32 bytes")
    mask = hmac.new(
        secret,
        b"castncasa-token-mask-v1\n" + client_nonce.encode(),
        hashlib.sha256,
    ).digest()
    encrypted = bytes(left ^ right for left, right in zip(token, mask, strict=True))
    tag_payload = (
        b"castncasa-token-tag-v1\n"
        + pairing_id.encode()
        + b"\n"
        + device_id.encode()
        + b"\n"
        + client_nonce.encode()
        + b"\n"
        + encrypted
    )
    tag = hmac.new(secret, tag_payload, hashlib.sha256).digest()
    return b64url(encrypted), b64url(tag)


def derive_api_key(token: bytes) -> bytes:
    return hmac.new(token, b"castncasa-api-key-v1", hashlib.sha256).digest()


def derive_encryption_key(api_key: bytes) -> bytes:
    """Derive an independent AES-256 key from the stored API key."""
    return hmac.new(api_key, b"castncasa-encryption-key-v1", hashlib.sha256).digest()


def api_signature_payload(
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    body_sha256 = hashlib.sha256(body).hexdigest()
    return (
        "castncasa-api-v1\n"
        f"{method.upper()}\n{path}\n{device_id}\n{timestamp}\n{nonce}\n{body_sha256}"
    ).encode()


def api_signature(
    api_key: bytes,
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    payload = api_signature_payload(method, path, device_id, timestamp, nonce, body)
    return b64url(hmac.new(api_key, payload, hashlib.sha256).digest())


def body_aad(
    direction: str,
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    request_nonce: str,
) -> bytes:
    if direction not in {"request", "response"}:
        raise ValueError("invalid direction")
    return (
        "castncasa-body-v1\n"
        f"{direction}\n{method.upper()}\n{path}\n{device_id}\n{timestamp}\n{request_nonce}"
    ).encode()


def encrypt_api_body(
    api_key: bytes,
    plaintext: bytes,
    *,
    direction: str,
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    request_nonce: str,
    body_nonce: bytes | None = None,
) -> bytes:
    """Encrypt one request or response body into a compact JSON envelope."""
    nonce = body_nonce or os.urandom(12)
    if len(nonce) != 12:
        raise ValueError("body nonce must be 12 bytes")
    ciphertext = AESGCM(derive_encryption_key(api_key)).encrypt(
        nonce,
        plaintext,
        body_aad(direction, method, path, device_id, timestamp, request_nonce),
    )
    return json.dumps(
        {"v": 1, "nonce": b64url(nonce), "ciphertext": b64url(ciphertext)},
        separators=(",", ":"),
    ).encode()


def decrypt_api_body(
    api_key: bytes,
    envelope: bytes,
    *,
    direction: str,
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    request_nonce: str,
) -> bytes:
    """Decrypt and authenticate one CastnCasa API body envelope."""
    try:
        payload = json.loads(envelope)
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise ValueError("invalid envelope")
        nonce = b64url_decode(str(payload["nonce"]))
        ciphertext = b64url_decode(str(payload["ciphertext"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as err:
        raise ValueError("invalid encrypted body") from err
    if len(nonce) != 12:
        raise ValueError("invalid body nonce")
    return AESGCM(derive_encryption_key(api_key)).decrypt(
        nonce,
        ciphertext,
        body_aad(direction, method, path, device_id, timestamp, request_nonce),
    )
