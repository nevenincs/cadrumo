"""Modelo work-unit value records.

:class:`WorkUnit` and :class:`WorkUnitCatalogue` bind a :class:`ModeloCode`,
:class:`Period`, :class:`BucketId`, and :data:`WorkUnitId` into the
operator-facing handle addressed by :func:`derive_work_unit_id`.

A modelo work unit is a stable, bucket-scoped handle over one
calculation revision of a specific (modelo, year, period). It is
the operator-facing object the modelo workflow verbs
(``calculate``, ``verify``, ``file``, ``filing-record``, etc.)
attach state to. The work unit itself carries metadata only —
its calculation results, verification reports, and filing records
live in separate stores keyed by ``work_unit_id``.

The work-unit identifier is a SHA-256 hex digest derived
deterministically from the four-axis key
``(bucket_id, modelo, filing_year, period, revision_id)``. The
deterministic derivation means two consumers of the same
four-axis key see the same ``work_unit_id`` without round-tripping
through storage. Renaming a work unit does not change the
identifier; ``name`` is a display-only attribute.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, ValuesView
from enum import StrEnum
from typing import Annotated, cast, override

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, Hex64Str, Period
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, WorkUnitId
from ...core.time import UtcInstant
from ..calculations.registry.ids import RevisionId
from ..contribuyente.ccaa import CCAA
from ._codes import ModeloCode
from .errors import ModeloValidationError
from .filing_text import ModeloActorLabel, OperatorReason


class WorkUnitState(StrEnum):
    """Closed enumeration of work-unit lifecycle states.

    * ``BORRADOR`` — default state at creation. The work unit
      participates in default listings and accepts mutation
      (rename, future calculation revisions).
    * ``DESCARTADO`` — operator marked the work unit abandoned.
      Excluded from default listings; mutations are rejected.
      Revision payloads remain in storage for audit; the work
      unit cannot be re-activated.
    """

    BORRADOR = "borrador"
    DESCARTADO = "descartado"


_RevisionId = RevisionId
"""The canonical registry revision-id type, not a second local constraint.

