"""Signed, versioned publication format for a validated registry authority.

Development signs canonical JSON with a publisher-held Ed25519 private key.
Runtime verifies it with a trusted public key supplied by its release boundary,
then reconstructs fresh typed models. This module neither knows a registry root
nor compiles, repairs, or validates authoring inputs on a failed read.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePath
from typing import Final, cast

from pydantic import BaseModel, ValidationError

from ....core.atomic_write import atomic_write_bytes
from ....core.ed25519_signing import digest_signature_is_valid, sign_digest_hex
from ....core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from .schema import ModeloDefinition, RegistryCatalogues

__all__ = [
    "AUTHORITY_ARTIFACT_SCHEMA_VERSION",
    "AuthorityArtifact",
    "AuthorityArtifactError",
    "AuthorityArtifactFormatError",
    "AuthorityArtifactIntegrityError",
    "AuthorityArtifactUnavailableError",
    "read_authority_artifact",
    "write_authority_artifact",
]

AUTHORITY_ARTIFACT_SCHEMA_VERSION: Final[str] = "cadrumo-authority-artifact-v1"
_IDENTITY_DIGEST = re.compile(r"[0-9a-f]{64}")


class AuthorityArtifactError(RuntimeError):
    """Base refusal raised when a published authority cannot be consumed."""


class AuthorityArtifactUnavailableError(AuthorityArtifactError):
    """The required published authority file could not be opened."""


class AuthorityArtifactIntegrityError(AuthorityArtifactError):
    """The artifact has an invalid content digest or publisher signature."""


class AuthorityArtifactFormatError(AuthorityArtifactError):
    """The artifact frame or typed authority payload has an unsupported shape."""


@dataclass(frozen=True, slots=True)
class AuthorityArtifact:
    """Complete typed authority payload emitted only after registry validation.

    ``identity_digest`` identifies the source generation development validated.
    Each read rebuilds this graph from signed JSON, isolating later reads from a
    consumer's mutation of a prior result.
    """

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    identity_digest: str

    def __post_init__(self) -> None:
        """Reject partial or untyped content before publication."""
        if not isinstance(self.modelos, tuple) or not all(
            isinstance(modelo, ModeloDefinition) for modelo in self.modelos
        ):
            raise TypeError("authority artifact modelos must be a tuple of ModeloDefinition instances")
        if not isinstance(self.catalogues, RegistryCatalogues):
            raise TypeError("authority artifact catalogues must be a RegistryCatalogues instance")
        if _IDENTITY_DIGEST.fullmatch(self.identity_digest) is None:
            raise ValueError("authority artifact identity_digest must be a lowercase SHA-256 hexadecimal digest")


def write_authority_artifact(path: Path, artifact: AuthorityArtifact, *, signing_private_key_hex: str) -> None:
    """Atomically publish an authority signed by the development publisher."""
    if not isinstance(artifact, AuthorityArtifact):
        raise TypeError("authority artifact writer requires an AuthorityArtifact")
    atomic_write_bytes(path, _encode_artifact(artifact, signing_private_key_hex=signing_private_key_hex))


def read_authority_artifact(path: Path, *, verification_public_key_hex: str) -> AuthorityArtifact:
    """Read a publisher-authenticated authority or fail closed without fallback."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuthorityArtifactUnavailableError(f"published authority artifact is unavailable at {path}") from exc
    return _decode_artifact(raw, verification_public_key_hex=verification_public_key_hex)


def _encode_artifact(artifact: AuthorityArtifact, *, signing_private_key_hex: str) -> bytes:
    """Return the canonical signed JSON frame for ``artifact``."""
    signed_document = {
        "schema_version": AUTHORITY_ARTIFACT_SCHEMA_VERSION,
        "payload": _artifact_document(artifact),
    }
    digest = sha256_hex(canonical_json_bytes(signed_document))
    return canonical_json_bytes(
        {
            **signed_document,
            "payload_sha256": digest,
            "signature": sign_digest_hex(private_key_hex=signing_private_key_hex, digest_hex=digest),
        }
    )


