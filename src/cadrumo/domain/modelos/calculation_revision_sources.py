"""Persisted calculation source provenance and unresolved source conditions."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import ModeloValidationError


class CalculationSourceRef(BaseModel):
    """One resolver-level source-object trace persisted on a calculation revision.

    The calculation source mesh (``cadrumo.application.aggregation``) resolves each
    registry binding source through an enrolled resolver and produces a typed
    ``CalculationSourceProvenance`` row per contributing source object. This is
    the DOMAIN-side, persistence-shaped projection of that provenance: it carries
    exactly the resolverâ†’source-objectâ†’fingerprint trace that lets an audit reader
    reconstruct which resolver mesh and which upstream source objects produced a
    revision, and whether those objects have since drifted.

    It deliberately does NOT carry ``legal_refs`` / ``source_refs`` â€” those are the
    per-casilla regulatory grounding already carried by
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` on the same
    revision; duplicating them here would fragment the grounding across two
    surfaces.

    ``source_casilla_ids`` is NOT grounding and the rationale above does
    not extend to it. It is a subject IDENTITY -- which casilla(s), if any,
    this source object's resolution feeds -- and nothing else on the revision
    carries it for the general (non-row-materialized) case; dropping it here
    was an omission the application-side
    :class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceProvenance` did
    not itself make (it already carries the field). An empty tuple is honest
    when the originating resolver call site did not associate this row with a
    casilla â€” it is not fabricated as a claim of "no subject", only carried as
    "not linked at resolution time".

    Attributes:
        resolver_id: Exact canonical resolver identity that produced this row.
        resolved_binding_source: Canonical binding source owned by the resolver.
        contributor_source_kind: Upstream taxonomy token for this source node.
        contributor_binding_source: Canonical :class:`BindingSourceKind` when
            ``contributor_source_kind`` belongs to the binding taxonomy; ``None``
            for an external or non-binding contributor.
        lineage_role: Whether this row is the resolver-owned primary or supporting contributor.
        source_ref: Stable reference to the contributing source object
            (e.g. ``collectible_invoice:{invoice_id}``).
        fingerprint: Data-dependent digest of the contributing source object when
            the resolver produced one; ``None`` when the resolver emits a
            reference without a content digest.
        source_casilla_ids: Casilla identities this source object's resolution
            feeds, when the originating resolver associated one; empty when it
            did not. Carried straight from
    :attr:`~cadrumo.application.aggregation.source_mesh.CalculationSourceProvenance.source_casilla_ids`.
        dependency_treatment: The registry's declared dependency treatment for
            this carry, empty when the revision declares none. Unlike
            ``legal_refs`` / ``source_refs`` this carries no grounding duplicated
            elsewhere on the revision â€” it is the sole persisted trace of whether
            a carry is a ``factual_evidence`` fact to reconcile against or a
            ``direct_annual_settlement`` figure that settles the return, and an
            audit reader has no other way to recover that distinction after the
            fact. Carried here rather than gated here: the value is NOT withheld
            on the basis of its treatment.
        source_filing_year: The filing year of the source this node rests on,
            when the resolver recorded one: the source modelo's year for a
            relation carry, and the accrual year for a Modelo 193 disclosure
            phase row, which tells a pending row from a settled prior-accrual
            one. ``None`` means the year is unknown, including on every revision
            persisted before the field existed; it never means "the current
            year". It joins the revision identity only when present, so those
            revisions keep their content-addressed ids.
    """

    model_config = STRICT_FROZEN_CONFIG

    resolver_id: str = Field(min_length=1, max_length=128)
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str = Field(min_length=1, max_length=64)
    contributor_binding_source: BindingSourceKind | None
    lineage_role: CalculationSourceLineageRole
    source_ref: str = Field(min_length=1, max_length=256)
    parent_source_ref: str | None = Field(min_length=1, max_length=256)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=256)
    source_casilla_ids: tuple[CasillaId, ...] = ()
    dependency_treatment: str = ""
    source_filing_year: FilingYear | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_coherent_lineage(self) -> CalculationSourceRef:
        try:
            contributor_kind = BindingSourceKind(self.contributor_source_kind)
        except ValueError:
            contributor_kind = None
        if self.contributor_binding_source is None:
            if contributor_kind is not None:
                raise ModeloValidationError(
                    "source provenance contributor_binding_source is required when contributor_source_kind "
                    "is a binding source kind",
                )
        elif contributor_kind is not self.contributor_binding_source:
            raise ModeloValidationError(
                "source provenance contributor_binding_source must equal contributor_source_kind",
            )
        if self.lineage_role is CalculationSourceLineageRole.PRIMARY:
            if self.parent_source_ref is not None:
                raise ModeloValidationError("primary source provenance cannot have a parent")
        elif self.parent_source_ref is None:
            raise ModeloValidationError("contributor source provenance requires a parent")
        return self


CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT: Final[int] = 512
"""A durable issue's technical account stops here, so a long one cannot fail the calculation it describes."""


