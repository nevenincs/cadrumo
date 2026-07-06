"""Per-ejercicio cross-period IVA prorrata register (LIVA arts. 102-106).

The provisional-to-definitive IVA prorrata lifecycle is inherently cross-year:
under prorrata general only the deduction percentage of soportado is deductible
in each liquidation period (art. 104.Uno); the percentage provisionally
applicable each year is the prior year's definitive (art. 105.Uno), with the
regulated alternatives of an AEAT-authorised provisional (art. 105.Dos) and the
inicio-de-actividades proposed percentage (art. 105.Tres via art. 111.Dos); the
last liquidation of the year computes the definitive prorrata from the year's
actual operations and regularises the provisional deductions (art. 105.Cuatro).

This module is the CARRY HOME for that lifecycle: a durable per-ejercicio
:class:`ProrrataRegister`, one :class:`ProrrataRegisterEntry` per
``(ejercicio, sector)`` carrying the regime, the provisional percentage in force
with its regulated :class:`~core.ProrrataProvisionalProvenance`, and — once
settled — the definitive percentage with the annual volume inputs it derived
from. The pure precedence-ladder resolver
(:func:`resolve_provisional_percentage`) selects the in-force provisional
percentage among candidate provenances (authorised/inicio outranking the carried
prior definitive) and returns a visible unresolved state rather than any
fabricated default — no percentage is ever assumed.

This is a taxpayer-fact store, sibling to :mod:`domain.bienes_inversion`: it
holds the per-ejercicio percentages and their provenance, never the regulatory
constants. The prorrata compute substrate (:mod:`domain.iva`:
``compute_prorrata_definitiva_anual``, ``compute_regularizacion_prorrata_anual``)
is consumed at settlement, not re-implemented here, and this module reads no
secure-object store — the seed, in-year apportionment, and settlement write-back
live in the application layer.

See Also:
    :mod:`adapters.persistence.profile.prorrata_register`
        FINANCIAL secure-object repository that stores the register singleton.
    :mod:`domain.iva`
        Legal prorrata substrate that computes the definitive percentage from
        annual volumes and the art. 105.Cuatro regularisation cuota.
    :mod:`domain.bienes_inversion`
        Sibling per-taxpayer-fact register whose shape this mirrors.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ...core import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ...core.errors import AeatError as _AeatError


class ProrrataRegisterError(_AeatError):
    """Raised when a prorrata-register record is structurally invalid."""


class ProrrataRegisterValidationError(ProrrataRegisterError, ValueError):
    """Raised when a prorrata-register model fails Pydantic validation."""


PRORRATA_REGISTER_SCHEMA_VERSION = "1"
"""Forward-compatible schema version stamped onto every record in this module."""

_HUNDRED = Decimal("100")
#: Lowest ejercicio the register accepts. IVA prorrata (LIVA arts. 102-106)
#: predates it, but a pre-2000 ejercicio can never be a modelled filing year.
_MIN_EJERCICIO = 2000
_MAX_EJERCICIO = 2099

#: Provenances that record an externally-referenced percentage (art. 105.Dos /
#: 105.Tres); these MUST carry an ``authorisation_reference`` and no other
#: provenance may.
_REFERENCED_PROVENANCES = frozenset(
    {
        ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
    }
)

#: Single declared precedence ladder (LIVA art. 105): the AEAT-authorised
#: provisional (105.Dos) and the inicio-de-actividades proposal (105.Tres)
#: outrank the carried prior definitive (105.Uno). An explicit AEAT
#: authorisation outranks a self-proposed inicio percentage as a deterministic
#: tie-break; the two are mutually exclusive in practice. Lower index = higher
#: precedence.
_PROVENANCE_PRECEDENCE: tuple[ProrrataProvisionalProvenance, ...] = (
    ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
    ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
    ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
)


class ProrrataRegisterEntry(BaseModel):
    """One ``(ejercicio, sector)`` entry in the cross-period prorrata register.

    Strict, frozen, no extra fields. Carries the regime in force, the provisional
    percentage with its regulated provenance (and, for the referenced
    provenances, its authorisation/proposal reference), and — populated only at
    settlement — the definitive percentage with the annual volume inputs it
    derived from. The provisional, referenced, and settlement field groups each
    travel together (present or absent as a unit), enforced by
    :meth:`_validate_field_coupling`.

    Attributes:
        ejercicio: Filing year the entry covers.
        regime: :class:`~core.ProrrataRegisterRegime` in force for the ejercicio.
        sector_id: Sector identifier for a sectores-diferenciados register, or
            ``None`` for the whole-entity register. Present from birth so
            sectores land without migration; the per-sector compute is deferred.
        provisional_percentage: The provisional deduction percentage (0-100) in
            force during the year's liquidations (art. 104.Uno + 105.Uno), or
            ``None`` when no percentage has resolved yet (never a fabricated
            default).
        provisional_provenance: The :class:`~core.ProrrataProvisionalProvenance`
            the provisional percentage came from. Present iff
            ``provisional_percentage`` is present.
        authorisation_reference: The AEAT authorisation (art. 105.Dos) or
            inicio-de-actividades proposal (art. 105.Tres) reference. Required iff
            ``provisional_provenance`` is a referenced provenance; forbidden
            otherwise.
        definitive_percentage: The definitive deduction percentage (0-100)
            computed at settlement from the annual volumes (art. 105.Cuatro), or
            ``None`` before settlement.
        definitive_volume_con_derecho: The annual con-derecho operations volume
            the definitive percentage derived from. Present iff
            ``definitive_percentage`` is present.
        definitive_volume_sin_derecho: The annual sin-derecho operations volume
            the definitive percentage derived from. Present iff
            ``definitive_percentage`` is present.
        source_observation_ref: The prior settlement observation identity a
            ``carried_prior_definitiva`` entry was seeded from, so the register
            stays cross-checkable against the prior filing. Permitted only for the
            carried provenance.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    ejercicio: int = Field(ge=_MIN_EJERCICIO, le=_MAX_EJERCICIO)
    regime: ProrrataRegisterRegime
    sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    provisional_percentage: Decimal | None = Field(default=None, ge=Decimal("0"), le=_HUNDRED)
    provisional_provenance: ProrrataProvisionalProvenance | None = None
    authorisation_reference: str | None = Field(default=None, min_length=1)
    definitive_percentage: Decimal | None = Field(default=None, ge=Decimal("0"), le=_HUNDRED)
    definitive_volume_con_derecho: Decimal | None = Field(default=None, ge=Decimal("0"))
    definitive_volume_sin_derecho: Decimal | None = Field(default=None, ge=Decimal("0"))
    source_observation_ref: str | None = Field(default=None, min_length=1)
    schema_version: str = PRORRATA_REGISTER_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than :data:`PRORRATA_REGISTER_SCHEMA_VERSION`."""
        if value != PRORRATA_REGISTER_SCHEMA_VERSION:
            raise ProrrataRegisterValidationError(f"unsupported ProrrataRegisterEntry schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_field_coupling(self) -> ProrrataRegisterEntry:
        """Enforce that the provisional, referenced, and settlement field groups are coherent."""
        if (self.provisional_percentage is None) != (self.provisional_provenance is None):
            raise ProrrataRegisterValidationError(
                "provisional_percentage and provisional_provenance must be present or absent together"
            )
        referenced = self.provisional_provenance in _REFERENCED_PROVENANCES
        if referenced and self.authorisation_reference is None:
            raise ProrrataRegisterValidationError(
                f"provenance {self.provisional_provenance} requires an authorisation_reference"
            )
        if not referenced and self.authorisation_reference is not None:
            raise ProrrataRegisterValidationError(
                "authorisation_reference is permitted only for an AEAT-authorised or inicio-actividad provenance"
            )
        settlement_fields = (
            self.definitive_percentage,
            self.definitive_volume_con_derecho,
            self.definitive_volume_sin_derecho,
        )
        present = [field is not None for field in settlement_fields]
        if any(present) and not all(present):
            raise ProrrataRegisterValidationError(
                "definitive_percentage and both definitive volume inputs must be present or absent together"
            )
        if (
            self.source_observation_ref is not None
            and self.provisional_provenance is not ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
        ):
            raise ProrrataRegisterValidationError(
                "source_observation_ref is permitted only for a carried_prior_definitiva entry"
            )
        return self


class ProrrataProvisionalResolution(BaseModel):
    """Outcome of the precedence-ladder resolution of the in-force provisional percentage.

    Attributes:
        percentage: The in-force provisional deduction percentage (0-100), or
            ``None`` when the ladder resolved no value (the visible unresolved
            state — the caller surfaces an advisory, never a silent default).
        provenance: The winning :class:`~core.ProrrataProvisionalProvenance`, or
            ``None`` when unresolved.
    """

    model_config = _STRICT_FROZEN_CONFIG

    percentage: Decimal | None
    provenance: ProrrataProvisionalProvenance | None

    @property
    def resolved(self) -> bool:
        """Whether the ladder resolved a percentage."""
        return self.percentage is not None


def resolve_provisional_percentage(
    candidates: Iterable[ProrrataRegisterEntry],
) -> ProrrataProvisionalResolution:
    """Resolve the in-force provisional percentage among candidate entries by the LIVA art. 105 ladder.

    Applies the single declared precedence ladder (:data:`_PROVENANCE_PRECEDENCE`):
    an AEAT-authorised (art. 105.Dos) or inicio-de-actividades (art. 105.Tres)
    provisional percentage outranks the carried prior definitive (art. 105.Uno).
    Only candidates that actually carry a provisional percentage participate; a
    candidate recording a regime but no percentage does not contribute a value.
    When no candidate carries a percentage the result is the visible unresolved
    state (both fields ``None``) — never a fabricated default.

    Args:
        candidates: Register entries to resolve among. In the normal register
            this is the (at most one) entry for a ``(ejercicio, sector)`` key; the
            seeding/override recording path supplies several provenance candidates.

    Returns:
        A :class:`ProrrataProvisionalResolution` naming the winning percentage and
        provenance, or both ``None`` when unresolved.
    """
    winner: ProrrataRegisterEntry | None = None
    winning_rank: int | None = None
    for entry in candidates:
        if entry.provisional_percentage is None or entry.provisional_provenance is None:
            continue
        rank = _PROVENANCE_PRECEDENCE.index(entry.provisional_provenance)
        if winning_rank is None or rank < winning_rank:
            winner = entry
            winning_rank = rank
    if winner is None:
        return ProrrataProvisionalResolution(percentage=None, provenance=None)
    return ProrrataProvisionalResolution(
        percentage=winner.provisional_percentage,
        provenance=winner.provisional_provenance,
    )


class ProrrataRegister(BaseModel):
    """Encrypted JSON document holding the per-ejercicio prorrata register.

    Holds one :class:`ProrrataRegisterEntry` per ``(ejercicio, sector_id)`` key;
    a duplicate key is rejected at construction. The regime and sector axes are
    present from birth so prorrata especial and sectores diferenciados land
    without a schema migration (no-legacy-compatibility).

    Attributes:
        schema_version: Forward-compatible schema version. ``"1"``.
        entries: Tuple of :class:`ProrrataRegisterEntry` rows.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = PRORRATA_REGISTER_SCHEMA_VERSION
    entries: tuple[ProrrataRegisterEntry, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than :data:`PRORRATA_REGISTER_SCHEMA_VERSION`."""
        if value != PRORRATA_REGISTER_SCHEMA_VERSION:
            raise ProrrataRegisterValidationError(f"unsupported ProrrataRegister schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _keys_unique(self) -> ProrrataRegister:
        """Reject a register that carries two entries for the same (ejercicio, sector_id)."""
        seen = [(entry.ejercicio, entry.sector_id) for entry in self.entries]
        if len(seen) != len(set(seen)):
            raise ProrrataRegisterValidationError("register carries duplicate (ejercicio, sector) entries")
        return self

    def entries_for_ejercicio(self, ejercicio: int) -> tuple[ProrrataRegisterEntry, ...]:
        """Return every entry recorded for ``ejercicio`` across all sectors."""
        return tuple(entry for entry in self.entries if entry.ejercicio == ejercicio)

    def entry_for(self, ejercicio: int, *, sector_id: str | None = None) -> ProrrataRegisterEntry | None:
        """Return the entry for a ``(ejercicio, sector_id)`` key, or ``None`` when absent."""
        for entry in self.entries:
            if entry.ejercicio == ejercicio and entry.sector_id == sector_id:
                return entry
        return None

    def resolve_provisional(self, ejercicio: int, *, sector_id: str | None = None) -> ProrrataProvisionalResolution:
        """Resolve the in-force provisional percentage for a ``(ejercicio, sector_id)`` key.

        Filters the register to the key's entry and applies
        :func:`resolve_provisional_percentage`, returning the visible unresolved
        state when no percentage is recorded.
        """
        entry = self.entry_for(ejercicio, sector_id=sector_id)
        return resolve_provisional_percentage(() if entry is None else (entry,))


__all__ = [
    "PRORRATA_REGISTER_SCHEMA_VERSION",
    "ProrrataProvisionalResolution",
    "ProrrataRegister",
    "ProrrataRegisterEntry",
    "ProrrataRegisterError",
    "ProrrataRegisterValidationError",
    "resolve_provisional_percentage",
]