def _decode_artifact(raw: bytes, *, verification_public_key_hex: str) -> AuthorityArtifact:
    """Verify one frame before reconstructing a fresh typed authority graph."""
    frame = _decode_json_object(raw, subject="published authority artifact")
    version = _required_string(frame, "schema_version")
    payload = _required_mapping(frame, "payload")
    recorded_digest = _required_string(frame, "payload_sha256")
    signature = _required_string(frame, "signature")
    if version != AUTHORITY_ARTIFACT_SCHEMA_VERSION:
        raise AuthorityArtifactFormatError("published authority artifact has an unsupported schema version")
    signed_document = {"schema_version": version, "payload": payload}
    expected_digest = sha256_hex(canonical_json_bytes(signed_document))
    if recorded_digest != expected_digest:
        raise AuthorityArtifactIntegrityError("published authority artifact failed its content digest check")
    try:
        signature_valid = digest_signature_is_valid(
            public_key_hex=verification_public_key_hex,
            digest_hex=expected_digest,
            signature_hex=signature,
        )
    except ValueError as exc:
        raise AuthorityArtifactFormatError("published authority artifact has an invalid signature encoding") from exc
    if not signature_valid:
        raise AuthorityArtifactIntegrityError("published authority artifact was not signed by the trusted publisher")
    return _artifact_from_document(payload)


def _artifact_document(artifact: AuthorityArtifact) -> dict[str, object]:
    """Project all schema fields, including non-rendered identities, into JSON."""
    return {
        "modelos": [_json_value(modelo) for modelo in artifact.modelos],
        "catalogues": _json_value(artifact.catalogues),
        "identity_digest": artifact.identity_digest,
    }


def _artifact_from_document(payload: Mapping[str, object]) -> AuthorityArtifact:
    """Rebuild a fresh strict authority graph from authenticated JSON data."""
    try:
        modelos_document = _required_sequence(payload, "modelos")
        catalogues_document = _required_mapping(payload, "catalogues")
        identity_digest = _required_string(payload, "identity_digest")
        modelos = tuple(
            ModeloDefinition.model_validate_json(canonical_json_bytes(_mapping_item(item, "modelos")))
            for item in modelos_document
        )
        catalogues = RegistryCatalogues.model_validate_json(canonical_json_bytes(catalogues_document))
        return AuthorityArtifact(modelos=modelos, catalogues=catalogues, identity_digest=identity_digest)
    except (ValidationError, TypeError, ValueError) as exc:
        raise AuthorityArtifactFormatError("published authority artifact has an invalid authority payload") from exc


def _json_value(value: object) -> object:
    """Project registry values to JSON without omitting excluded model fields."""
    if isinstance(value, BaseModel):
        return {field_name: _json_value(getattr(value, field_name)) for field_name in type(value).model_fields}
    if isinstance(value, Mapping):
        return {_json_key(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, PurePath):
        return value.as_posix()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"authority artifact cannot serialize {type(value).__name__}")


def _json_key(key: object) -> str:
    """Project a mapping key through the JSON-safe value vocabulary."""
    value = _json_value(key)
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError("authority artifact mapping keys must be JSON scalar values")
    return str(value)


def _decode_json_object(raw: bytes, *, subject: str) -> dict[str, object]:
    """Decode JSON while refusing duplicate names and non-finite values."""
    try:
        decoded = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
    except (TypeError, UnicodeDecodeError, ValueError) as exc:
        raise AuthorityArtifactFormatError(f"{subject} is not valid canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise AuthorityArtifactFormatError(f"{subject} must be a JSON object")
    return cast(dict[str, object], decoded)


def _required_string(document: Mapping[str, object], field_name: str) -> str:
    """Return one non-empty string field or raise a format refusal."""
    value = document.get(field_name)
    if not isinstance(value, str) or not value:
        raise AuthorityArtifactFormatError(
            f"published authority artifact field {field_name!r} must be a non-empty string"
        )
    return value


def _required_mapping(document: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    """Return one object field or raise a format refusal."""
    return _mapping_item(document.get(field_name), field_name)


def _mapping_item(value: object, field_name: str) -> Mapping[str, object]:
    """Require one decoded JSON object."""
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise AuthorityArtifactFormatError(f"published authority artifact field {field_name!r} must be an object")
    return cast(Mapping[str, object], value)


def _required_sequence(document: Mapping[str, object], field_name: str) -> Sequence[object]:
    """Return one JSON array field or raise a format refusal."""
    value = document.get(field_name)
    if not isinstance(value, list):
        raise AuthorityArtifactFormatError(f"published authority artifact field {field_name!r} must be an array")
    return value