class CalculationNoteSentence(StrEnum):
    """The catalogue sentence that states one note's facts."""

    CLAIM_GAP_ACCRUED = "claim_gap_accrued"
    CLAIM_GAP_FREE_METHOD = "claim_gap_free_method"
    INSTALMENT_FREE_GAP = "instalment_free_gap"
    ACCRUAL_UNAVAILABLE = "accrual_unavailable"
    AMORTIZATION_BOX_UNBOUND = "amortization_box_unbound"
    ACTIVITY_UNDECLARED = "activity_undeclared"
    AGRARIAN_EXCLUDED = "agrarian_excluded"
    RESIDENCE_PERIOD_UNKNOWN = "residence_period_unknown"
    ROW_UNREGISTERED = "row_unregistered"
    REGISTER_OWNED_ACQUISITION = "register_owned_acquisition"
    POSSIBLY_DURABLE_EXPENSE = "possibly_durable_expense"
    REGISTER_ROW_MISSING = "register_row_missing"
    REGISTER_COST_EXCEEDS_PAID = "register_cost_exceeds_paid"
    REGISTER_PRICE_EXCEEDS_BASE = "register_price_exceeds_base"
    REGISTER_PARTLY_ACCOUNTED = "register_partly_accounted"
    DISPOSAL_UNRESOLVED_INCOME = "disposal_unresolved_income"
    DISPOSAL_UNRESOLVED_NO_BOX = "disposal_unresolved_no_box"
    DISPOSAL_INSTALMENT_EXCESS_UNRESOLVED = "disposal_instalment_excess_unresolved"
    DISPOSAL_INSTALMENT_AGRARIAN_EXCESS = "disposal_instalment_agrarian_excess"
    DISPOSAL_MODULES_AGRARIAN_EXCESS = "disposal_modules_agrarian_excess"
    DISPOSAL_M131_EXCESS = "disposal_m131_excess"
    DISPOSAL_M131_EXCESS_UNRESOLVED = "disposal_m131_excess_unresolved"
    DISPOSAL_LATER_AFFECTATION = "disposal_later_affectation"
    DISPOSAL_FIGURE_NO_BOX = "disposal_figure_no_box"
    DISPOSAL_FIGURE_IN_BOX = "disposal_figure_in_box"
    DISPOSAL_FIGURE_ELEMENT_ROW = "disposal_figure_element_row"
    DISPOSAL_FIGURE_PROPERTY_ROW = "disposal_figure_property_row"
    DISPOSAL_SHARED_ROW = "disposal_shared_row"
    DISPOSAL_CLAIM_GAP = "disposal_claim_gap"
    DISPOSAL_MINIMUM_EXCEEDED_DEDUCTION = "disposal_minimum_exceeded_deduction"
    DISPOSAL_NO_MINIMUM_AUTHORITY = "disposal_no_minimum_authority"
    DISPOSAL_MINIMUM_UNRESOLVED = "disposal_minimum_unresolved"
    DISPOSAL_EXEMPTION_NOT_COMPUTED = "disposal_exemption_not_computed"


class CalculationNoteFact(BaseModel):
    """What one note says about its own subject: a catalogue sentence and the values it names.

    A note's reason says what kind of thing was noticed, and several notes can share
    a reason. This says which row, element, interval and amount this one is about, so
    what was known at calculation stays readable in every language after the process
    that calculated it has gone. Values are text the sentence prints as they stand.
    """

    model_config = STRICT_FROZEN_CONFIG

    sentence: CalculationNoteSentence
    values: tuple[tuple[str, str], ...] = ()

    @classmethod
    def of(cls, sentence: CalculationNoteSentence, /, **values: object) -> Self:
        """Build the fact from named values, in a stable order."""
        return cls(sentence=sentence, values=tuple(sorted((name, str(value)) for name, value in values.items())))

    def identity(self) -> tuple[str, ...]:
        """Flatten the fact for a revision's content identity and for telling two notes apart."""
        return (self.sentence.value, *(part for pair in self.values for part in pair))


