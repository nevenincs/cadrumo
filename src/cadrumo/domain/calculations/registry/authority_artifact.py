"""Signed, versioned publication format for a validated registry authority.

Development signs canonical JSON with a publisher-held Ed25519 private key.
Runtime verifies it with a trusted public key supplied by its release boundary,
then reconstructs fresh typed models. This module neither knows a registry root
nor compiles, repairs, or validates authoring inputs on a failed read.
"""

from __future__ import annotations

import json
import re
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
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
from .corpus_provenance import NormativeCorpusProvenance
from .schema import DeclaredPredecessor, ModeloDefinition, NoPredecessor, RegistryCatalogues

__all__ = [
    "AUTHORITY_ARTIFACT_SCHEMA_VERSION",
    "AuthorityArtifact",
    "AuthorityArtifactError",
    "AuthorityArtifactFormatError",
    "AuthorityArtifactIntegrityError",
    "AuthorityArtifactUnavailableError",
    "AuthorityEvidenceProjection",
    "PublishedLegalEvidence",
    "PublishedSourceEvidence",
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
class PublishedLegalEvidence:
    """One publisher-validated, anchor-scoped legal text projection.

    This is deliberately text and identity, rather than a corpus filename or
    source root.  The release artifact is the runtime evidence boundary.
    """

    legal_reference_id: str
    anchored_text: str
    text_sha256: str
    provenance: NormativeCorpusProvenance = NormativeCorpusProvenance.OUT_OF_SCOPE

    def __post_init__(self) -> None:
        """Reject incomplete or altered publisher-projected text."""
        if not self.legal_reference_id:
            raise ValueError("published legal evidence requires a legal reference id")
        if not self.anchored_text:
            raise ValueError("published legal evidence requires anchored text")
        if _IDENTITY_DIGEST.fullmatch(self.text_sha256) is None:
            raise ValueError("published legal evidence requires a lowercase SHA-256 text digest")
        if sha256_hex(self.anchored_text.encode("utf-8")) != self.text_sha256:
            raise ValueError("published legal evidence text digest does not match its anchored text")


@dataclass(frozen=True, slots=True)
class PublishedSourceEvidence:
    """Publisher-validated source bytes required by a shipped workflow.

    Corpus paths remain descriptive catalogue metadata.  A runtime reader gets
    bytes only through this signed projection, never by joining that path to a
    package or checkout root.
    """

    source_reference_id: str
    payload: bytes
    payload_sha256: str

    def __post_init__(self) -> None:
        """Reject incomplete or altered publisher-projected source bytes."""
        if not self.source_reference_id:
            raise ValueError("published source evidence requires a source reference id")
        if not self.payload:
            raise ValueError("published source evidence requires payload bytes")
        if _IDENTITY_DIGEST.fullmatch(self.payload_sha256) is None:
            raise ValueError("published source evidence requires a lowercase SHA-256 payload digest")
        if sha256_hex(self.payload) != self.payload_sha256:
            raise ValueError("published source evidence payload digest does not match its bytes")


@dataclass(frozen=True, slots=True)
class AuthorityEvidenceProjection:
    """Immutable evidence needed by citation consumers after publication."""

    legal: tuple[PublishedLegalEvidence, ...] = ()
    sources: tuple[PublishedSourceEvidence, ...] = ()

    def __post_init__(self) -> None:
        """Reject non-deterministic or ambiguous evidence collections."""
        if not isinstance(self.legal, tuple) or not all(
            isinstance(item, PublishedLegalEvidence) for item in self.legal
        ):
            raise TypeError("authority evidence projection legal entries must be PublishedLegalEvidence tuples")
        ids = tuple(item.legal_reference_id for item in self.legal)
        if len(ids) != len(set(ids)):
            raise ValueError("authority evidence projection legal reference ids must be unique")
        if not isinstance(self.sources, tuple) or not all(
            isinstance(item, PublishedSourceEvidence) for item in self.sources
        ):
            raise TypeError("authority evidence projection source entries must be PublishedSourceEvidence tuples")
        source_ids = tuple(item.source_reference_id for item in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("authority evidence projection source reference ids must be unique")

    def legal_text(self, legal_reference_id: str) -> str:
        """Return publisher-validated text for one legal citation or refuse."""
        for item in self.legal:
            if item.legal_reference_id == legal_reference_id:
                return item.anchored_text
        raise AuthorityArtifactFormatError(
            f"published authority artifact has no evidence projection for legal reference {legal_reference_id!r}"
        )

    def quotation_is_grounded(self, legal_reference_id: str, quotation: str) -> bool:
        """Answer a citation query without opening any authoring corpus path."""
        from ....core.corpus_text import normalise_corpus_text

        return bool(quotation.strip()) and normalise_corpus_text(quotation) in self.legal_text(legal_reference_id)

    def legal_provenance(self, legal_reference_id: str) -> NormativeCorpusProvenance:
        """Return the publisher-derived provenance for one legal reference."""
        for item in self.legal:
            if item.legal_reference_id == legal_reference_id:
                return item.provenance
        raise AuthorityArtifactFormatError(
            f"published authority artifact has no evidence projection for legal reference {legal_reference_id!r}"
        )

    def source_bytes(self, source_reference_id: str) -> bytes:
        """Return signed runtime source bytes for one source reference."""
        for item in self.sources:
            if item.source_reference_id == source_reference_id:
                return item.payload
        raise AuthorityArtifactFormatError(
            f"published authority artifact has no evidence projection for source reference {source_reference_id!r}"
        )


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
    evidence: AuthorityEvidenceProjection = AuthorityEvidenceProjection()

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
        if not isinstance(self.evidence, AuthorityEvidenceProjection):
            raise TypeError("authority artifact evidence must be an AuthorityEvidenceProjection")


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
    except (Base64Error, ValueError) as exc:
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
        "evidence": {
            "legal": [
                {
                    "legal_reference_id": item.legal_reference_id,
                    "anchored_text": item.anchored_text,
                    "text_sha256": item.text_sha256,
                    "provenance": item.provenance.value,
                }
                for item in artifact.evidence.legal
            ],
            "sources": [
                {
                    "source_reference_id": item.source_reference_id,
                    "payload_base64": b64encode(item.payload).decode("ascii"),
                    "payload_sha256": item.payload_sha256,
                }
                for item in artifact.evidence.sources
            ],
        },
    }


def _artifact_from_document(payload: Mapping[str, object]) -> AuthorityArtifact:
    """Rebuild a fresh strict authority graph from authenticated JSON data."""
    try:
        modelos_document = _required_sequence(payload, "modelos")
        catalogues_document = _required_mapping(payload, "catalogues")
        identity_digest = _required_string(payload, "identity_digest")
        evidence_document = _required_mapping(payload, "evidence")
        modelos = tuple(
            ModeloDefinition.model_validate(_immutable_json_value(_mapping_item(item, "modelos")), strict=False)
            for item in modelos_document
        )
        catalogues = RegistryCatalogues.model_validate(_immutable_json_value(catalogues_document), strict=False)
        legal_evidence = tuple(
            PublishedLegalEvidence(
                legal_reference_id=_required_string(_mapping_item(item, "evidence.legal"), "legal_reference_id"),
                anchored_text=_required_string(_mapping_item(item, "evidence.legal"), "anchored_text"),
                text_sha256=_required_string(_mapping_item(item, "evidence.legal"), "text_sha256"),
                provenance=NormativeCorpusProvenance(
                    _required_string(_mapping_item(item, "evidence.legal"), "provenance")
                ),
            )
            for item in _required_sequence(evidence_document, "legal")
        )
        source_evidence = tuple(
            PublishedSourceEvidence(
                source_reference_id=_required_string(_mapping_item(item, "evidence.sources"), "source_reference_id"),
                payload=_decode_base64(_required_string(_mapping_item(item, "evidence.sources"), "payload_base64")),
                payload_sha256=_required_string(_mapping_item(item, "evidence.sources"), "payload_sha256"),
            )
            for item in _required_sequence(evidence_document, "sources")
        )
        return AuthorityArtifact(
            modelos=modelos,
            catalogues=catalogues,
            identity_digest=identity_digest,
            evidence=AuthorityEvidenceProjection(legal=legal_evidence, sources=source_evidence),
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise AuthorityArtifactFormatError("published authority artifact has an invalid authority payload") from exc


def _json_value(value: object) -> object:
    """Project registry values to JSON without omitting excluded model fields."""
    if isinstance(value, DeclaredPredecessor | NoPredecessor):
        # The predecessor union intentionally owns a compact authored wire
        # dialect. Its serializer is a semantic projection, unlike ordinary
        # presentation serializers that may hide fields needed for authority
        # reconstruction.
        return _json_value(value.model_dump(mode="json"))
    if isinstance(value, BaseModel):
        decorators = type(value).__pydantic_decorators__
        # A model serializer owns the complete wire spelling.  In particular,
        # predecessor declarations must retain their authored string/table
        # form rather than their internal wrapper fields.
        if decorators.model_serializers:
            return _json_value(value.model_dump(mode="json", round_trip=True))
        serializer_fields = {
            field_name
            for decorator in decorators.field_serializers.values()
            for field_name in decorator.info.fields
        }
        return {
            field_name: _json_value(
                value.model_dump(mode="json", include={field_name}, round_trip=True)[field_name]
                if field_name in serializer_fields
                else getattr(value, field_name)
            )
            for field_name in type(value).model_fields
        }
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


_DATE_FIELD_NAMES = frozenset(
    {
        "applies_from",
        "applies_to",
        "closes_on",
        "consolidated_as_of",
        "effective_from",
        "effective_to",
        "event_date",
        "governs_periods_from",
        "governs_periods_to",
        "observed_at",
        "opens_on",
        "payment_cutoff_on",
        "published_at",
        "retrieved_at",
        "reviewed_at",
        "span_from",
        "span_to",
        "valid_from",
        "valid_to",
    }
)


def _immutable_json_value(value: object, *, field_name: str | None = None) -> object:
    """Restore JSON primitives only for declared strict authority field names.

    The registry models are intentionally strict and model their declared
    collections as tuples and date fields as :class:`date`. JSON has only
    arrays and date strings, so this converts those authenticated wire shapes
    before model reconstruction. The artifact signature authenticates this
    canonical JSON; the schema still validates every declared invariant.
    """
    if isinstance(value, Mapping):
        return {str(key): _immutable_json_value(item, field_name=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_immutable_json_value(item, field_name=field_name) for item in value)
    if field_name in _DATE_FIELD_NAMES and isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            # A catalogue identifier may happen to use a date-shaped field
            # name at a deeper mapping level; its declared schema remains the
            # authority for interpreting that value.
            return value
    return value


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


def _decode_base64(value: str) -> bytes:
    try:
        return b64decode(value.encode("ascii"), validate=True)
    except ValueError as exc:
        raise AuthorityArtifactFormatError(
            "published authority artifact contains invalid base64 source evidence"
        ) from exc
