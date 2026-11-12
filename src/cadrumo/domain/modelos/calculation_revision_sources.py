"""Persisted calculation source provenance and unresolved source conditions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind, BindingValueOutcome, CalculationSourceLineageRole
from ...core.authority_grade import BindingGradeCapReason
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import NoRecoveryOutcome
from .errors import ModeloValidatedRecord, ModeloValidationError
from .source_disagreement import SourceDisagreementFact


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
                    no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                    record=ModeloValidatedRecord.CALCULATION_REVISION,
                )
        elif contributor_kind is not self.contributor_binding_source:
            raise ModeloValidationError(
                "source provenance contributor_binding_source must equal contributor_source_kind",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CALCULATION_REVISION,
            )
        if self.lineage_role is CalculationSourceLineageRole.PRIMARY:
            if self.parent_source_ref is not None:
                raise ModeloValidationError(
                    "primary source provenance cannot have a parent",
                    no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                    record=ModeloValidatedRecord.CALCULATION_REVISION,
                )
        elif self.parent_source_ref is None:
            raise ModeloValidationError(
                "contributor source provenance requires a parent",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CALCULATION_REVISION,
            )
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
    ROW_UNREGISTERED_UNDATED = "row_unregistered_undated"
    REGISTER_OWNED_ACQUISITION = "register_owned_acquisition"
    REGISTER_OWNED_ACQUISITION_UNDATED = "register_owned_acquisition_undated"
    BOOK_CLAIMED_PURCHASE = "book_claimed_purchase"
    BOOK_CLAIMED_PURCHASE_UNDATED = "book_claimed_purchase_undated"
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
    DISPOSAL_ZERO_RESULT = "disposal_zero_result"
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
    ADVISORY_IMPUTATION_PERIOD_UNGROUNDED = "advisory_imputation_period_ungrounded"
    ADVISORY_VALUE_PROVEN_ZERO = "advisory_value_proven_zero"
    RETENCION_SOPORTADA_EVIDENCE_REQUIRED = "retencion_soportada_evidence_required"
    """A suffered-withholding class that may have income has neither a payer record nor an absence attestation."""
    RETENCION_SOPORTADA_ABSENCE_CONTRADICTED = "retencion_soportada_absence_contradicted"
    """A suffered-withholding class holds payer records and an operator's attestation that it has none."""
    RETENCION_SOPORTADA_INCOME_RECORD_REQUIRED = "retencion_soportada_income_record_required"
    """An absence attestation zeroes a credit but not the income of its class, which only a record states."""
    RETENCION_SOPORTADA_RECORD_FIGURE_MISSING = "retencion_soportada_record_figure_missing"
    """A stored payer record predates a figure an income casilla draws and does not state it."""
    CREDIT_SOURCE_DISAGREEMENT = "credit_source_disagreement"
    """A credit casilla's value and one of its declared cross-check sources state different amounts."""
    CREDIT_CROSS_CHECK_ABSENT = "credit_cross_check_absent"
    """A declared cross-check source of a credit casilla holds nothing to compare."""
    CREDIT_RESOLUTION_STALE = "credit_resolution_stale"
    """A figure the operator accepted is now disputed in another way than the one accepted."""
    CREDIT_RESOLUTION_APPLIED = "credit_resolution_applied"
    """The operator accepted the value in use for a disagreement this calculation persisted."""
    HOUSEHOLD_ROWS_INCOMPLETE = "household_rows_incomplete"
    """A household group states more people than the profile records."""
    HOUSEHOLD_ROW_FACT_UNSTATED = "household_row_fact_unstated"
    """A household row omits a fact the official design requires of every row of its group."""
    PROFILE_FACT_UNRECORDED = "profile_fact_unrecorded"
    """A profile fact a calculation compares is unrecorded, so the box built on it stays open."""
    PRIOR_FILING_UNRECORDED = "prior_filing_unrecorded"
    """A box is built on a figure of an earlier filing, and that filing is not recorded, so the box stays open."""
    WITHHOLDING_INVOICE_KIND_UNDECLARED = "withholding_invoice_kind_undeclared"
    """A received invoice states a retención and its payment says neither rent nor an activity's fee."""
    WITHHOLDING_INVOICE_ENTITY_PROFESSIONAL_FEE = "withholding_invoice_entity_professional_fee"
    """A received invoice states a retención on a company's professional fee, which bears none."""
    WITHHOLDING_INVOICE_RECIPIENT_UNKNOWN = "withholding_invoice_recipient_unknown"
    """A received invoice states a retención and its supplier's NIF does not say which income tax it pays."""
    WITHHOLDING_INVOICE_NON_RESIDENT = "withholding_invoice_non_resident"
    """A received invoice states a retención and its supplier is not resident in Spain."""
    WITHHOLDING_INVOICE_RATE_UNRECOGNISED = "withholding_invoice_rate_unrecognised"
    """A received invoice states a retención at a rate no activity rate matches."""
    WITHHOLDING_INVOICE_INCOMPLETE = "withholding_invoice_incomplete"
    """A received invoice states a retención and lacks the supplier's NIF or a euro value."""
    M347_PROVINCIA_UNRECORDED = "m347_provincia_unrecorded"
    """Modelo 347 records of Spanish counterparts whose provincia code no record states, listed together.

    Read only from revisions calculated before each counterpart was named on its own.
    """
    M347_PROVINCIA_UNSTATED = "m347_provincia_unstated"
    """One Spanish Modelo 347 declarado whose provincia the person has not stated for the counterparty."""
    DECLARED_PARTY_NAME_MISSING = "declared_party_name_missing"
    """One party a record names, for which the person has declared no filing name."""
    DECLARED_PARTY_NAME_SINGLE_SURNAME = "declared_party_name_single_surname"
    """One party declared as a natural person with one surname, which the record design gives no rule for."""
    DECLARED_PARTY_NAME_TOO_WIDE = "declared_party_name_too_wide"
    """One party whose declared filing name is wider than its field, with no rendering stated for that width."""
    M349_OPERATION_UNCLASSIFIED = "m349_operation_unclassified"
    """One invoice with a party in another member state and no cuota whose Modelo 349 operation no record states."""
    UNROUTED_IVA_BASE = "unrouted_iva_base"
    """One IVA record's base imponible that no box of the declaration draws for its category."""
    UNROUTED_IVA_CUOTA = "unrouted_iva_cuota"
    """One IVA record's cuota that no box of the declaration draws for its category."""
    UNROUTED_IVA_RECARGO = "unrouted_iva_recargo"
    """One IVA record's recargo de equivalencia that no box of the declaration draws for its category."""
    INVENTORY_PURCHASE_LEDGER_ROW_UNSTATED = "inventory_purchase_ledger_row_unstated"
    """Purchases of an inventory book state nothing about the ledger entry that books them."""
    INVENTORY_PURCHASE_CLAIM_REFUSED = "inventory_purchase_claim_refused"
    """Purchases of an inventory book name a ledger entry that cannot stand as the one that books them."""