class RecordedCalculationNote(BaseModel):
    """A note kept with a calculation, as verification and export restate it."""

    model_config = STRICT_FROZEN_CONFIG

    reason: str = Field(min_length=1, max_length=64)
    fact: CalculationNoteFact


class CalculationSourceIssue(BaseModel):
    """One durable unresolved source condition found while calculating a revision.

    Resolver diagnostics are useful calculate-time operator feedback, but a
    filing-grade verification runs later against the persisted calculation
    revision.  This narrow envelope carries a source condition that reached no
    binding, without misrepresenting it as source provenance for a computed
    output.

    Every reason below must survive to the persisted revision, because each
    describes a condition the filing cannot treat as complete.
    ``unrouted_observation`` is a row no binding consumes at all.
    ``unrouted_declarable_quantity`` is an independent quantity that consumed
    rows carry and no binding drawing that quantity reaches â€” the row-keyed
    screens are silent on it by construction, so a verify or export gate that
    saw only the row condition would read their silence as confirmation.
    ``iva_selected_scope_evidence_failure`` is a ledger IVA row whose selected
    filing scope cannot be completed from its recorded tax evidence.
    ``iva_compensation_annual_source_evidence_failure`` is a required Modelo
    390 annual partition whose filed Modelo 303 source set is incomplete or
    stale. ``withholding_detail_absent`` is an annual withholding summary whose
    per-perceptor-clave detail store held no observation for the year, so its
    percepciones count rests on a zero the store cannot support. A contradictory
    source is refused during calculation before a revision can be persisted.

    The remaining reasons each mean a filed figure is missing or cannot be
    trusted. ``unresolved_binding`` is a box printed on the form whose declared
    source produced no value, named by ``casilla_id``, which must never read as
    a zero. ``unhandled_binding_source`` is a declared source with no
    executable route. ``source_domain_not_ready`` is a source store that could
    not be read yet. ``invoice_reverse_charge_cuota_not_derivable`` is a
    reverse-charge invoice whose IVA owed could not be derived.
    These block filing until a recalculation clears them.
    ``terminal_origin_mismatch`` is a value that reached the declaration by an
    undeclared route; it persists so a reopened declaration still shows it, but
    withholds nothing, because the route it reports may lack a terminal origin by
    design. ``ledger_amortization_row_unregistered`` is a ledger row in an
    amortization category no registered element owns.
    ``activity_asset_foral_territory`` is a period in a foral territory, whose
    amortization is determined under foral rules.
    ``activity_asset_residence_unresolved`` is a tax residence that could not be
    read while the register holds elements. These three persist in the same way:
    the amortization is left out and the rest of the declaration stands.
    The other activity-asset reasons persist as durable notes for the same cause:
    what was known about the register at calculation stays with the filed record.
    None of them withholds anything. ``fact`` states such a note's own row, element,
    interval and amount. ``binding_source`` is ``None`` only where the condition
    names no binding source kind.
    """

    model_config = STRICT_FROZEN_CONFIG

    reason: Literal[
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
        "unresolved_binding",
        "terminal_origin_mismatch",
        "unhandled_binding_source",
        "source_domain_not_ready",
        "invoice_reverse_charge_cuota_not_derivable",
        "ledger_amortization_row_unregistered",
        "activity_asset_foral_territory",
        "activity_asset_residence_unresolved",
        "activity_asset_claim_gap",
        "activity_asset_accrual_unavailable",
        "activity_asset_activity_undeclared",
        "activity_asset_agrarian_excluded",
        "activity_asset_residence_period_unknown",
        "activity_asset_disposal_finding",
        "register_acquisition_exceeds_ledger",
        "register_acquisition_partly_accounted",
        "register_acquisition_row_missing",
        "register_owned_capital_acquisition",
        "ledger_expense_may_be_durable",
    ]
    binding_source: BindingSourceKind | None
    message: str = Field(min_length=1, max_length=CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)
    casilla_id: CasillaId | None = None
    fact: CalculationNoteFact | None = None


ACTIVITY_ASSET_CLAIM_REF_PREFIX: Final = "activity-asset-claim:"
"""Prefix of the source reference naming one effective amortization claim."""

ACTIVITY_ASSET_SCHEDULE_REF_PREFIX: Final = "activity-asset-schedule:"
"""Prefix of the source reference naming one element schedule by its fingerprint."""


ACTIVITY_ASSET_DISPOSAL_REF_PREFIX: Final = "activity-asset-disposal:"
"""Prefix of the source reference naming one baja by the revision that records it."""

