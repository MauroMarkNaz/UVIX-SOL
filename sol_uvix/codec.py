"""
Core UVIX Protocol Codec (UVIX-RI-1.0)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles serialization, canonical SHA-256 hashing, base64 envelope framing,
and cryptographic integrity validation for cross-platform UVIX slugs.
"""

import base64
import hashlib
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

UVIX_PREFIX = "UVIX::"
UVIX_SUFFIX = "::END"
PROTOCOL_VERSION = "1.0"


class UVIXError(Exception):
    """Base exception for all UVIX protocol errors."""
    pass


class UVIXIntegrityError(UVIXError):
    """Raised when payload_hash does not match the canonical hash of raw_payload."""
    pass


class UVIXFormatError(UVIXError):
    """Raised when envelope framing or JSON structure is invalid."""
    pass


@dataclass
class UVIXSlug:
    protocol_version: str
    source_platform: str
    target_platform: str
    payload_hash: str
    compatibility_layer: str
    raw_payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_envelope(self) -> str:
        return encode_uvix_slug(self)


def compute_canonical_payload_hash(raw_payload: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA-256 hash of raw_payload.
    Ensures keys are lexicographically sorted and formatting is compact.
    """
    canonical_json = json.dumps(raw_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def encode_uvix_slug(slug_or_payload: Any,
                     source_platform: str = "Solana-Stack",
                     target_platform: str = "UVIX-Mesh-MultiAgent",
                     compatibility_layer: str = "solana-uvix-v1") -> str:
    """
    Encodes payload or UVIXSlug instance into canonical UVIX::<base64>::END envelope.
    """
    if isinstance(slug_or_payload, UVIXSlug):
        slug_dict = slug_or_payload.to_dict()
    elif isinstance(slug_or_payload, dict) and "protocol_version" in slug_or_payload and "payload_hash" in slug_or_payload:
        slug_dict = slug_or_payload
    elif isinstance(slug_or_payload, dict):
        payload_hash = compute_canonical_payload_hash(slug_or_payload)
        slug_dict = {
            "protocol_version": PROTOCOL_VERSION,
            "source_platform": source_platform,
            "target_platform": target_platform,
            "payload_hash": payload_hash,
            "compatibility_layer": compatibility_layer,
            "raw_payload": slug_or_payload,
        }
    else:
        raise UVIXFormatError(f"Unsupported payload type for encoding: {type(slug_or_payload)}")

    # Deterministic JSON serialization for the full slug dictionary
    slug_json = json.dumps(slug_dict, sort_keys=True, separators=(",", ":"))
    b64_payload = base64.b64encode(slug_json.encode("utf-8")).decode("utf-8")
    return f"{UVIX_PREFIX}{b64_payload}{UVIX_SUFFIX}"


def decode_uvix_slug(envelope: str, verify_integrity: bool = True) -> UVIXSlug:
    """
    Decodes a UVIX::<base64>::END envelope and validates its structural and cryptographic integrity.
    """
    if not isinstance(envelope, str):
        raise UVIXFormatError(f"Envelope must be a string, received {type(envelope)}")

    trimmed = envelope.strip()
    if not (trimmed.startswith(UVIX_PREFIX) and trimmed.endswith(UVIX_SUFFIX)):
        raise UVIXFormatError(f"Envelope does not match UVIX framing '{UVIX_PREFIX}...{UVIX_SUFFIX}'")

    b64_data = trimmed[len(UVIX_PREFIX) : -len(UVIX_SUFFIX)]
    try:
        raw_json_str = base64.b64decode(b64_data.encode("utf-8")).decode("utf-8")
        slug_dict = json.loads(raw_json_str)
    except Exception as e:
        raise UVIXFormatError(f"Failed to decode base64 or parse JSON in UVIX envelope: {str(e)}") from e

    required_keys = {"protocol_version", "source_platform", "target_platform", "payload_hash", "compatibility_layer", "raw_payload"}
    missing = required_keys - set(slug_dict.keys())
    if missing:
        raise UVIXFormatError(f"UVIX slug is missing required fields: {missing}")

    if verify_integrity:
        expected_hash = compute_canonical_payload_hash(slug_dict["raw_payload"])
        actual_hash = slug_dict["payload_hash"]
        if actual_hash != expected_hash:
            raise UVIXIntegrityError(
                f"Payload integrity hash mismatch! Expected {expected_hash}, got {actual_hash}"
            )

    return UVIXSlug(
        protocol_version=slug_dict["protocol_version"],
        source_platform=slug_dict["source_platform"],
        target_platform=slug_dict["target_platform"],
        payload_hash=slug_dict["payload_hash"],
        compatibility_layer=slug_dict["compatibility_layer"],
        raw_payload=slug_dict["raw_payload"],
    )
