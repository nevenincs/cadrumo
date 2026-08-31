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

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ...core.prorrata_register import ProrrataActivityRowType as _ProrrataActivityRowType
from ...core.prorrata_register import ProrrataEspecialTransitionKind as _ProrrataEspecialTransitionKind
from ...core.prorrata_register import ProrrataProvisionalProvenance as _ProrrataProvisionalProvenance
from ...core.prorrata_register import ProrrataRegisterRegime as _ProrrataRegisterRegime
from ...core.prorrata_register import SectorDiferenciadoLetra as _SectorDiferenciadoLetra
from ...core.errors.hierarchy import CadrumoError as _CadrumoError
from ...core.filing_year import FilingYear
from ._protocols import ProrrataRegisterRepositoryProtocol


class ProrrataRegisterError(_CadrumoError):
    """Raised when a prorrata-register record is structurally invalid."""


class ProrrataRegisterValidationError(ProrrataRegisterError, ValueError):
    """Raised when a prorrata-register model fails Pydantic validation."""


PRORRATA_REGISTER_SCHEMA_VERSION = "2"
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
        _ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        _ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
    }
)

#: Single declared precedence ladder (LIVA art. 105): the AEAT-authorised
#: provisional (105.Dos) and the inicio-de-actividades proposal (105.Tres)
#: outrank the carried prior definitive (105.Uno). An explicit AEAT
#: authorisation outranks a self-proposed inicio percentage as a deterministic
#: tie-break; the two are mutually exclusive in practice. Lower index = higher
#: precedence.
_PROVENANCE_PRECEDENCE: tuple[_ProrrataProvisionalProvenance, ...] = (
    _ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
    _ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
    _ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
    _ProrrataProvisionalProvenance.INTERRUMPIDA_TRES_ULTIMOS,
)


class ProrrataEspecialTransitionEvidence(BaseModel):
    """Evidence for one Modelo 303 prorrata-especial transition.

    The voluntary special-prorrata choice and its revocation are filing facts,
    not inferred descriptions of a register regime.  A single discriminated
    transition keeps their mutual exclusion structural while its reference
    retains the operator evidence that supports the filing projection.

    The enclosing :class:`ProrrataRegisterEntry` owns the ejercicio and sector,
    so this child deliberately carries only the closed legal transition and its
    durable operator-held reference.
    """

    model_config = _STRICT_FROZEN_CONFIG

    kind: _ProrrataEspecialTransitionKind
    evidence_reference: str = Field(min_length=1, max_length=256)

    @field_validator("evidence_reference")
    @classmethod
    def _evidence_reference_is_not_blank(cls, value: str) -> str:
        """Refuse whitespace-only evidence before it reaches encrypted storage."""
        if not value.strip():
            raise ProrrataRegisterValidationError("prorrata especial transition evidence_reference must not be blank")
        return value


