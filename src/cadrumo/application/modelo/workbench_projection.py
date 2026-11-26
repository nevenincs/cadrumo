"""Strict public projection of one declaration's workbench reads.

The workbench form is an owner read model: a password-authenticated human CLI
or TUI session may receive it through the verified local transport, and no
automation or off-host destination may. Its canonical models are not all shaped for
a registered operation result -- a modelo code and a period customise their
core schema, a field's scalar value reads a decimal back as text through strict
JSON, a verification finding serialises its facts -- so exactly those nodes are
mirrored here, through the shared public-mirror engine, and restored afterwards.

Projection proves itself: the restored canonical read must equal the original,
so a mirror that loses a type, a precision or a field fails before anything is
stored. The canonical models' own excluded fields are an empty, reviewed
inventory; a new excluded field fails the projection until it is reviewed.

An authenticated session may retain the immutable form subtree together with
its strictly validated inverse. Exact value, admission and live-schema keys
permit reuse. Strict public-to-canonical restoration is proved at pair build
time; a hit reuses that proof and compares the previously validated inverse
with the fresh read, including every outer and derived field. Admission,
baseline issuance and the outer read are never retained.

The filing-state projection carries only what exporting and recording the
filing rest on, and proves each of those fields restores to the read's own
value; it never mirrors the whole form.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.absence_attestation_family import AbsenceAttestationFamily
from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.export_layout_format import ExportLayoutFormat
from ...core.external_constants import OutputLanguage
from ...core.identity.documents import SpanishTaxIdFormat
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormLayoutSeedSource,
    FormPageCondition,
    FormUnplacedReason,
)
from ...domain.iva.refund_eligibility import RefundEligibilityBasis, RefundEligibilityOutcome
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ..operations.public_mirror import (
    PublicScalarValueV1,
    excluded_canonical_fields,
    project_public_mirror,
    restore_public_mirror,
)
from ..operations.public_period import PublicPeriod
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..workbench_capture_memory import WorkbenchMemoSlot
from ..workbench_generation_modelo_contracts import PublicCasillaConstraints, PublicModeloVerificationFinding
from .calculation_report import CalculationReportRowRole
from .edit_apply_scalar_contracts import ModeloEditWireScalar
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_models import ModeloEditAdmittedV1, ModeloEditBindingIntentKind, ModeloEditRefusedV1
from .reconciliation_sources import ReconciliationSourceRequirementV1
from .source_policy import SourceFamily
from .work_form_declaration_facts import (
    ModeloFormAeatData,
    ModeloFormCalculationNote,
    ModeloFormDeadline,
    ModeloFormEditClosure,
    ModeloFormExport,
    ModeloFormFiling,
    ModeloFormResultDirection,
    ModeloFormYearProjection,
)
from .work_form_export_offer import (
    ModeloExportRequestField,
    ModeloFormArtefactOption,
    ModeloFormAvailability,
    ModeloFormElection,
    ModeloFormElectionChoice,
    ModeloFormElectionFigure,
    ModeloFormElectionReason,
    ModeloFormElectionState,
    ModeloFormExportOffer,
    ModeloFormReceipt,
    ModeloFormReviewPackageOffer,
)
from .work_form_field_vocabulary import (
    ModeloFormAddressV1,
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormBlocker,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormRateUnit,
    ModeloFormStanding,
    ModeloFormText,
)
from .work_form_findings import ModeloFormAttention
from .work_form_header import ModeloFormFilingHeader, ModeloFormHeader
from .work_form_issue_lines import ModeloFormIssueLine, ModeloFormVerdict
from .work_form_journey import ModeloFormJourney
from .work_form_models import (
    ModeloFormBindingStatement,
    ModeloFormCarryAttestation,
    ModeloFormCounts,
    ModeloFormCredit,
    ModeloFormGridColumn,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormOutlineGroup,
    ModeloFormRecordAttention,
    ModeloFormSourceGroup,
    ModeloFormStatedPriorValue,
)
from .work_form_next_step import ModeloFormNextStep
from .work_form_prior_value_models import ModeloFormPriorValueRefusal, ModeloFormPriorValueWithdrawal
from .work_form_service import ModeloWorkFormLoadV1
from .work_form_typing_effect import ModeloFormTypingEffect
from .work_review import ModeloWorkProgress
from .workbench_projection_memory import (
    FormIdentities,
    FormProjectionContext,
    FormProjectionPair,
    FormSectionPair,
    form_identities,
    form_projection_is_immutable,
)
from .workbench_read import ModeloFormLedgerHold, ModeloWorkbenchFilingStateReadV1, ModeloWorkbenchFormReadV1


class PublicModeloFormEarlierFiling(BaseModel):
    """Typed local-human workbench view of ModeloFormEarlierFiling."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    period: PublicPeriod


