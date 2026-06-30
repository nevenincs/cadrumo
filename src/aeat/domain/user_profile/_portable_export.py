"""Portable-export bundle for cross-bucket user-profile transfer.

This module is isolated from :mod:`aeat.domain.user_profile._values` so the
four heavy domain types it composes (:class:`CalculationRevision`,
``WorkUnit``, ``Transaction``, :class:`ModeloRecord`) and their transitive
registry-parse cost do not enter ``sys.modules`` at user-profile package
init. The :class:`UserProfileRecord` is included via the ``profile`` field
of :class:`UserProfilePortableExport`. This module is the canonical
definition site; :mod:`aeat.domain.user_profile` exposes the same class
through lazy ``__getattr__`` resolution so package import stays light.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterable, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.classification import SensitivityClass
from ...core.time import now as utc_now
from ..modelos._calculation_revision import CalculationRevision as _CalculationRevision
from ..modelos._filing_record import ModeloRecord as _ModeloRecord
from ..modelos._work_unit import WorkUnit as _WorkUnit
from ..transactions._models import Transaction as _Transaction
from ._values import UserProfileRecord

_SECURE_OBJECT_KEY_BYTES = 32


def _clean_required_text(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def _decode_canonical_base64(value: str, *, field_name: str) -> bytes:
    text = _clean_required_text(value, field_name=field_name)
    try:
        decoded = base64.b64decode(text.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError(f"{field_name} must be canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != text:
        raise ValueError(f"{field_name} must be canonical base64")
    return decoded


class CarriedSecureObject(BaseModel):
    """One decrypted secure-object row carried by a v3 bundle.

    The generic custody path addresses rows by the stored HMAC lookup digest
    because natural object keys are not recoverable from the substrate index.
    Payload bytes are base64 encoded so full-custody rows can carry arbitrary
    decrypted bytes, including attachment blobs that are not JSON.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    hashed_object_key_b64: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload_b64: str = Field(min_length=1)

    @field_validator("namespace")
    @classmethod
    def _required_text_has_content(cls, value: str) -> str:
        return _clean_required_text(value, field_name="namespace")

    @field_validator("hashed_object_key_b64")
    @classmethod
    def _hashed_object_key_is_32_bytes(cls, value: str) -> str:
        decoded = _decode_canonical_base64(value, field_name="hashed_object_key_b64")
        if len(decoded) != _SECURE_OBJECT_KEY_BYTES:
            raise ValueError("hashed_object_key_b64 must decode to 32 bytes")
        return value

    @field_validator("payload_b64")
    @classmethod
    def _payload_is_canonical_base64(cls, value: str) -> str:
        _decode_canonical_base64(value, field_name="payload_b64")
        return value

    @property
    def hashed_object_key(self) -> bytes:
        """Return the stored secure-object lookup digest."""
        return _decode_canonical_base64(self.hashed_object_key_b64, field_name="hashed_object_key_b64")

    @property
    def payload(self) -> bytes:
        """Return the decrypted payload bytes carried by the bundle."""
        return _decode_canonical_base64(self.payload_b64, field_name="payload_b64")


class CoverageManifest(BaseModel):
    """Namespace coverage declared by a portable-export bundle."""

    model_config = _STRICT_FROZEN

    custody_profile: Literal["structured", "full"] = "structured"
    carried_namespaces: tuple[str, ...] = ()
    excluded_namespaces: tuple[str, ...] = ()
    row_counts_by_namespace: Mapping[str, int] = Field(default_factory=lambda: MappingProxyType({}))

    @field_validator("carried_namespaces", "excluded_namespaces", mode="before")
    @classmethod
    def _normalize_namespaces(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str | bytes):
            raise ValueError("namespaces must be a sequence of namespace strings")
        if not isinstance(value, Iterable):
            raise ValueError("namespaces must be iterable")
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("namespaces must contain strings only")
            namespace = _clean_required_text(item, field_name="namespace")
            if namespace not in seen:
                normalized.append(namespace)
                seen.add(namespace)
        return tuple(normalized)

    @field_validator("row_counts_by_namespace", mode="before")
    @classmethod
    def _normalize_row_counts(cls, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("row_counts_by_namespace must be a mapping")
        row_counts: dict[str, int] = {}
        for raw_namespace, raw_count in value.items():
            if not isinstance(raw_namespace, str):
                raise ValueError("row count namespaces must be strings")
            namespace = _clean_required_text(raw_namespace, field_name="row count namespace")
            if not isinstance(raw_count, int) or isinstance(raw_count, bool):
                raise ValueError("row counts must be integers")
            if raw_count < 0:
                raise ValueError("row counts must be non-negative")
            row_counts[namespace] = raw_count
        return row_counts

    @field_validator("row_counts_by_namespace")
    @classmethod
    def _freeze_row_counts(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        return MappingProxyType(dict(value))

    @field_serializer("row_counts_by_namespace")
    def _serialize_row_counts(self, value: Mapping[str, int]) -> dict[str, int]:
        return dict(value)


class UserProfilePortableExport(BaseModel):
    """User-directed portable profile export payload.

    ``bundle_schema_version`` gates forward-compatible import: callers that read
    an export bundle compare this integer to their supported range before
    attempting to parse ``profile``. Increment it when the serialised shape
    changes in a backward-incompatible way.

    Version 3 is the only supported shape (this is a pre-beta project with no
    released bundles; earlier shapes are deleted, not bridged — see
    ``no-legacy-compatibility``). It carries ``profile`` plus the
    financial-history fields ``work_units``, ``ledger_transactions``,
    ``calculation_revisions``, and ``filing_records``. It also declares the v3
    generic secure-object carry surface and coverage manifest; those fields
    default empty until the transport-aware serialise/deserialise phases populate
    them.

    Encrypted-material blobs are NOT included (ADR D2: strip encrypted
    material; re-encrypt under recipient bucket DEK on import).
    """

    model_config = _STRICT_FROZEN

    bundle_schema_version: int = Field(default=3, ge=1)
    # Provenance metadata, deliberately NOT content-addressable: two exports of
    # identical bucket state differ by this timestamp. That is acceptable because
    # the sealed-archive transport is itself non-deterministic by design (a random
    # AEAD nonce per seal), so making the bundle byte-stable would not yield a
    # content-addressable archive. The strict roundtrip gate compares re-loaded
    # repository objects, not this wrapper, so the timestamp does not affect it.
    exported_at: datetime = Field(default_factory=utc_now)
    profile: UserProfileRecord

    # --- Financial-history fields --------------------------------------------
    # All default to empty tuples because a bucket may legitimately carry no
    # rows in a category; the import path checks bundle_schema_version first.

    work_units: tuple[_WorkUnit, ...] = ()
    ledger_transactions: tuple[_Transaction, ...] = ()
    calculation_revisions: tuple[_CalculationRevision, ...] = ()
    filing_records: tuple[_ModeloRecord, ...] = ()

    # --- v3 generic secure-object carry contract -----------------------------
    carried_objects: tuple[CarriedSecureObject, ...] = ()
    coverage_manifest: CoverageManifest = Field(default_factory=CoverageManifest)

__all__ = ["UserProfilePortableExport"]