``revision_id`` names a registry revision, so the value type that decides which
spellings exist belongs to the registry. The local alias this replaced only
stripped whitespace and bounded length, which accepted values the registry
grammar refuses -- ``"BAD revision/with spaces"`` among them. Because membership
and law-resolution checks run later in the application layer, such a revision was
accepted, content-addressed into the work-unit identity, and persisted before any
resolver could object, leaving a durable record whose identity was derived from a
value no registry revision could ever match.
"""
_DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


def derive_work_unit_id(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    revision_id: RevisionId,
) -> str:
    """Return the deterministic ``work_unit_id`` for a four-axis key.

    The five inputs are normalised (stripped, upper-cased where case is
    insignificant) into a keyed payload and hashed through
    :func:`~cadrumo.core.hashing.content_hash_hex`, the project's one
    content-addressing primitive, yielding 64-character lowercase hex.

    This derivation previously joined the components with a separator
    byte and called :func:`~cadrumo.core.hashing.sha256_hex` directly,
    while this docstring claimed it was "identical to the catalogue-key
    shape the project uses elsewhere". It was not: every other derived
    id in the tree hashes canonical JSON through ``content_hash_hex``.
    Routing this one onto that primitive makes the claim true and leaves
    one content-addressing mechanism rather than two.

    Determinism is the operative contract: callers that build the
    same four-axis key see the same identifier without
    round-tripping through storage.
    """
    if period.filing_year != int(filing_year):
        raise ModeloValidationError(
            f"filing_year {filing_year!r} does not match period year {period.filing_year!r}",
        )
    payload = {
        "bucket_id": bucket_id.strip(),
        "modelo": modelo.strip().upper(),
        "filing_year": int(filing_year),
        "period": period.registry_token,
        "revision_id": revision_id.strip(),
    }
    return content_hash_hex(payload)


class WorkUnit(BaseModel):
    """One operator-facing modelo calculation work unit.

    Attributes:
        work_unit_id: Lowercase 64-char SHA-256 derived from
            ``(bucket_id, modelo, filing_year, period, revision_id)``
            by :func:`derive_work_unit_id`. The identifier is
            stable across renames.
        bucket_id: Stable bucket identity the work unit lives
            inside. Two work units with the same modelo / year /
            period / revision in different buckets have different
            ``work_unit_id`` values.
        modelo: AEAT modelo code (e.g. ``"303"``, ``"130"``).
        filing_year: Tax year for which the modelo is being filed.
        period: Typed filing period value carrying the filing year and
            bare registry token (e.g. ``"4T"``, ``"0A"``, ``"01"``).
        revision_id: Stable id of the registry-known modelo
            revision the work unit targets.
        name: Display name. Defaults to ``"<modelo>-<year>-<period>"``
            when the operator does not supply one explicitly.
        created_at: Timezone-aware UTC timestamp at first creation.
        updated_at: Timezone-aware UTC timestamp at the most recent
            mutation. Equals ``created_at`` on a fresh work unit.
        state: Lifecycle state — ``BORRADOR`` by default, ``DESCARTADO``
            once the operator marks the unit abandoned via the
            discard verb.
        discarded_at: Timezone-aware UTC timestamp set at discard
            time. ``None`` for non-discarded units.
        discarded_by: Actor label captured at discard time.
            ``None`` for non-discarded units.
        discard_reason: Operator-supplied free-text reason for
            the discard. ``None`` when no reason was given (or
            when the unit is not discarded).
    """

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    revision_id: _RevisionId
    name: _DisplayName
    created_at: UtcInstant
    updated_at: UtcInstant
    state: WorkUnitState = WorkUnitState.BORRADOR
    discarded_at: UtcInstant | None = None
    discarded_by: ModeloActorLabel | None = None
    discard_reason: OperatorReason | None = None
    current_calculation_revision_id: Hex64Str | None = None
    filed_calculation_revision_id: Hex64Str | None = None
    current_filing_record_id: Hex64Str | None = None
    # ISD (Modelo 650/660) and ITPyAJD (Modelo 600/620) context axis:
    # CCAA of the causante (Ley 22/2009 Art. 32) or the bien-location CCAA.
    # None for modelos where jurisdiction follows the declarant's profile CCAA.
    causante_ccaa: CCAA | None = None

    @field_validator("modelo", mode="before")
    @classmethod
    def _coerce_modelo(cls, value: object) -> ModeloCode:
        """Accept a raw modelo string and coerce it into ``ModeloCode``.

        Pydantic's strict mode rejects implicit ``str`` → ``ModeloCode``
        coercion; this validator runs before strict mode so callers
        can pass a plain ``str`` from CLI input without losing the
        typed-key invariant downstream.
        """
        if isinstance(value, ModeloCode):
            return value
        if isinstance(value, str):
            return ModeloCode(value)
        raise ModeloValidationError(f"expected ModeloCode or str, got {type(value).__name__}")

    @model_validator(mode="after")
    def _enforce_derived_id(self) -> WorkUnit:
        """Confirm ``work_unit_id`` matches the deterministic derivation.

        The identifier is content-addressed; if a caller persists a
        work unit with a mismatched id (e.g. through manual
        editing), reads will refuse the record. This keeps the
        catalogue's content-addressing invariant intact.
        """
        if self.period.filing_year != self.filing_year:
            raise ModeloValidationError(
                f"filing_year {self.filing_year!r} does not match period year {self.period.filing_year!r}",
            )
        derived = derive_work_unit_id(
            bucket_id=self.bucket_id,
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            revision_id=self.revision_id,
        )
        if derived != self.work_unit_id:
            raise ModeloValidationError(
                f"work_unit_id {self.work_unit_id!r} does not match the derived id "
                f"{derived!r} for (bucket={self.bucket_id!r}, modelo={self.modelo!r}, "
                f"year={self.filing_year}, period={self.period!r}, revision={self.revision_id!r})",
            )
        if self.updated_at < self.created_at:
            raise ModeloValidationError(
                f"updated_at {self.updated_at.isoformat()} precedes created_at {self.created_at.isoformat()}",
            )
        if self.state is WorkUnitState.BORRADOR:
            if self.discarded_at is not None or self.discarded_by is not None or self.discard_reason is not None:
                raise ModeloValidationError(
                    "draft work unit must not carry discard metadata (discarded_at / discarded_by / discard_reason)",
                )
        elif self.state is WorkUnitState.DESCARTADO:
            if self.discarded_at is None or self.discarded_by is None:
                raise ModeloValidationError("discarded work unit must carry discarded_at and discarded_by")
            if self.discarded_at < self.created_at:
                raise ModeloValidationError(
                    f"discarded_at {self.discarded_at.isoformat()} precedes created_at {self.created_at.isoformat()}",
                )
        return self


class WorkUnitCatalogue(BaseModel):
    """Immutable catalogue of every work unit known in storage.

    The catalogue is a frozen mapping keyed by ``work_unit_id``.
    Lookups by other shapes (bucket, modelo, year, period) are
    iterated at the catalogue boundary; the catalogue itself does
    not index secondary keys.
    """

    model_config = STRICT_FROZEN_CONFIG

    work_units: Mapping[str, WorkUnit] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> WorkUnitCatalogue:
        """Pin that every mapping key equals its record's ``work_unit_id``."""
        for key, unit in self.work_units.items():
            if key != unit.work_unit_id:
                raise ModeloValidationError(f"catalogue key {key!r} does not match work_unit_id {unit.work_unit_id!r}")
        return self

    @classmethod
    def from_work_units(cls, units: Mapping[str, WorkUnit] | tuple[WorkUnit, ...]) -> WorkUnitCatalogue:
        """Build a :class:`WorkUnitCatalogue` from an iterable / mapping of work units."""
        if isinstance(units, tuple):
            mapping: dict[str, WorkUnit] = {}
            # CAST-RATIONALE-WORK-UNIT-CATALOGUE-TUPLE-NARROW: the isinstance
            # check above already narrows the union to tuple[WorkUnit, ...];
            # ty narrows the tuple union conservatively, so the cast restates
            # what pyright itself already knows.
            # nosemgrep: no-cast-in-domain-application
            units_tuple = cast(tuple[WorkUnit, ...], units)  # pyright: ignore[reportUnnecessaryCast]
            for unit in units_tuple:
                if unit.work_unit_id in mapping:
                    raise ModeloValidationError(f"duplicate work_unit_id {unit.work_unit_id!r}")
                mapping[unit.work_unit_id] = unit
            return cls(work_units=mapping)
        return cls(work_units={str(k): v for k, v in units.items()})

    @override
    def __iter__(self) -> Iterator[WorkUnit]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields WorkUnit records, not BaseModel field-value tuples
        """Iterate the loaded work units (not the keys)."""
        return iter(self.work_units.values())

    def __len__(self) -> int:
        return len(self.work_units)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, WorkUnit):
            return key.work_unit_id in self.work_units
        if isinstance(key, str):
            return key in self.work_units
        return False

    def get(self, work_unit_id: str) -> WorkUnit | None:
        """Return the work unit for ``work_unit_id`` or ``None`` if absent.

        Returns:
            The :class:`WorkUnit` for the given id, or ``None`` when not found.
        """
        return self.work_units.get(work_unit_id)

    def values(self) -> ValuesView[WorkUnit]:
        """Return a view of every :class:`WorkUnit` in the catalogue."""
        return self.work_units.values()


__all__ = [
    "WorkUnit",
    "WorkUnitCatalogue",
    "WorkUnitState",
    "derive_work_unit_id",
]