class PublicModeloFormPriorValueAttestation(BaseModel):
    """Typed local-human workbench view of ModeloFormPriorValueAttestation."""

    model_config = STRICT_FROZEN_CONFIG

    binding_id: str
    edit_address: ModeloFormBindingAddressV1
    intent: ModeloEditBindingIntentKind
    family_id: str
    earlier_filings: tuple[PublicModeloFormEarlierFiling, ...]
    source_words: str
    action_words: str
    statement_words: str
    effect_words: str
    stated: bool
    admitted: bool
    refusal_reason: ModeloFormPriorValueRefusal | None = None
    refusal_words: str | None = None
    refusal: PreconditionVerdictSnapshot | None = None
    withdrawal: ModeloFormPriorValueWithdrawal | None = None


class PublicModeloFormValueSource(BaseModel):
    """Typed local-human workbench view of ModeloFormValueSource."""

    model_config = STRICT_FROZEN_CONFIG

    family: SourceFamily
    binding_id: str | None
    source_kind: BindingSourceKind | None
    earlier_filings: tuple[PublicModeloFormEarlierFiling, ...]


class PublicModeloFormRate(BaseModel):
    """Typed local-human workbench view of ModeloFormRate; the ratio keeps its exact decimal text."""

    model_config = STRICT_FROZEN_CONFIG

    ratio: str
    unit: ModeloFormRateUnit
    binding_id: str


class PublicModeloFormPrintedRate(BaseModel):
    """Typed local-human workbench view of ModeloFormPrintedRate; the ratio keeps its exact decimal text."""

    model_config = STRICT_FROZEN_CONFIG

    ratio: str
    unit: ModeloFormRateUnit
    literal: str


class PublicRefundEligibility(BaseModel):
    """Typed local-human view of RefundEligibility: whether the IVA refund may be asked for, and why.

    ``legal_refs`` are the registry's declared references for the provisions the
    outcome rests on. A frontend renders the header's words; this carries the
    machine-readable outcome beside them so none of it is re-derived there.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: RefundEligibilityOutcome
    basis: RefundEligibilityBasis
    legal_refs: tuple[str, ...]


class PublicModeloFormResult(BaseModel):
    """Typed local-human workbench view of ModeloFormResult; the value keeps its exact decimal text."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    box: str | None
    value: str | None
    direction: ModeloFormResultDirection
    disposition: ResultDisposition | None
    election_may_change: bool
    refund_eligibility: PublicRefundEligibility | None


class PublicModeloFormField(BaseModel):
    """Typed local-human workbench view of ModeloFormField."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    box: str | None
    label: ModeloFormText
    help: str | None
    data_type: str
    #: ``None`` only when the field holds no value, exactly as the canonical field does.
    value: PublicScalarValueV1 | None
    origin: ModeloFormOrigin
    editability: ModeloFormEditability
    not_writable_reason: str | None
    required: bool
    unattributed: bool
    grounded_rate: PublicModeloFormRate | None
    printed_rate: PublicModeloFormPrintedRate | None
    role: CalculationReportRowRole | None
    bindings: tuple[ModeloFormBinding, ...]
    source: PublicModeloFormValueSource | None
    formula_id: str | None
    formula_operands: tuple[str, ...]
    blockers: tuple[ModeloFormBlocker, ...]
    constraints: PublicCasillaConstraints | None
    legal_refs: tuple[str, ...]
    also_appears_on: tuple[str, ...]
    standing: ModeloFormStanding
    attention_rank: int
    edit_address: ModeloFormAddressV1
    confirmable: bool
    held_zero: bool
    origin_words: str | None
    origin_explanation: str | None
    editability_words: str | None
    value_text: str | None
    restorable: bool
    filers_own: bool
    stated_absent: AbsenceAttestationFamily | None = None
    stated_prior_value: ModeloFormStatedPriorValue | None = Field(default=None, exclude_if=lambda value: value is None)
    statements: tuple[ModeloFormBindingStatement, ...] = Field(default=(), exclude_if=lambda value: not value)
    confirm_value: ModeloEditWireScalar
    takes_typed_value: bool
    clearable: bool
    removable: bool
    own_value: ModeloEditWireScalar
    confirm_comparable: ModeloEditWireScalar
    state_digest: str


class PublicModeloFormFieldBlock(BaseModel):
    """Typed local-human workbench view of ModeloFormFieldBlock."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["field"]
    id: str
    field: PublicModeloFormField


class PublicModeloFormContextFieldBlock(BaseModel):
    """Selected read-only context, with no producer snapshot or editing target."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["context_field"]
    id: str
    label: ModeloFormText
    box_number: str | None
    value: PublicScalarValueV1 | None
    value_text: str | None


class PublicModeloFormGridCell(BaseModel):
    """Typed local-human workbench view of ModeloFormGridCell."""

    model_config = STRICT_FROZEN_CONFIG

    kind: FormCellKind
    field: PublicModeloFormField | None
    literal: str | None


class PublicModeloFormGridRow(BaseModel):
    """Typed local-human workbench view of ModeloFormGridRow."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    heading: ModeloFormText
    cells: tuple[PublicModeloFormGridCell, ...]
    rate_cell: int | None
    rate_base_empty: bool | None


