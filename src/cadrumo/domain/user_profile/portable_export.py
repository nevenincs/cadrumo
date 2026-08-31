"""Portable-export bundle for cross-bucket user-profile transfer.

This module is isolated from :mod:`domain.user_profile.values` so the
four heavy domain types it composes (:class:`CalculationRevision`,
``WorkUnit``, ``Transaction``, :class:`ModeloRecord`) and their transitive
registry-parse cost do not enter ``sys.modules`` at user-profile package
init. The :class:`UserProfileRecord` is included via the ``profile`` field
of :class:`UserProfilePortableExport`. This module is the canonical
definition site; :mod:`domain.user_profile` exposes the same class
through lazy ``__getattr__`` resolution so package import stays light.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterable, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Literal, cast

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core.classification.policies import SensitivityClass
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now as _utc_now
from ...core.time.utc import UtcInstant, validate_utc_aware
from ..modelos.calculation_revision import CalculationRevision as _CalculationRevision
from ..modelos.filing_record import ModeloRecord as _ModeloRecord
from ..modelos.work_unit import WorkUnit as _WorkUnit
from ..transactions.models import Transaction as _Transaction
from .values import UserProfileRecord


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

    A bundle addresses each carried row by its **natural** object key (the
    store-derived identifier), never by the stored HMAC lookup digest: the
    digest is keyed by the per-bucket data-encryption key, so a source-bucket
    digest is unreadable in the recipient bucket (proven by the custody
    roundtrip tests). On import the carried payload is re-saved through the
    owning store's save path, which re-derives the natural key under the
    recipient DEK and re-encrypts. The natural ``object_key`` is carried for
    coverage auditing and for the bespoke stores that re-save through the raw
    secure-object substrate.

    ``payload_b64`` is the canonical adapter-serialised form: for typed stores
    it is the :class:`Envelope` JSON bytes the store persists, and for the
    attachment-blob store it is the raw decrypted blob bytes (which are not
    JSON). The owning store adapter is the sole interpreter of these bytes.
    ``classification`` carries the row's :class:`SensitivityClass` so import
    replays the same namespace sensitivity contract.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: UtcInstant
    payload_b64: str = Field(min_length=1)

    @field_validator("written_at")
    @classmethod
    def _written_at_is_utc(cls, value: datetime) -> datetime:
        """Reject a carried write instant that is naive or not UTC.

        The bundle serialises as JSON, which preserves the offset, so a
        carried object can be held to the canonical instant contract rather
        than transporting an ambiguous local time into another bucket.
        """
        return validate_utc_aware(value)

    @field_validator("namespace", "object_key")
    @classmethod
    def _required_text_has_content(cls, value: str) -> str:
        return _clean_required_text(value, field_name="value")

    @field_validator("payload_b64")
    @classmethod
    def _payload_is_canonical_base64(cls, value: str) -> str:
        _decode_canonical_base64(value, field_name="payload_b64")
        return value

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
        # CAST-RATIONALE-NAMESPACES-ITERABLE: isinstance narrows to Iterable but
        # not its element type; each item is validated as str in the loop.
        # nosemgrep: no-cast-in-domain-application
        for item in cast(Iterable[object], value):
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
        # CAST-RATIONALE-ROW-COUNTS-MAPPING: isinstance narrows to Mapping but
        # not its type parameters; each key/value pair is validated in the
        # loop below.
        # nosemgrep: no-cast-in-domain-application
        for raw_namespace, raw_count in cast(Mapping[object, object], value).items():
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

    Which versions are accepted is the bundle lineage's decision, not this
    model's, so it is not restated here. This is the version-3 SHAPE: it
    carries ``profile`` plus the financial-history fields
    ``work_units``, ``ledger_transactions``, ``calculation_revisions``, and
    ``filing_records``. It also declares the v3 generic secure-object carry
    surface and coverage manifest; those fields default empty until the
    transport-aware serialise/deserialise phases populate them.

    Encrypted-material blobs are NOT included: the export strips encrypted
    material and re-encrypts it under the recipient bucket's DEK on import.
    """

    model_config = _STRICT_FROZEN

    # Required, with NO default, on two grounds. A default here would be a
    # second declaration of the current write version, which is owned by the
    # bundle lineage alongside its durability floor and its upgrader table --
    # and a version bump must land its hop with it, so the two halves of one
    # obligation cannot sit in different layers. A default is also silent
    # read-tolerance: a payload carrying no version would validate as whichever
    # number happened to be written here, so a bundle nothing wrote would parse
    # as current. Absent must refuse.
    bundle_schema_version: int = Field(ge=1)
    # Provenance metadata, deliberately NOT content-addressable: two exports of
    # identical bucket state differ by this timestamp. That is acceptable because
    # the sealed-archive transport is itself non-deterministic by design (a random
    # AEAD nonce per seal), so making the bundle byte-stable would not yield a
    # content-addressable archive. The strict roundtrip gate compares re-loaded
    # repository objects, not this wrapper, so the timestamp does not affect it.
    # Held to the same instant contract as the carried rows below. It was a
    # bare ``datetime`` while ``CarriedSecureObject.written_at`` validated, so
    # one export boundary transported two competing timestamp policies: the
    # outer provenance stamp accepted a naive or offset value that every row
    # it wrapped would have refused.
    exported_at: UtcInstant = Field(default_factory=_utc_now)
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