class SectorDefinition(BaseModel):
    """One operator-declared differentiated sector (LIVA arts. 9.1.c / 101).

    Strict, frozen, no extra fields. The art. 9.1.c partition of a taxpayer's
    activities into differentiated sectors is a legal judgment the ledger cannot
    infer (which CNAE groups are run, whether their prorrata percentages diverge
    by more than 50 percentage points, whether a special-regime activity is
    present), so it is operator-declared: each sector carries a stable
    ``sector_id`` (the key the register entries and the ledger rows reference),
    the member activity codes it groups, and the :class:`~core.SectorDiferenciadoLetra`
    that makes it differentiated. Fail-closed: a register with no sector
    definitions is a whole-entity register (``sector_id = None`` throughout), the
    landed cross-period behaviour, never a silently inferred partition.

    Attributes:
        sector_id: Stable identifier the register entries and ledger rows
            reference. Must match the ``sector_id`` on the per-sector
            :class:`ProrrataRegisterEntry` rows.
        letra: The :class:`~core.SectorDiferenciadoLetra` (art. 9.1.c letra
            a'/b'/c'/d') on which this sector is differentiated.
        member_activity_codes: The CNAE / IAE-epígrafe activity codes grouped
            into this sector. Non-empty: a declared sector groups at least one
            activity. Recorded for provenance and operator audit; the per-sector
            routing keys on ``sector_id``, never on these codes.
    """

    model_config = _STRICT_FROZEN_CONFIG

    sector_id: str = Field(min_length=1, max_length=64)
    letra: _SectorDiferenciadoLetra
    member_activity_codes: tuple[str, ...] = Field(min_length=1)

    @field_validator("member_activity_codes")
    @classmethod
    def _member_codes_non_empty_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject a blank member activity code — every grouped code is a real token."""
        for code in value:
            if not code.strip():
                raise ProrrataRegisterValidationError("member_activity_codes must not contain a blank code")
        return value


class ProrrataActivityRow(BaseModel):
    """One canonical Modelo 303 per-activity prorrata filing row.

    The five official DP30305 rows are taxpayer facts, not copies of the
    register's global percentage or five families of numbered scalar inputs.
    ``activity_id`` gives a durable operator identity while ``slot`` records
    the reviewed fixed-row projection (1 through 5).  The registry owns the
    revision-specific boxes and byte geometry; this child owns only the typed
    row facts and their evidence reference.
    """

    model_config = _STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    activity_id: str = Field(min_length=1, max_length=128)
    slot: int = Field(ge=1, le=5)
    cnae_code: str = Field(min_length=3, max_length=4, pattern=r"^\d{3,4}$")
    operaciones_total: Decimal = Field(ge=Decimal("0"))
    operaciones_con_derecho: Decimal = Field(ge=Decimal("0"))
    prorrata_type: _ProrrataActivityRowType
    percentage: Decimal = Field(ge=Decimal("0"), le=_HUNDRED)
    evidence_reference: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def _deductible_operations_do_not_exceed_total(self) -> ProrrataActivityRow:
        """Reject a row whose declared right-bearing volume exceeds its total."""
        if self.operaciones_con_derecho > self.operaciones_total:
            raise ProrrataRegisterValidationError(
                "operaciones_con_derecho must not exceed operaciones_total for an activity row",
            )
        return self


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
        especial_transition: The :class:`ProrrataEspecialTransitionEvidence` for
            an art. 103.Dos option or its revocation evidenced *in this*
            ejercicio, or ``None`` when the regime merely continues. Required
            rather than defaulted: a regime is durable state, so an absent
            transition must be an explicit declaration and never an omission.
        sector_id: Sector identifier for a sectores-diferenciados register, or
            ``None`` for the whole-entity register. Present from birth so
            sectores land without migration; the per-sector compute is deferred.
        interrupted: The art. 105.Cinco "sin operaciones" marker — ``True`` when
            the taxpayer (or the differentiated sector) performed no operations
            during the ejercicio. Distinct from the ``ninguna`` regime (an
            *active* year under no prorrata): an interrupted year is *inactive*.
            An interrupted entry carries no provisional or definitive percentage
            and no volume inputs; the three-active-years seed walk skips it. The
            register thereby retains a truthful active/inactive history.
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
        schema_version: Forward-compatible schema version. ``"2"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    regime: _ProrrataRegisterRegime
    especial_transition: ProrrataEspecialTransitionEvidence | None
    sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    interrupted: bool = False
    provisional_percentage: Decimal | None = Field(default=None, ge=Decimal("0"), le=_HUNDRED)
    provisional_provenance: _ProrrataProvisionalProvenance | None = None
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
        _validate_interrupted_entry_fields(self)
        _validate_provisional_field_coupling(self)
        _validate_settlement_field_coupling(self)
        _validate_source_observation_provenance(self)
        _validate_especial_transition_regime(self)
        return self


def _validate_interrupted_entry_fields(entry: ProrrataRegisterEntry) -> None:
    """Keep an interrupted exercise free from every active-operation field."""
    fields = (
        entry.provisional_percentage,
        entry.provisional_provenance,
        entry.authorisation_reference,
        entry.definitive_percentage,
        entry.definitive_volume_con_derecho,
        entry.definitive_volume_sin_derecho,
        entry.source_observation_ref,
    )
    if entry.interrupted and any(field is not None for field in fields):
        raise ProrrataRegisterValidationError(
            "an interrupted (sin operaciones) ejercicio carries no provisional/definitive percentage, "
            "volume inputs, authorisation, or source-observation reference"
        )


def _validate_provisional_field_coupling(entry: ProrrataRegisterEntry) -> None:
    """Validate the provisional percentage, provenance, and referenced-authorisation group."""
    if (entry.provisional_percentage is None) != (entry.provisional_provenance is None):
        raise ProrrataRegisterValidationError(
            "provisional_percentage and provisional_provenance must be present or absent together"
        )
    referenced = entry.provisional_provenance in _REFERENCED_PROVENANCES
    if referenced and entry.authorisation_reference is None:
        raise ProrrataRegisterValidationError(
            f"provenance {entry.provisional_provenance} requires an authorisation_reference"
        )
    if not referenced and entry.authorisation_reference is not None:
        raise ProrrataRegisterValidationError(
            "authorisation_reference is permitted only for an AEAT-authorised or inicio-actividad provenance"
        )


def _validate_settlement_field_coupling(entry: ProrrataRegisterEntry) -> None:
    """Require definitive percentage and both annual volume inputs as one group."""
    settlement_fields = (
        entry.definitive_percentage,
        entry.definitive_volume_con_derecho,
        entry.definitive_volume_sin_derecho,
    )
    present = [field is not None for field in settlement_fields]
    if any(present) and not all(present):
        raise ProrrataRegisterValidationError(
            "definitive_percentage and both definitive volume inputs must be present or absent together"
        )


def _validate_source_observation_provenance(entry: ProrrataRegisterEntry) -> None:
    """Restrict source observations to the carried-prior-definitive lifecycle."""
    if (
        entry.source_observation_ref is not None
        and entry.provisional_provenance is not _ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    ):
        raise ProrrataRegisterValidationError(
            "source_observation_ref is permitted only for a carried_prior_definitiva entry"
        )


def _validate_especial_transition_regime(entry: ProrrataRegisterEntry) -> None:
    """Require the regime declared by a typed especial option or revocation."""
    transition = entry.especial_transition
    if transition is None:
        return
    required_regime = (
        _ProrrataRegisterRegime.ESPECIAL
        if transition.kind is _ProrrataEspecialTransitionKind.OPCION
        else _ProrrataRegisterRegime.GENERAL
    )
    if entry.regime is not required_regime:
        verb = "option" if transition.kind is _ProrrataEspecialTransitionKind.OPCION else "revocation"
        raise ProrrataRegisterValidationError(
            f"prorrata especial {verb} requires current {required_regime.value} regime"
        )


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
    provenance: _ProrrataProvisionalProvenance | None

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


class ThreeActiveYearsAggregate(BaseModel):
    """Aggregated volume inputs of the last three ACTIVE años naturales (LIVA art. 105.Cinco).

    The art. 105.Cinco interrupted-activity rule seeds a resumed ejercicio from
    the percentage that "globalmente corresponda al conjunto de los tres últimos
    años naturales en que se hubiesen realizado operaciones": a GLOBAL percentage
    over the AGGREGATE volumes of the last three active years, not the average of
    their three definitive percentages. This carrier holds those summed volumes
    and the contributing ejercicios (newest-first). :attr:`sufficient` is ``True``
    only when a full three active years were found; with fewer, the application
    seed surfaces an advisory rather than assuming a percentage.

    Attributes:
        contributing_ejercicios: The active ejercicios whose volumes were summed,
            newest first (at most three).
        summed_volume_con_derecho: Sum of the contributing years' annual
            con-derecho operation volumes.
        summed_volume_sin_derecho: Sum of the contributing years' annual
            sin-derecho operation volumes.
    """

    model_config = _STRICT_FROZEN_CONFIG

    contributing_ejercicios: tuple[int, ...] = ()
    summed_volume_con_derecho: Decimal = Decimal("0")
    summed_volume_sin_derecho: Decimal = Decimal("0")

    @property
    def sufficient(self) -> bool:
        """Whether a full three active años naturales contributed."""
        return len(self.contributing_ejercicios) == 3


class ProrrataRegister(BaseModel):
    """Encrypted JSON document holding the per-ejercicio prorrata register.

    Holds one :class:`ProrrataRegisterEntry` per ``(ejercicio, sector_id)`` key;
    a duplicate key is rejected at construction. The regime and sector axes are
    present from birth so prorrata especial and sectores diferenciados land
    without a schema migration (no-legacy-compatibility).

    Attributes:
        schema_version: Forward-compatible schema version. ``"2"``.
        entries: Tuple of :class:`ProrrataRegisterEntry` rows.
        sector_definitions: The operator-declared differentiated-sector partition
            (LIVA arts. 9.1.c / 101). Empty for a whole-entity register — the
            fail-closed default; when non-empty every per-sector
            :class:`ProrrataRegisterEntry` ``sector_id`` and every sectored
            ledger row references one of these declared sectors.
        activity_rows: Canonical, evidence-carrying Modelo 303 per-activity
            prorrata rows.  They are keyed by ``(ejercicio, activity_id)`` and
            retain their fixed official row slot without owning any global
            prorrata result.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = PRORRATA_REGISTER_SCHEMA_VERSION
    entries: tuple[ProrrataRegisterEntry, ...] = ()
    sector_definitions: tuple[SectorDefinition, ...] = ()
    activity_rows: tuple[ProrrataActivityRow, ...] = ()

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

    @model_validator(mode="after")
    def _sector_definitions_unique(self) -> ProrrataRegister:
        """Reject a register that declares two sector definitions for the same sector_id."""
        sector_ids = [definition.sector_id for definition in self.sector_definitions]
        if len(sector_ids) != len(set(sector_ids)):
            raise ProrrataRegisterValidationError("register carries duplicate sector_id definitions")
        return self

    @model_validator(mode="after")
    def _activity_row_keys_unique(self) -> ProrrataRegister:
        """Keep each activity identity and fixed row slot unambiguous per year."""
        activity_keys = [(row.ejercicio, row.activity_id) for row in self.activity_rows]
        if len(activity_keys) != len(set(activity_keys)):
            raise ProrrataRegisterValidationError("register carries duplicate (ejercicio, activity_id) activity rows")
        slot_keys = [(row.ejercicio, row.slot) for row in self.activity_rows]
        if len(slot_keys) != len(set(slot_keys)):
            raise ProrrataRegisterValidationError("register carries duplicate (ejercicio, slot) activity rows")
        return self

    @model_validator(mode="after")
    def _transitions_are_continuous_and_unambiguous(self) -> ProrrataRegister:
        """Require transition evidence to agree with its prior same-sector state."""
        kinds_by_ejercicio, references_by_ejercicio = _especial_transition_evidence(self.entries)
        _validate_one_transition_kind_per_ejercicio(kinds_by_ejercicio)
        _validate_one_transition_reference_per_ejercicio(references_by_ejercicio)
        _validate_option_follows_no_prior_especial_state(self)
        _validate_revocation_prior_especial_state(self)
        return self

    @property
    def is_sectorized(self) -> bool:
        """Whether the register declares a differentiated-sector partition.

        Fail-closed: ``False`` (whole-entity) when no sector definition exists,
        so a taxpayer with no declared partition keeps the landed cross-period
        behaviour byte-identical.
        """
        return bool(self.sector_definitions)

    def sector_ids(self) -> tuple[str, ...]:
        """Return the declared sector ids, in declaration order."""
        return tuple(definition.sector_id for definition in self.sector_definitions)

    def sector_definition_for(self, sector_id: str) -> SectorDefinition | None:
        """Return the declared :class:`SectorDefinition` for ``sector_id``, or ``None``."""
        for definition in self.sector_definitions:
            if definition.sector_id == sector_id:
                return definition
        return None

    def entries_for_ejercicio(self, ejercicio: int) -> tuple[ProrrataRegisterEntry, ...]:
        """Return every entry recorded for ``ejercicio`` across all sectors."""
        return tuple(entry for entry in self.entries if entry.ejercicio == ejercicio)

    def has_complete_current_entry_coverage(self, ejercicio: int) -> bool:
        """Whether every declared prorrata scope has an explicit current entry.

        A whole-entity register has exactly one ``None`` sector scope. Once
        sectors are declared, the common whole-entity scope remains required
        alongside every differentiated sector: a filing-wide Modelo 303
        reduction is valid only when the current ejercicio has exactly one
        entry for that complete set. It must not turn an absent declaration
        into ``NO``.
        """
        current_sector_ids = {entry.sector_id for entry in self.entries_for_ejercicio(ejercicio)}
        expected_sector_ids = {None, *self.sector_ids()} if self.is_sectorized else {None}
        return current_sector_ids == expected_sector_ids

    def activity_rows_for_ejercicio(self, ejercicio: int) -> tuple[ProrrataActivityRow, ...]:
        """Return the year's canonical activity rows in official fixed-slot order."""
        rows = (row for row in self.activity_rows if row.ejercicio == ejercicio)
        return tuple(sorted(rows, key=lambda row: row.slot))

    def requires_activity_rows_for(self, ejercicio: int) -> bool:
        """Whether the recorded prorrata regime makes the five rows applicable."""
        return any(
            not entry.interrupted and entry.regime is not _ProrrataRegisterRegime.NINGUNA
            for entry in self.entries_for_ejercicio(ejercicio)
        )

    def activity_rows_complete_for(self, ejercicio: int) -> bool:
        """Whether an applicable year has exactly the five declared official rows."""
        if not self.requires_activity_rows_for(ejercicio):
            return True
        rows = self.activity_rows_for_ejercicio(ejercicio)
        return len(rows) == 5 and {row.slot for row in rows} == {1, 2, 3, 4, 5}

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

    def collect_last_three_active_years(
        self,
        *,
        before_ejercicio: int,
        sector_id: str | None = None,
    ) -> ThreeActiveYearsAggregate:
        """Aggregate the volume inputs of the last three ACTIVE años naturales (LIVA art. 105.Cinco).

        Walks the register backward from ``before_ejercicio`` for the given
        ``sector_id``, SKIPPING interrupted (sin operaciones) years and any year
        that has not settled (no definitive volumes), and sums the con-derecho and
        sin-derecho volume inputs of the last three active años naturales. An
        "active" year is a settled, non-interrupted entry; the walk is over
        *active* years, not calendar years, so the interruption gap is skipped.

        Returns a :class:`ThreeActiveYearsAggregate` whose ``sufficient`` is
        ``True`` only when three active years contributed; the application seed
        turns an insufficient aggregate into a visible advisory rather than
        assuming a percentage.
        """
        active = sorted(
            (
                entry
                for entry in self.entries
                if entry.sector_id == sector_id
                and entry.ejercicio < before_ejercicio
                and not entry.interrupted
                and entry.definitive_percentage is not None
                and entry.definitive_volume_con_derecho is not None
                and entry.definitive_volume_sin_derecho is not None
            ),
            key=lambda entry: entry.ejercicio,
            reverse=True,
        )[:3]
        con_volumes = [
            entry.definitive_volume_con_derecho for entry in active if entry.definitive_volume_con_derecho is not None
        ]
        sin_volumes = [
            entry.definitive_volume_sin_derecho for entry in active if entry.definitive_volume_sin_derecho is not None
        ]
        if len(con_volumes) != len(active) or len(sin_volumes) != len(active):
            raise ProrrataRegisterValidationError("settled prorrata entry is missing definitive volume evidence")
        summed_con = sum(con_volumes, Decimal("0"))
        summed_sin = sum(sin_volumes, Decimal("0"))
        return ThreeActiveYearsAggregate(
            contributing_ejercicios=tuple(entry.ejercicio for entry in active),
            summed_volume_con_derecho=summed_con,
            summed_volume_sin_derecho=summed_sin,
        )


