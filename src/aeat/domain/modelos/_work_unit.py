"""Modelo work-unit value records.

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

import hashlib
from collections.abc import Iterator, Mapping, ValuesView
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..profile._ccaa import CCAA
from ._codes import ModeloCode
from ._errors import ModeloValidationError


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


_ActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_DiscardReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_StaleReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_OptionalHex64 = Annotated[
    str | None,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
]

_HEX_WORK_UNIT_ID_LENGTH = 64
"""Length of the SHA-256 hex digest used as the work-unit identifier."""


from ._ids import BucketId as _BucketId
from ._ids import WorkUnitId as _WorkUnitId
_Period = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16),
]
_RevisionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


def derive_work_unit_id(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
) -> str:
    """Return the deterministic ``work_unit_id`` for a four-axis key.

    The five inputs are normalised (stripped, lowercased where
    case is insignificant) and joined with a stable separator that
    cannot appear inside any of the inputs. The resulting bytes
    are hashed with SHA-256 and rendered as 64-character lowercase
    hex — identical to the catalogue-key shape the project uses
    elsewhere for content-addressed identifiers.

    Determinism is the operative contract: callers that build the
    same four-axis key see the same identifier without
    round-tripping through storage.
    """

    components = (
        bucket_id.strip(),
        modelo.strip().upper(),
        str(int(filing_year)),
        period.strip().upper(),
        revision_id.strip(),
    )
    payload = "\x1f".join(components).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
        period: Filing period token (e.g. ``"Q1"``, ``"4T"``,
            ``"0A"``, ``"01"``).
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
        census_stamped_stale_at: Timezone-aware UTC timestamp the
            stale-cascade walker set when ``aeat config profile census
            apply`` superseded the census facts the work unit depended
            on. ``None`` while the unit is still census-current.
            Set/unset together with ``census_stale_reason``.
        census_stale_reason: Operator-readable text recording why the
            unit was marked stale (typically the
            superseding snapshot id). ``None`` while not stale; both
            this and ``census_stamped_stale_at`` set together when
            stale, both ``None`` otherwise.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    work_unit_id: _WorkUnitId
    bucket_id: _BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    period: _Period
    revision_id: _RevisionId
    name: _DisplayName
    created_at: datetime
    updated_at: datetime
    state: WorkUnitState = WorkUnitState.BORRADOR
    discarded_at: datetime | None = None
    discarded_by: _ActorLabel | None = None
    discard_reason: _DiscardReason | None = None
    current_calculation_revision_id: _OptionalHex64 = None
    filed_calculation_revision_id: _OptionalHex64 = None
    current_filing_record_id: _OptionalHex64 = None
    census_stamped_stale_at: datetime | None = None
    census_stale_reason: _StaleReason | None = None
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
                f"year={self.filing_year}, period={self.period!r}, revision={self.revision_id!r})"
            )
        if self.updated_at < self.created_at:
            raise ModeloValidationError(
                f"updated_at {self.updated_at.isoformat()} precedes created_at {self.created_at.isoformat()}"
            )
        if self.state is WorkUnitState.BORRADOR:
            if self.discarded_at is not None or self.discarded_by is not None or self.discard_reason is not None:
                raise ModeloValidationError(
                    "draft work unit must not carry discard metadata (discarded_at / discarded_by / discard_reason)"
                )
        elif self.state is WorkUnitState.DESCARTADO:
            if self.discarded_at is None or self.discarded_by is None:
                raise ModeloValidationError("discarded work unit must carry discarded_at and discarded_by")
            if self.discarded_at < self.created_at:
                raise ModeloValidationError(
                    f"discarded_at {self.discarded_at.isoformat()} precedes created_at {self.created_at.isoformat()}"
                )
        stamped = self.census_stamped_stale_at is not None
        reasoned = self.census_stale_reason is not None
        if stamped != reasoned:
            raise ModeloValidationError(
                "census_stamped_stale_at and census_stale_reason must be set or unset together",
            )
        if stamped and self.census_stamped_stale_at is not None and self.census_stamped_stale_at < self.created_at:
            raise ModeloValidationError(
                f"census_stamped_stale_at {self.census_stamped_stale_at.isoformat()} "
                f"precedes created_at {self.created_at.isoformat()}",
            )
        return self


class WorkUnitCatalogue(BaseModel):
    """Immutable catalogue of every work unit known in storage.

    The catalogue is a frozen mapping keyed by ``work_unit_id``.
    Lookups by other shapes (bucket, modelo, year, period) are
    iterated at the catalogue boundary; the catalogue itself does
    not index secondary keys.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
        """Build a catalogue from an iterable / mapping of work units."""
        if isinstance(units, tuple):
            mapping: dict[str, WorkUnit] = {}
            for unit in units:
                if not isinstance(unit, WorkUnit):
                    raise ModeloValidationError(f"expected WorkUnit, got {type(unit).__name__}")
                if unit.work_unit_id in mapping:
                    raise ModeloValidationError(f"duplicate work_unit_id {unit.work_unit_id!r}")
                mapping[unit.work_unit_id] = unit
            return cls(work_units=mapping)
        return cls(work_units={str(k): v for k, v in units.items()})

    def __iter__(self) -> Iterator[WorkUnit]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
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
        """Return the work unit for ``work_unit_id`` or ``None`` if absent."""
        return self.work_units.get(work_unit_id)

    def values(self) -> ValuesView[WorkUnit]:
        """Return a view of every work unit in the catalogue."""
        return self.work_units.values()


__all__ = [
    "WorkUnit",
    "WorkUnitCatalogue",
    "WorkUnitState",
    "derive_work_unit_id",
]