class PublicModeloFormGridBlock(BaseModel):
    """Typed local-human workbench view of ModeloFormGridBlock."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["grid"]
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    rows: tuple[PublicModeloFormGridRow, ...]


class PublicModeloFormRepeatingRow(BaseModel):
    """Typed local-human workbench view of ModeloFormRepeatingRow."""

    model_config = STRICT_FROZEN_CONFIG

    index: int
    values: tuple[PublicScalarValueV1 | None, ...]
    value_texts: tuple[str | None, ...]


class PublicModeloFormRepeatingBlock(BaseModel):
    """Typed local-human workbench view of ModeloFormRepeatingBlock."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["repeating"]
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    column_casilla_ids: tuple[str | None, ...]
    column_data_types: tuple[str, ...]
    min_rows: int
    max_rows: int | None
    rows_known: bool
    rows: tuple[PublicModeloFormRepeatingRow, ...]


class PublicModeloFormBindingInputsBlock(BaseModel):
    """Typed local-human workbench view of ModeloFormBindingInputsBlock."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["binding_inputs"]
    id: str
    fields: tuple[PublicModeloFormField, ...]


type PublicModeloFormBlock = Annotated[
    PublicModeloFormFieldBlock
    | PublicModeloFormGridBlock
    | PublicModeloFormRepeatingBlock
    | PublicModeloFormBindingInputsBlock
    | PublicModeloFormContextFieldBlock,
    Field(discriminator="kind"),
]


class PublicModeloFormSection(BaseModel):
    """Typed local-human workbench view of ModeloFormSection."""

    model_config = STRICT_FROZEN_CONFIG

    id: str
    heading: ModeloFormText
    official_heading: str | None
    blocks: tuple[PublicModeloFormBlock, ...]
    counts: ModeloFormCounts
    applies: bool | None
    record_attention: tuple[ModeloFormRecordAttention, ...]


class PublicModeloFormPage(BaseModel):
    """Typed local-human workbench view of ModeloFormPage."""

    model_config = STRICT_FROZEN_CONFIG

    id: str
    heading: ModeloFormText
    official_ref: str | None
    condition: FormPageCondition
    applies: bool | None
    sections: tuple[PublicModeloFormSection, ...]
    counts: ModeloFormCounts
    applicability_words: str | None


class PublicModeloFormUnplacedField(BaseModel):
    """Typed local-human workbench view of ModeloFormUnplacedField."""

    model_config = STRICT_FROZEN_CONFIG

    field: PublicModeloFormField
    reason: FormUnplacedReason | None


class PublicModeloFormIssue(BaseModel):
    """Typed local-human workbench view of ModeloFormIssue."""

    model_config = STRICT_FROZEN_CONFIG

    finding: PublicModeloVerificationFinding
    box: str | None
    attention: ModeloFormAttention
    action_locale_key: str
    open_invoice_id: str | None = None
    door_action_id: str | None = None


class PublicModeloWorkForm(BaseModel):
    """Typed local-human workbench view of ModeloWorkForm."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: PublicPeriod
    registry_revision_id: str
    year_projection: ModeloFormYearProjection
    work_unit_id: str
    calculation_revision_id: str | None
    language: OutputLanguage
    layout_provenance: ModeloFormLayoutProvenance
    inspection_reason: ModeloFormInspectionReason | None
    seed_source: FormLayoutSeedSource | None
    pages: tuple[PublicModeloFormPage, ...]
    outline: tuple[ModeloFormOutlineGroup, ...]
    working_figures: tuple[PublicModeloFormField, ...]
    unplaced: tuple[PublicModeloFormUnplacedField, ...]
    answers: tuple[PublicModeloFormField, ...] = ()
    result_addresses: tuple[CasillaId, ...]
    withholding_credits: tuple[ModeloFormCredit, ...] = ()
    withholding_credits_heading: str | None = None
    counts: ModeloFormCounts
    progress: ModeloWorkProgress
    operator_entries_known: bool
    edit_admitted: bool
    verification: VerificationCompletenessStatus | None
    issues: tuple[PublicModeloFormIssue, ...]
    calculation_notes: tuple[ModeloFormCalculationNote, ...]
    calculation_notes_held: bool
    source_groups: tuple[ModeloFormSourceGroup, ...]
    result: PublicModeloFormResult | None
    deadline: ModeloFormDeadline | None
    aeat_data: ModeloFormAeatData | None
    projectable: bool = False
    asks_imputation_election: bool = False
    compares_taxation: bool = False
    compares_borrador: bool = False
    offers_iva_wallet: bool = False
    verification_out_of_date: bool = False
    calculation_sources_arrived: bool = Field(default=False, exclude_if=lambda value: not value)
    filing: ModeloFormFiling | None
    last_export: ModeloFormExport | None
    edit_closure: ModeloFormEditClosure | None
    carry_attestations: tuple[ModeloFormCarryAttestation, ...] = ()
    prior_value_attestations: tuple[PublicModeloFormPriorValueAttestation, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    modelo_title: str | None
    modelo_name: str | None
    modelo_number: str | None
    period_words: str | None


class PublicModeloWorkFormLoadV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkFormLoadV1."""

    model_config = STRICT_FROZEN_CONFIG

    form: PublicModeloWorkForm
    verified: bool
    filed: bool
    journey: ModeloFormJourney


class PublicSpanishTaxIdFormat(BaseModel):
    """Typed local-human workbench view of the governed SpanishTaxIdFormat."""

    model_config = STRICT_FROZEN_CONFIG

    width: int
    country_prefix: str
    country_prefixed_width: int
    country_prefix_strip_width: int
    prefixed_nif_leaders: str
    nie_leaders: str
    cif_leaders: str
    nif_letters: str
    nif_check_modulus: int
    nie_prefix_substitutions: tuple[tuple[str, str], ...]
    cif_digit_only_kinds: str
    cif_letter_only_kinds: str
    cif_letter_table: str


class PublicModeloFormElectionFigure(ModeloFormElectionFigure):
    """Public figure preserving the canonical exact amount and advisory validation."""


class PublicModeloFormElectionQuestion(BaseModel):
    """Public election question whose figures preserve their decimal precision."""

    model_config = STRICT_FROZEN_CONFIG

    election: ModeloFormElection
    request_field: ModeloExportRequestField
    words: str = Field(min_length=1)
    state: ModeloFormElectionState = ModeloFormElectionState.AVAILABLE
    reason: ModeloFormElectionReason | None = None
    state_words: str | None = None
    help: str | None = None
    default: str | None = None
    choices: tuple[ModeloFormElectionChoice, ...] = ()
    figures: tuple[PublicModeloFormElectionFigure, ...] = ()


class PublicModeloFormExportOffer(BaseModel):
    """Public export offer carrying decimal-safe election questions."""

    model_config = STRICT_FROZEN_CONFIG

    artefacts: tuple[ModeloFormArtefactOption, ...] = Field(min_length=1)
    record: ModeloFormAvailability
    review_package: ModeloFormReviewPackageOffer
    asks_elections: bool
    elections: tuple[PublicModeloFormElectionQuestion, ...]
    file_format: ExportLayoutFormat | None
    file_format_words: str | None


class ModeloWorkbenchFormProjectionV1(BaseModel):
    """Public exact-profile envelope around one declaration's workbench read.

    Exactly one of ``admitted_baseline`` and ``admission_refusal`` is present:
    the edit baseline admitted with this read, or why the declaration cannot be
    edited.
    """

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    work_unit_id: str
    form: PublicModeloWorkFormLoadV1
    admitted_baseline: ModeloEditApplyBaselineV1 | None
    admission_refusal: ModeloEditRefusedV1 | None
    #: Why the declaration cannot be edited, as one sentence in the form's language; ``None`` once admitted.
    admission_refusal_words: str | None = None
    #: Whether the registry rules for the revision stop short of calculation grade, so nothing can be worked out.
    rules_incomplete: bool = False
    #: The one action the form offers next, ``None`` when the registry rules for the revision cannot calculate it.
    next_step: ModeloFormNextStep | None
    #: What the header states: the attention counts, the result, the deadline, the latest file and any hold.
    header: ModeloFormHeader
    #: What the check view lists: every finding and calculation note in words, most urgent first.
    issue_lines: tuple[ModeloFormIssueLine, ...]
    #: What the last check concluded, in words.
    verdict: ModeloFormVerdict
    calculation_revision_id: str | None
    verification_report_id: str | None
    asks_m303_evidence: bool
    asks_modelo_390: bool
    registry_revision_id: str
    tax_id_format: PublicSpanishTaxIdFormat
    #: What typing a value over each box the filer can type on does, in words, by the box's address.
    typing_effects: tuple[ModeloFormTypingEffect, ...] = ()
    #: What exporting offers: the artefacts, whether elections are asked and with which choices, the file format.
    export_offer: PublicModeloFormExportOffer | None = None
    #: The profile details the readiness gate still asks for, each as its label in the form's language.
    profile_requirements: tuple[str, ...] = ()
    #: The declarations an annual summary sums whose filed figures are not there yet, each with its step.
    source_requirements: tuple[ReconciliationSourceRequirementV1, ...] = ()
    #: The recorded filing's AEAT receipt state; ``None`` when the declaration is not recorded as filed.
    receipt: ModeloFormReceipt | None = None
    #: What in the ledger holds calculating this declaration, in words, with the movement to open.
    ledger_hold: ModeloFormLedgerHold | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _bound_to_one_profile_and_declaration(self) -> Self:
        if (self.admitted_baseline is None) == (self.admission_refusal is None):
            raise ValueError("a workbench read carries exactly one admission outcome")
        baseline = self.admitted_baseline
        if baseline is not None and (
            baseline.bucket_id != str(self.profile_id) or baseline.work_unit_id != self.work_unit_id
        ):
            raise ValueError("the admitted baseline belongs to another declaration")
        form = self.form.form
        if form.work_unit_id != self.work_unit_id or form.calculation_revision_id != self.calculation_revision_id:
            raise ValueError("the workbench form belongs to another declaration or calculation")
        if self.verification_report_id is not None and self.calculation_revision_id is None:
            raise ValueError("a granting verification report requires its calculation")
        return self


class ModeloWorkFilingStateProjectionV1(BaseModel):
    """Public exact-profile envelope around what exporting and recording one declaration's filing rest on.

    Each field is the one :class:`ModeloWorkbenchFormProjectionV1` carries for
    the same stored state: ``modelo``, ``period``, ``filing`` and
    ``edit_closure`` are its form's, ``filed`` and ``journey`` its load's,
    ``header`` its header's result, latest file and export hold, and
    ``rules_incomplete`` and ``next_step`` its own.
    """

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    work_unit_id: str
    modelo: str
    period: PublicPeriod
    #: The filing recorded in Cadrumo; ``None`` while the declaration is not recorded as filed.
    filing: ModeloFormFiling | None
    #: Whether the declaration is recorded as filed.
    filed: bool
    #: Why the form no longer takes edits; ``None`` while it may still be edited.
    edit_closure: ModeloFormEditClosure | None
    #: Where the declaration stands on the filing journey.
    journey: ModeloFormJourney
    #: Whether the registry rules for the revision stop short of calculation grade, so nothing can be worked out.
    rules_incomplete: bool
    #: The one action the form offers next, ``None`` when the registry rules for the revision cannot calculate it.
    next_step: ModeloFormNextStep | None
    header: ModeloFormFilingHeader
    calculation_revision_id: str | None
    verification_report_id: str | None
    #: What exporting offers: the artefacts, whether recording is available, the elections and the file format.
    export_offer: PublicModeloFormExportOffer
    #: The recorded filing's AEAT receipt state; ``None`` when the declaration is not recorded as filed.
    receipt: ModeloFormReceipt | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _report_follows_its_calculation(self) -> Self:
        if self.verification_report_id is not None and self.calculation_revision_id is None:
            raise ValueError("a granting verification report requires its calculation")
        return self


_REVIEWED_EXCLUDED_FIELDS: frozenset[tuple[type[BaseModel], str]] = frozenset[tuple[type[BaseModel], str]]()
"""No canonical workbench form field is excluded from its own serializer today."""


def _require_reviewed_exclusions() -> None:
    excluded = excluded_canonical_fields(ModeloWorkFormLoadV1) | excluded_canonical_fields(ModeloFormExportOffer)
    if excluded != _REVIEWED_EXCLUDED_FIELDS:
        raise ValueError("workbench form excluded-field inventory changed")


def _project_form(load: ModeloWorkFormLoadV1, kept: Mapping[int, object] | None = None) -> PublicModeloWorkFormLoadV1:
    projected = project_public_mirror(load, ModeloWorkFormLoadV1, PublicModeloWorkFormLoadV1, kept=kept)
    if not isinstance(projected, PublicModeloWorkFormLoadV1):
        raise TypeError("workbench form public projection failed")
    return projected


def _restore_form(public: PublicModeloWorkFormLoadV1, kept: Mapping[int, object] | None = None) -> ModeloWorkFormLoadV1:
    restored = restore_public_mirror(public, ModeloWorkFormLoadV1, PublicModeloWorkFormLoadV1, kept=kept)
    if not isinstance(restored, ModeloWorkFormLoadV1):
        raise TypeError("workbench form canonical restoration failed")
    return restored


type FormSectionSlot = WorkbenchMemoSlot[Hashable, Mapping[Hashable, FormSectionPair]]
"""The sections of the form a session was last served, each kept with its proven mirror, under their schemas."""


def _mirrored_form(
    load: ModeloWorkFormLoadV1,
    sections: FormSectionSlot | None,
    identities: FormIdentities | None,
    spent: dict[str, int] | None = None,
) -> tuple[FormProjectionPair, bool | None]:
    """Mirror ``load`` and restore it, proving the two equal; sections proven before are not walked again.

    A section kept in ``sections`` under its exact value stands for its own
    mirror and restoration; every other part of the form is mirrored and
    restored here. The restored form is compared whole with ``load`` before
    anything is kept, so a kept section is always one a full proof covered.
    The second answer is whether the pair is immutable, ``None`` when no
    memory asked.
    """
    if sections is None or identities is None:
        public = _project_form(load)
        return _proven_pair(load, public, _restore_form(public)), None
    kept = sections.recall(identities.schemas) or {}
    held = {
        id(section): pair
        for page, page_keys in zip(load.form.pages, identities.sections, strict=True)
        for section, key in zip(page.sections, page_keys, strict=True)
        if (pair := kept.get(key)) is not None
    }
    public = _project_form(load, {identity: pair.public for identity, pair in held.items()})
    restored = _restore_form(public, {id(pair.public): pair.canonical for pair in held.values()})
    proven = _proven_pair(load, public, restored)
    if spent is not None:
        spent["projection_sections_reused"] = len(held)
        spent["projection_sections"] = sum(len(page_keys) for page_keys in identities.sections)
    # A kept section passed this check when it was kept, and it is the same object now.
    immutable = form_projection_is_immutable(
        public, PublicModeloWorkFormLoadV1, settled=[pair.public for pair in held.values()]
    ) and form_projection_is_immutable(
        restored, PublicModeloWorkFormLoadV1, settled=[pair.canonical for pair in held.values()]
    )
    if immutable:
        sections.keep(identities.schemas, _section_pairs(identities.sections, public, restored))
    return proven, immutable


def _proven_pair(
    load: ModeloWorkFormLoadV1, public: PublicModeloWorkFormLoadV1, restored: ModeloWorkFormLoadV1
) -> FormProjectionPair:
    if restored != load:
        raise ValueError("workbench form public projection changed canonical meaning")
    return FormProjectionPair(public, restored)


def _section_pairs(
    keys: tuple[tuple[Hashable, ...], ...], public: PublicModeloWorkFormLoadV1, restored: ModeloWorkFormLoadV1
) -> dict[Hashable, FormSectionPair]:
    return {
        key: FormSectionPair(public_section, section)
        for public_page, page, page_keys in zip(public.form.pages, restored.form.pages, keys, strict=True)
        for public_section, section, key in zip(public_page.sections, page.sections, page_keys, strict=True)
    }


def _project_export_offer(offer: ModeloFormExportOffer | None) -> PublicModeloFormExportOffer | None:
    if offer is None:
        return None
    projected = project_public_mirror(offer, ModeloFormExportOffer, PublicModeloFormExportOffer)
    if not isinstance(projected, PublicModeloFormExportOffer):
        raise TypeError("workbench export offer public projection failed")
    return projected


def _restore_export_offer(public: PublicModeloFormExportOffer | None) -> ModeloFormExportOffer | None:
    if public is None:
        return None
    restored = restore_public_mirror(public, ModeloFormExportOffer, PublicModeloFormExportOffer)
    if not isinstance(restored, ModeloFormExportOffer):
        raise TypeError("workbench export offer canonical restoration failed")
    return restored


def _project_tax_id_format(value: SpanishTaxIdFormat) -> PublicSpanishTaxIdFormat:
    projected = project_public_mirror(value, SpanishTaxIdFormat, PublicSpanishTaxIdFormat)
    if not isinstance(projected, PublicSpanishTaxIdFormat):
        raise TypeError("tax-identifier format public projection failed")
    return projected


def _restore_tax_id_format(public: PublicSpanishTaxIdFormat) -> SpanishTaxIdFormat:
    restored = restore_public_mirror(public, SpanishTaxIdFormat, PublicSpanishTaxIdFormat)
    if not isinstance(restored, SpanishTaxIdFormat):
        raise TypeError("tax-identifier format restoration failed")
    return restored


def _restore(
    projection: ModeloWorkbenchFormProjectionV1, pair: FormProjectionPair | None = None
) -> ModeloWorkbenchFormReadV1:
    baseline = projection.admitted_baseline
    admission = (
        ModeloEditAdmittedV1(baseline=baseline.to_baseline()) if baseline is not None else projection.admission_refusal
    )
    if admission is None:
        raise ValueError("workbench projection has no edit admission outcome")
    return ModeloWorkbenchFormReadV1(
        load=pair.canonical if pair is not None and projection.form is pair.public else _restore_form(projection.form),
        admission=admission,
        calculation_revision_id=projection.calculation_revision_id,
        verification_report_id=projection.verification_report_id,
        asks_m303_evidence=projection.asks_m303_evidence,
        asks_modelo_390=projection.asks_modelo_390,
        registry_revision_id=projection.registry_revision_id,
        tax_id_format=_restore_tax_id_format(projection.tax_id_format),
        export_offer=_restore_export_offer(projection.export_offer),
        receipt=projection.receipt,
        profile_requirements=projection.profile_requirements,
        ledger_hold=projection.ledger_hold,
        source_requirements=projection.source_requirements,
    )


def _require_projection_roundtrip(
    read: ModeloWorkbenchFormReadV1,
    projection: ModeloWorkbenchFormProjectionV1,
    pair: FormProjectionPair | None = None,
) -> None:
    restored = _restore(projection, pair)
    if (
        restored != read
        or restored.typing_effects != projection.typing_effects
        or restored.next_step != projection.next_step
        or restored.admission_refusal_words != projection.admission_refusal_words
        or restored.rules_incomplete is not projection.rules_incomplete
        or restored.header != projection.header
        or restored.issue_lines != projection.issue_lines
        or restored.verdict != projection.verdict
    ):
        raise ValueError("workbench form public projection changed canonical meaning")


def project_modelo_workbench_form(
    profile_id: UUID,
    work_unit_id: str,
    read: ModeloWorkbenchFormReadV1,
    *,
    memory: WorkbenchMemoSlot[Hashable, FormProjectionPair | None] | None = None,
    context: FormProjectionContext | None = None,
    spent: dict[str, int] | None = None,
    sections: FormSectionSlot | None = None,
) -> ModeloWorkbenchFormProjectionV1:
    """Project one workbench read for its exact profile and prove nothing was lost.

    ``spent`` receives ``projection_pair_reused`` whenever the form could be
    kept in ``memory``: whether a projection kept for this exact form served it.
    ``sections`` keeps each section's proven mirror, so a form read again after
    a change mirrors and proves only the sections that changed.
    """
    _require_reviewed_exclusions()
    admission = read.admission
    identities = (
        form_identities(read.load, PublicModeloWorkFormLoadV1) if memory is not None or sections is not None else None
    )
    pair = (
        _reusable_form(read, memory, context, identities, spent, sections)
        or _mirrored_form(read.load, sections, identities, spent)[0]
    )
    public_form = pair.public
    if not isinstance(public_form, PublicModeloWorkFormLoadV1):
        raise TypeError("workbench form public projection failed")
    projection = ModeloWorkbenchFormProjectionV1(
        result_version=1,
        profile_id=profile_id,
        work_unit_id=work_unit_id,
        form=public_form,
        admitted_baseline=(
            ModeloEditApplyBaselineV1.from_baseline(admission.baseline)
            if isinstance(admission, ModeloEditAdmittedV1)
            else None
        ),
        admission_refusal=admission if isinstance(admission, ModeloEditRefusedV1) else None,
        admission_refusal_words=read.admission_refusal_words,
        rules_incomplete=read.rules_incomplete,
        next_step=read.next_step,
        header=read.header,
        issue_lines=read.issue_lines,
        verdict=read.verdict,
        calculation_revision_id=read.calculation_revision_id,
        verification_report_id=read.verification_report_id,
        asks_m303_evidence=read.asks_m303_evidence,
        asks_modelo_390=read.asks_modelo_390,
        registry_revision_id=read.registry_revision_id,
        tax_id_format=_project_tax_id_format(read.tax_id_format),
        typing_effects=read.typing_effects,
        export_offer=_project_export_offer(read.export_offer),
        receipt=read.receipt,
        profile_requirements=read.profile_requirements,
        ledger_hold=read.ledger_hold,
        source_requirements=read.source_requirements,
    )
    try:
        _require_projection_roundtrip(read, projection, pair)
    except ValueError:
        if memory is not None:
            memory.clear()
        if sections is not None:
            sections.clear()
        raise
    return projection


def _reusable_form(
    read: ModeloWorkbenchFormReadV1,
    memory: WorkbenchMemoSlot[Hashable, FormProjectionPair | None] | None,
    context: FormProjectionContext | None,
    identities: FormIdentities | None,
    spent: dict[str, int] | None = None,
    sections: FormSectionSlot | None = None,
) -> FormProjectionPair | None:
    if memory is None or context is None or not isinstance(read.admission, ModeloEditAdmittedV1):
        return None
    if identities is None:
        return None
    built: FormProjectionPair | None = None

    def build() -> FormProjectionPair | None:
        nonlocal built
        built, immutable = _mirrored_form(read.load, sections, identities, spent)
        if immutable is None:
            immutable = form_projection_is_immutable(
                built.public, PublicModeloWorkFormLoadV1
            ) and form_projection_is_immutable(built.canonical, PublicModeloWorkFormLoadV1)
        return built if immutable else None

    pair = memory.reuse((context, identities.form), build) or built
    if spent is not None:
        spent["projection_pair_reused"] = built is None and pair is not None
    return pair


def _require_filing_state_roundtrip(
    read: ModeloWorkbenchFilingStateReadV1, projection: ModeloWorkFilingStateProjectionV1
) -> None:
    """Prove every field the projection carries restores to the read's own value."""
    form = read.load.summary
    restored: tuple[tuple[object, object], ...] = (
        (_restore_export_offer(projection.export_offer), read.export_offer),
        (ModeloCode(projection.modelo), form.modelo),
        (projection.period.to_period(), form.period),
        (projection.filing, form.filing),
        (projection.filed, read.load.filed),
        (projection.edit_closure, form.edit_closure),
        (projection.journey, read.load.journey),
        (projection.rules_incomplete, read.rules_incomplete),
        (projection.next_step, read.next_step),
        (projection.header, read.header),
        (projection.work_unit_id, form.work_unit_id),
        (projection.calculation_revision_id, read.calculation_revision_id),
        (projection.verification_report_id, read.verification_report_id),
        (projection.receipt, read.receipt),
    )
    if any(public != canonical for public, canonical in restored):
        raise ValueError("filing state public projection changed canonical meaning")


def project_modelo_work_filing_state(
    profile_id: UUID, work_unit_id: str, read: ModeloWorkbenchFilingStateReadV1
) -> ModeloWorkFilingStateProjectionV1:
    """Project one filing-state read for its exact profile and prove none of its fields lost anything."""
    _require_reviewed_exclusions()
    form = read.load.summary
    if form.work_unit_id != work_unit_id or form.calculation_revision_id != read.calculation_revision_id:
        raise ValueError("the filing state belongs to another declaration or calculation")
    export_offer = _project_export_offer(read.export_offer)
    if export_offer is None:
        raise TypeError("filing state export offer public projection failed")
    projection = ModeloWorkFilingStateProjectionV1(
        result_version=1,
        profile_id=profile_id,
        work_unit_id=work_unit_id,
        modelo=str(form.modelo),
        period=PublicPeriod.from_period(form.period),
        filing=form.filing,
        filed=read.load.filed,
        edit_closure=form.edit_closure,
        journey=read.load.journey,
        rules_incomplete=read.rules_incomplete,
        next_step=read.next_step,
        header=read.header,
        calculation_revision_id=read.calculation_revision_id,
        verification_report_id=read.verification_report_id,
        export_offer=export_offer,
        receipt=read.receipt,
    )
    _require_filing_state_roundtrip(read, projection)
    return projection


def restore_modelo_workbench_form(projection: ModeloWorkbenchFormProjectionV1) -> ModeloWorkbenchFormReadV1:
    """Rebuild the canonical workbench read and prove it projects back unchanged."""
    _require_reviewed_exclusions()
    restored = _restore(projection)
    if _project_form(restored.load) != projection.form:
        raise ValueError("workbench form public projection changed canonical meaning")
    return restored


def _public_section_fields(section: PublicModeloFormSection) -> tuple[PublicModeloFormField, ...]:
    """A section's fields in reading order, grid rows left to right."""
    collected: list[PublicModeloFormField] = []
    for block in section.blocks:
        if isinstance(block, PublicModeloFormFieldBlock):
            collected.append(block.field)
        elif isinstance(block, PublicModeloFormGridBlock):
            collected.extend(cell.field for row in block.rows for cell in row.cells if cell.field is not None)
        elif isinstance(block, PublicModeloFormBindingInputsBlock):
            collected.extend(block.fields)
    return tuple(collected)


def public_form_fields(form: PublicModeloWorkForm) -> tuple[PublicModeloFormField, ...]:
    """Every field of ``form`` once, in reading order: pages, then working figures, unplaced, then answers."""
    placed = tuple(
        field for page in form.pages for section in page.sections for field in _public_section_fields(section)
    )
    return (*placed, *form.working_figures, *(item.field for item in form.unplaced), *form.answers)


__all__ = [
    "ModeloWorkFilingStateProjectionV1",
    "ModeloWorkbenchFormProjectionV1",
    "PublicModeloFormBindingInputsBlock",
    "PublicModeloFormContextFieldBlock",
    "PublicModeloFormEarlierFiling",
    "PublicModeloFormElectionFigure",
    "PublicModeloFormElectionQuestion",
    "PublicModeloFormExportOffer",
    "PublicModeloFormField",
    "PublicModeloFormFieldBlock",
    "PublicModeloFormGridBlock",
    "PublicModeloFormGridCell",
    "PublicModeloFormGridRow",
    "PublicModeloFormIssue",
    "PublicModeloFormPage",
    "PublicModeloFormPrintedRate",
    "PublicModeloFormPriorValueAttestation",
    "PublicModeloFormRate",
    "PublicModeloFormRepeatingBlock",
    "PublicModeloFormRepeatingRow",
    "PublicModeloFormResult",
    "PublicModeloFormSection",
    "PublicModeloFormUnplacedField",
    "PublicModeloFormValueSource",
    "PublicModeloWorkForm",
    "PublicModeloWorkFormLoadV1",
    "PublicSpanishTaxIdFormat",
    "project_modelo_work_filing_state",
    "project_modelo_workbench_form",
    "public_form_fields",
    "restore_modelo_workbench_form",
]