GRADE_CAP_NOTE_SENTENCES: Final[Mapping[BindingGradeCapReason, CalculationNoteSentence]] = MappingProxyType(
    {BindingGradeCapReason.IMPUTATION_PERIOD_UNGROUNDED: CalculationNoteSentence.ADVISORY_IMPUTATION_PERIOD_UNGROUNDED}
)
"""The one sentence that states a capped value's facts, by the reason its binding is capped."""

if set(GRADE_CAP_NOTE_SENTENCES) != set(BindingGradeCapReason):
    raise ValueError("every binding grade-cap reason is worded by exactly one calculation note sentence")


class CalculationNoteFact(BaseModel):
    """What one note says about its own subject: a catalogue sentence and the values it names.

    A note's reason says what kind of thing was noticed, and several notes can share
    a reason. This says which row, element, interval and amount this one is about, so
    what was known at calculation stays readable in every language after the process
    that calculated it has gone. Values are the sentence's dates, amounts and box.

    A fact is part of its revision's identity, and an element's name is not a tax
    fact, so ``element_refs`` holds which elements it speaks of and the name is
    read when the note is shown: renaming an element moves no revision. ``row_refs``
    keeps two rows of one date and amount apart; neither is ever shown.
    """

    model_config = STRICT_FROZEN_CONFIG

    sentence: CalculationNoteSentence
    values: tuple[tuple[str, str], ...] = ()
    element_refs: tuple[str, ...] = ()
    row_refs: tuple[str, ...] = ()

    @classmethod
    def of(
        cls,
        sentence: CalculationNoteSentence,
        /,
        *,
        elements: Iterable[str] = (),
        rows: Iterable[str] = (),
        **values: object,
    ) -> Self:
        """Build the fact from the elements and rows it speaks of and its named values, in a stable order."""
        return cls(
            sentence=sentence,
            values=tuple(sorted((name, str(value)) for name, value in values.items())),
            element_refs=tuple(elements),
            row_refs=tuple(rows),
        )

    def identity(self) -> tuple[str, ...]:
        """Flatten the fact for a revision's content identity and for telling two notes apart."""
        return (
            self.sentence.value,
            *(part for pair in self.values for part in pair),
            *self.element_refs,
            *self.row_refs,
        )


class RecordedCalculationNote(BaseModel):
    """A note kept with a calculation, as verification and export restate it."""

    model_config = STRICT_FROZEN_CONFIG

    reason: str = Field(min_length=1, max_length=64)
    fact: CalculationNoteFact
    element_names: tuple[tuple[str, str], ...] = ()
    """The current name of each element the fact speaks of that still has one, read for this showing."""
    message: str = ""
    """The fact in words, in the language of this showing, for a reader that draws it as it stands."""
    detail: str = ""
    """What kind of note this is, in the same language."""