def _especial_transition_evidence(
    entries: tuple[ProrrataRegisterEntry, ...],
) -> tuple[
    dict[int, set[_ProrrataEspecialTransitionKind]],
    dict[int, set[str]],
]:
    """Collect the transition kinds and evidence references declared per exercise."""
    kinds_by_ejercicio: dict[int, set[_ProrrataEspecialTransitionKind]] = {}
    references_by_ejercicio: dict[int, set[str]] = {}
    for entry in entries:
        transition = entry.especial_transition
        if transition is None:
            continue
        kinds_by_ejercicio.setdefault(entry.ejercicio, set()).add(transition.kind)
        references_by_ejercicio.setdefault(entry.ejercicio, set()).add(transition.evidence_reference)
    return kinds_by_ejercicio, references_by_ejercicio


def _validate_one_transition_kind_per_ejercicio(
    kinds_by_ejercicio: dict[int, set[_ProrrataEspecialTransitionKind]],
) -> None:
    """Reject option and revocation evidence asserted for the same exercise."""
    contradictory_ejercicios = tuple(ejercicio for ejercicio, kinds in kinds_by_ejercicio.items() if len(kinds) > 1)
    if contradictory_ejercicios:
        raise ProrrataRegisterValidationError(
            "register carries contradictory prorrata especial option and revocation evidence for "
            f"ejercicio(s) {contradictory_ejercicios}"
        )


