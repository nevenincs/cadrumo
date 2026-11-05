"""Canonical on-disk documents of the profile acceleration receipt and its retirement journal.

The strict models, the schema-independent header and the exact-byte parse and
hydration helpers live apart from the custody operations that publish, resume
and retire receipts.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .....core.base64_codec import b64_decode, b64_encode
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import (
    canonical_json_bytes,
    reject_duplicate_json_members,
    reject_json_constant,
)
from .....core.models import STRICT_FROZEN_CONFIG
from .....core.time.utc import validate_utc_aware
from . import acceleration_receipt_crypto
from .sign_in_generation import SignInGeneration


class AccelerationReceiptDocument(BaseModel):
    """On-disk JSON envelope for one persisted profile session."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID
    custody_generation: int = Field(ge=1)
    dek_epoch: str = Field(min_length=1, max_length=128)
    login_binding: acceleration_receipt_crypto.LoginBindingDigest
    sign_in_lineage: UUID
    sign_in_generation: int = Field(ge=1)
    issued_at: str = Field(min_length=1)
    idle_deadline: str = Field(min_length=1)
    absolute_deadline: str = Field(min_length=1)
    nonce_b64: str = Field(min_length=1)
    ciphertext_b64: str = Field(min_length=1)
    tag_b64: str = Field(min_length=1)


class _ReceiptHeader(BaseModel):
    """The identity every receipt schema shares, read before the strict parse.

    It ignores the remaining fields on purpose: a record from another build
    must still yield the profile and session that name its keychain half, so
    the delete-only path can retire both halves.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="ignore")

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID


type DecodedReceipt = acceleration_receipt_crypto.PersistedProfileSession | _ReceiptHeader
"""A current record, or only the header of a record from another schema."""


class PendingReceiptRetirementDocument(BaseModel):
    """Bounded exact-byte receipt for an interrupted session-key rotation.

    ``predecessor_b64`` is absent only for the first mint.  Keeping both
    canonical receipt byte strings makes recovery an equality decision, not a
    reconstruction from mutable metadata: if the current receipt is the
    predecessor the staged successor is retired; if it is the successor the
    predecessor is retired.  Any third receipt is a concurrent substitution
    and is preserved/refused.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(ge=1)
    profile_id: UUID
    predecessor_b64: str | None = None
    successor_b64: str = Field(min_length=1)


def document_from_record(record: acceleration_receipt_crypto.PersistedProfileSession) -> AccelerationReceiptDocument:
    """Build the acceleration receipt document from a persisted profile session record."""
    return AccelerationReceiptDocument(
        schema_version=record.schema_version,
        profile_id=record.profile_id,
        session_id=record.session_id,
        custody_generation=record.custody_generation,
        dek_epoch=record.dek_epoch,
        login_binding=record.login_binding,
        sign_in_lineage=record.sign_in.lineage,
        sign_in_generation=record.sign_in.generation,
        issued_at=record.issued_at.isoformat(),
        idle_deadline=record.idle_deadline.isoformat(),
        absolute_deadline=record.absolute_deadline.isoformat(),
        nonce_b64=b64_encode(record.nonce),
        ciphertext_b64=b64_encode(record.ciphertext),
        tag_b64=b64_encode(record.tag),
    )


def record_from_document(document: AccelerationReceiptDocument) -> acceleration_receipt_crypto.PersistedProfileSession:
    """Hydrate the strict record from an on-disk document.

    Raises:
        ValueError: On any malformed field (base64, datetime, enum, or
            length); the resume evaluation maps this to the ``MALFORMED``
            refusal.
    """
    return acceleration_receipt_crypto.PersistedProfileSession(
        schema_version=document.schema_version,
        profile_id=document.profile_id,
        session_id=document.session_id,
        custody_generation=document.custody_generation,
        dek_epoch=document.dek_epoch,
        login_binding=document.login_binding,
        sign_in=SignInGeneration(lineage=document.sign_in_lineage, generation=document.sign_in_generation),
        issued_at=validate_utc_aware(datetime.fromisoformat(document.issued_at)),
        idle_deadline=validate_utc_aware(datetime.fromisoformat(document.idle_deadline)),
        absolute_deadline=validate_utc_aware(datetime.fromisoformat(document.absolute_deadline)),
        nonce=b64_decode(document.nonce_b64),
        ciphertext=b64_decode(document.ciphertext_b64),
        tag=b64_decode(document.tag_b64),
    )


def canonical_document_bytes(document: BaseModel) -> bytes:
    """Encode one strict receipt with the sole accepted JSON byte spelling."""
    return canonical_json_bytes(document.model_dump(mode="json"))


def _parse_json_object(payload: bytes) -> dict[str, object]:
    """Decode one JSON object, refusing duplicate keys and non-finite constants."""
    decoded = payload.decode(UTF_8_ENCODING)
    parsed = json.loads(
        decoded,
        object_pairs_hook=reject_duplicate_json_members,
        parse_constant=reject_json_constant,
    )
    if not isinstance(parsed, dict):
        raise ValueError("session receipt must be a JSON object")
    return cast(dict[str, object], parsed)


def parse_canonical_document(payload: bytes, model: type[BaseModel]) -> BaseModel:
    """Decode exact canonical JSON without accepting duplicate-key aliases."""
    _parse_json_object(payload)
    # ``strict`` models deliberately accept their wire UUID/datetime strings
    # only through Pydantic's JSON boundary.  The independent ``json.loads``
    # above owns duplicate/non-finite refusal before this typed decode.
    document = model.model_validate_json(payload)
    if canonical_document_bytes(document) != payload:
        raise ValueError("session receipt bytes are not canonical")
    return document


def parse_receipt_header(payload: bytes) -> _ReceiptHeader:
    """Read the schema-independent identity of one canonical receipt."""
    parsed = _parse_json_object(payload)
    if canonical_json_bytes(parsed) != payload:
        raise ValueError("session receipt bytes are not canonical")
    return _ReceiptHeader.model_validate_json(payload)