DISAGREEMENT_REASONS: Final[frozenset[str]] = frozenset({"credit_source_disagreement", "precedence_tier_divergence"})
"""The persisted reasons that carry a source disagreement, and only those."""


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
    ``m349_operation_unclassified`` is an invoice with a party in another member
    state and no cuota whose Modelo 349 operation no record states, so the
    recapitulativa leaves it out.
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
    None of them withholds anything. ``advisory_binding_value`` is a value a
    binding produced whose declared grade cap stops it at calculation: it names
    the box the value reaches and the binding, and withholds filing until a
    recalculation under an uncapped binding clears it. ``value_outcome`` is
    what the resolver stated beside that value: a proven zero persists too, so a
    reopened declaration still shows the zero was proven, and withholds nothing;
    a capped note without a stated outcome withholds. Only that reason carries an
    outcome. ``credit_source_disagreement`` is a credit casilla whose value
    source and a declared cross-check source differ by any amount; it carries
    the whole :class:`~.source_disagreement.SourceDisagreementFact` in
    ``disagreement`` and withholds filing. ``credit_cross_check_absent`` is a
    declared cross-check source with nothing to compare, which reads "not
    cross-checked", never agreement, and withholds nothing.
    ``credit_resolution_stale`` is a figure the operator accepted that is now
    disputed in another way than the one accepted: the resolution no longer
    covers it, the disagreement it restates still withholds filing, and the note
    itself withholds nothing. ``fact`` states such a note's own row, element, interval and
    amount. ``binding_source`` is ``None`` only where the condition names no
    binding source kind.
    outcome. ``household_rows_incomplete`` is a household group whose stated
    count is larger than the rows the profile records: the recorded rows are
    used and the group is not proven complete; it withholds nothing.
    ``household_row_fact_unstated`` is a stored household row that omits a fact
    the official design requires of every row, such as an ascendant's NIF: it
    withholds checking, exporting and filing until the profile states the fact.
    ``fact`` states such a note's own row, element, interval and amount.
    ``binding_source`` is ``None`` only where the condition names no binding
    source kind. ``precedence_tier_divergence`` is a filed figure for
    which a higher source tier replaced a different value a lower tier held;
    ``disagreement`` states every tier's value and which one the calculation
    used, and it withholds filing until the sources agree. ``disagreement`` is
    carried by exactly the reasons in :data:`DISAGREEMENT_REASONS`.
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
        "m349_operation_unclassified",
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
        "inventory_book_claimed_purchase",
        "ledger_expense_may_be_durable",
        "household_rows_incomplete",
        "household_row_fact_unstated",
        "advisory_binding_value",
        "credit_source_disagreement",
        "credit_cross_check_absent",
        "credit_resolution_stale",
        "precedence_tier_divergence",
    ]
    binding_source: BindingSourceKind | None
    message: str = Field(min_length=1, max_length=CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)
    casilla_id: CasillaId | None = None
    fact: CalculationNoteFact | None = None
    value_outcome: BindingValueOutcome | None = None
    disagreement: SourceDisagreementFact | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_outcome_on_capped_value_only(self) -> Self:
        if self.value_outcome is not None and self.reason != "advisory_binding_value":
            raise ModeloValidationError(
                "only a capped binding value carries a resolver-stated value outcome",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CALCULATION_REVISION,
            )
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_disagreement_on_disagreement_reasons_only(self) -> Self:
        if (self.disagreement is not None) != (self.reason in DISAGREEMENT_REASONS):
            raise ModeloValidationError(
                "a source disagreement is carried by exactly the reasons that state one",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CALCULATION_REVISION,
            )
        return self


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
        raise ModeloValidationError(
            "source provenance primary reference is ambiguous",
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
            record=ModeloValidatedRecord.CALCULATION_REVISION,
        )
    primary_ref_set = frozenset(primary_refs)
    if any(
        row.parent_source_ref not in primary_ref_set
        for row in rows
        if row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
    ):
        raise ModeloValidationError(
            "source provenance contributor parent does not resolve to a primary",
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
            record=ModeloValidatedRecord.CALCULATION_REVISION,
        )


def element_names_of(fact: CalculationNoteFact | None, names: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Pick out the names a fact's elements go by now; an element that no longer has one is simply absent."""
    if fact is None:
        return ()
    return tuple((ref, names[ref]) for ref in fact.element_refs if ref in names)


def recorded_calculation_notes(
    issues: Iterable[CalculationSourceIssue], *, names: Mapping[str, str] | None = None
) -> tuple[RecordedCalculationNote, ...]:
    """The notes a calculation kept that state their own facts, once each and in the order they were raised."""
    return tuple(
        dict.fromkeys(
            RecordedCalculationNote(
                reason=issue.reason, fact=issue.fact, element_names=element_names_of(issue.fact, names or {})
            )
            for issue in issues
            if issue.fact is not None
        )
    )