def _validate_one_transition_reference_per_ejercicio(
    references_by_ejercicio: dict[int, set[str]],
) -> None:
    """Reject divergent transition-evidence references for one exercise."""
    conflicting_reference_ejercicios = tuple(
        ejercicio for ejercicio, references in references_by_ejercicio.items() if len(references) > 1
    )
    if conflicting_reference_ejercicios:
        raise ProrrataRegisterValidationError(
            "register carries conflicting prorrata especial transition evidence references for "
            f"ejercicio(s) {conflicting_reference_ejercicios}"
        )


def _validate_option_follows_no_prior_especial_state(register: ProrrataRegister) -> None:
    """Reject an option declared over a same-sector especial regime already in force.

    The art. 103.Dos option is an election, not a restatement: once it is in
    force the regime simply continues into the next ejercicio.  Recording a
    fresh option on top of an immediately prior especial year would let durable
    state masquerade as current-period evidence.
    """
    for entry in register.entries:
        transition = entry.especial_transition
        if transition is None or transition.kind is not _ProrrataEspecialTransitionKind.OPCION:
            continue
        prior_entry = register.entry_for(entry.ejercicio - 1, sector_id=entry.sector_id)
        if prior_entry is not None and prior_entry.regime is _ProrrataRegisterRegime.ESPECIAL:
            raise ProrrataRegisterValidationError(
                "prorrata especial option cannot repeat an immediately prior especial regime for "
                f"sector {entry.sector_id!r}"
            )


def _validate_revocation_prior_especial_state(register: ProrrataRegister) -> None:
    """Require every revocation to follow the same sector's prior especial state."""
    for entry in register.entries:
        transition = entry.especial_transition
        if transition is None or transition.kind is not _ProrrataEspecialTransitionKind.REVOCACION:
            continue
        prior_entry = register.entry_for(entry.ejercicio - 1, sector_id=entry.sector_id)
        if prior_entry is None or prior_entry.regime is not _ProrrataRegisterRegime.ESPECIAL:
            raise ProrrataRegisterValidationError(
                "prorrata especial revocation requires a prior-year especial register state for "
                f"sector {entry.sector_id!r}"
            )


__all__ = [
    "PRORRATA_REGISTER_SCHEMA_VERSION",
    "ProrrataActivityRow",
    "ProrrataEspecialTransitionEvidence",
    "ProrrataProvisionalResolution",
    "ProrrataRegister",
    "ProrrataRegisterEntry",
    "ProrrataRegisterError",
    "ProrrataRegisterRepositoryProtocol",
    "ProrrataRegisterValidationError",
    "SectorDefinition",
    "ThreeActiveYearsAggregate",
    "resolve_provisional_percentage",
]