ACTIVITY_ASSET_DISPOSAL_FIGURES_REF_PREFIX: Final = "activity-asset-disposal-figures:"
"""Prefix of the source reference naming what one baja's figures rested on and came to, by digest."""


class ActivityAssetConsumption(BaseModel):
    """The activity-asset register state one calculation rested on.

    Claim identity hashes the claim's content, so a claim cannot name the
    calculation that consumed it. The calculation records the claims and
    schedules instead, and any difference between that record and what the
    register yields now means the calculation no longer reflects the register.

    Attributes:
        claim_ids: Sorted identities of the effective claims consumed.
        schedule_fingerprints: Sorted fingerprints of the element schedules
            consumed where no claim stood behind the amount (Modelo 130 accrual).
        disposal_revision_ids: Sorted identities of the revisions recording a baja
            the calculation's period reaches, so a late baja reads as drift even
            where it changed no claim.
        disposal_digests: Sorted digests of those bajas' inputs and results, so a
            claim of an earlier year that moves a baja's figures reads as drift even
            where the revision and the year's claims stand as they were.
    """

    model_config = STRICT_FROZEN_CONFIG

    claim_ids: tuple[str, ...] = ()
    schedule_fingerprints: tuple[str, ...] = ()
    disposal_revision_ids: tuple[str, ...] = ()
    disposal_digests: tuple[str, ...] = ()

    @classmethod
    def from_source_refs(cls, source_refs: Iterable[str]) -> ActivityAssetConsumption:
        """Read the consumption out of source references, ignoring every other kind."""
        claims: set[str] = set()
        schedules: set[str] = set()
        disposals: set[str] = set()
        digests: set[str] = set()
        for source_ref in source_refs:
            if source_ref.startswith(ACTIVITY_ASSET_CLAIM_REF_PREFIX):
                claims.add(source_ref.removeprefix(ACTIVITY_ASSET_CLAIM_REF_PREFIX))
            elif source_ref.startswith(ACTIVITY_ASSET_SCHEDULE_REF_PREFIX):
                schedules.add(source_ref.removeprefix(ACTIVITY_ASSET_SCHEDULE_REF_PREFIX))
            elif source_ref.startswith(ACTIVITY_ASSET_DISPOSAL_REF_PREFIX):
                disposals.add(source_ref.removeprefix(ACTIVITY_ASSET_DISPOSAL_REF_PREFIX))
            elif source_ref.startswith(ACTIVITY_ASSET_DISPOSAL_FIGURES_REF_PREFIX):
                digests.add(source_ref.removeprefix(ACTIVITY_ASSET_DISPOSAL_FIGURES_REF_PREFIX))
        return cls(
            claim_ids=tuple(sorted(claims)),
            schedule_fingerprints=tuple(sorted(schedules)),
            disposal_revision_ids=tuple(sorted(disposals)),
            disposal_digests=tuple(sorted(digests)),
        )

    @property
    def is_empty(self) -> bool:
        """Whether the calculation rested on no register state."""
        return (
            not self.claim_ids
            and not self.schedule_fingerprints
            and not self.disposal_revision_ids
            and not self.disposal_digests
        )

    def disposals_changed_from(self, other: ActivityAssetConsumption) -> int:
        """How many bajas differ from ``other``: recorded or dropped, or standing with other figures."""
        ours, theirs = set(self.disposal_digests), set(other.disposal_digests)
        return max(
            len(set(self.disposal_revision_ids) ^ set(other.disposal_revision_ids)),
            len(ours - theirs),
            len(theirs - ours),
        )


def validate_revision_source_provenance(rows: Sequence[CalculationSourceRef]) -> None:
    """Require unique primary identities and a declared primary parent for each contributor."""
    primary_refs = tuple(row.source_ref for row in rows if row.lineage_role is CalculationSourceLineageRole.PRIMARY)
    if len(primary_refs) != len(set(primary_refs)):
        raise ModeloValidationError("source provenance primary reference is ambiguous")
    primary_ref_set = frozenset(primary_refs)
    if any(
        row.parent_source_ref not in primary_ref_set
        for row in rows
        if row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
    ):
        raise ModeloValidationError("source provenance contributor parent does not resolve to a primary")


def recorded_calculation_notes(issues: Iterable[CalculationSourceIssue]) -> tuple[RecordedCalculationNote, ...]:
    """The notes a calculation kept that state their own facts, once each and in the order they were raised."""
    return tuple(
        dict.fromkeys(
            RecordedCalculationNote(reason=issue.reason, fact=issue.fact) for issue in issues if issue.fact is not None
        )
    )
