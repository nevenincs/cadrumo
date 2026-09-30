"""The editor form of one modelo work target, as a person reads and edits it.

The form is the canonical work review arranged by the revision's declared form
layout and classified for an editor: every casilla sits on a page and section
the official form names, or among the working figures the form does not print,
or in the unplaced list with its reason. Every field carries its official box
number, its localized label and help, its value, one origin state and one
editability classification, so a frontend renders the form and never decides
what a value means or whether it may change.

The two classifications are closed application vocabulary:

* :class:`ModeloFormOrigin` says where the value stands: entered by the filer,
  imported from a source, calculated, still needed, not applicable by design,
  and the other states a filer must be able to tell apart. "Nothing was
  entered" and "zero was entered" are different origins, never one figure.
* :class:`ModeloFormEditability` says what may be done about it: type a value,
  override a source with a reason, fix it at its source, correct it in the
  profile, or nothing because it is calculated or fixed by the official design.

Every text a person reads carries its :class:`ModeloFormTextDisclosure`, so a
Spanish fallback, a verbatim official heading or a technical name is never
passed off as a translation.

Beside the fields, the form states the facts a filer asks about the whole
declaration: where each bound value comes from (:class:`ModeloFormValueSource`),
whether the calculation replayed AEAT tax data (:class:`ModeloFormAeatData`),
the last day to file (:class:`ModeloFormDeadline`), the settled result and its
direction (:class:`ModeloFormResult`), and whether the declaration is recorded
as filed (:class:`ModeloFormFiling`). Each is classified here from declared
facts, so a frontend only renders it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.ids import BindingId, FormulaId, LegalRefId, RevisionId
from ...domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormLayoutSeedSource,
    FormPageCondition,
    FormUnplacedReason,
)
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from .calculation_report import CalculationReportRowRole
from .source_policy import SourceFamily, SourcePolicyV1
from .work_review import ModeloWorkProgress

type ModeloFormScalar = Decimal | int | str | bool | date | None
"""A field's value as the calculation holds it; ``None`` only when there is none."""


class _FormModel(BaseModel):
    model_config = STRICT_FROZEN_CONFIG


class ModeloFormLayoutProvenance(StrEnum):
    """Where the form's arrangement comes from."""

    #: A declared layout a named person reviewed.
    REVIEWED = "reviewed"
    #: A declared layout generated from official sources and not yet reviewed.
    GENERATED = "generated"
    #: No usable declared layout: a read-only list in box order, with its reason.
    INSPECTION_ONLY = "inspection_only"


class ModeloFormInspectionReason(StrEnum):
    """Why a form could only be inspected."""

    LAYOUT_ABSENT = "layout_absent"
    LAYOUT_FOR_ANOTHER_REVISION = "layout_for_another_revision"


class ModeloFormTextDisclosure(StrEnum):
    """Which catalogue coordinate a displayed text came from."""

    #: Translated into the requested language.
    LOCALIZED = "localized"
    #: The Spanish source text, shown because no translation exists yet.
    SPANISH_FALLBACK = "spanish_fallback"
    #: The official design's Spanish words, quoted verbatim.
    OFFICIAL_SPANISH = "official_spanish"
    #: A technical name, shown because no human text exists.
    TECHNICAL = "technical"


class ModeloFormText(_FormModel):
    """One displayed text and the honest account of where it came from."""

    text: str = Field(min_length=1)
    disclosure: ModeloFormTextDisclosure


class ModeloFormOrigin(StrEnum):
    """Where one field's value stands; exactly one per field."""

    #: The registry proves the value does not apply to this filer or period.
    NOT_APPLICABLE = "not_applicable"
    #: The filer's value replaces what a source or the calculation produced.
    OVERRIDES_SOURCE = "overrides_source"
    CALCULATED = "calculated"
    #: A calculated box on a work unit that has not been calculated yet.
    NOT_CALCULATED_YET = "not_calculated_yet"
    #: A calculated box the last calculation could not produce.
    CALCULATION_FAILED = "calculation_failed"
    #: Identification or projection figures that are shown, not declared.
    INFORMATIONAL = "informational"
    #: A box the declaration needs and nobody has filled.
    NEEDS_INPUT = "needs_input"
    IMPORTED = "imported"
    #: A box a source should fill and has not.
    NOT_IMPORTED_YET = "not_imported_yet"
    OPTIONAL_EMPTY = "optional_empty"
    #: The filer explicitly removed a value they had declared.
    CLEARED = "cleared"
    #: A value the calculation holds that nobody is proven to have entered.
    DEFAULT_TO_CONFIRM = "default_to_confirm"
    ENTERED = "entered"


ABSENT_FROM_ADMISSION: Final[str] = "absent_from_admission"
"""The not-writable reason of a field the edit admission does not name at all."""


class ModeloFormEditability(StrEnum):
    """What may be done about one field's value; exactly one per field."""

    #: The filer types the value.
    EDITABLE_VALUE = "editable_value"
    #: The filer types the value of a binding no casilla owns.
    EDITABLE_OVERRIDE = "editable_override"
    #: A carried source value the filer may replace, with a reason.
    OVERRIDABLE_SOURCE = "overridable_source"
    #: A value that follows the filer's records and is corrected there.
    LOCKED_SOURCE = "locked_source"
    #: A source nobody has yet decided a filer may replace.
    SOURCE_POLICY_UNDECIDED = "source_policy_undecided"
    #: A profile fact, corrected once in the profile.
    EDIT_AT_PROFILE = "edit_at_profile"
    CALCULATED = "calculated"
    #: A value the official design fixes.
    DESIGN_CONSTANT = "design_constant"
    INFORMATIONAL = "informational"
    #: The edit admission declares the address read-only, with its reason.
    NOT_WRITABLE = "not_writable"
    #: No edit admission is available for this form.
    NO_ADMISSION = "no_admission"


class ModeloFormCasillaAddressV1(_FormModel):
    """A field addressed by its casilla."""

    kind: Literal["casilla"] = "casilla"
    casilla_id: CasillaId


class ModeloFormBindingAddressV1(_FormModel):
    """A field addressed by a binding no casilla owns."""

    kind: Literal["binding"] = "binding"
    binding_id: BindingId


type ModeloFormAddressV1 = Annotated[
    ModeloFormCasillaAddressV1 | ModeloFormBindingAddressV1, Field(discriminator="kind")
]
"""A field's semantic address; focus, staging and review key on it, never on position."""


def address_key(address: ModeloFormAddressV1) -> tuple[str, str]:
    """Return the hashable identity of one address."""
    if isinstance(address, ModeloFormCasillaAddressV1):
        return ("casilla", str(address.casilla_id))
    return ("binding", str(address.binding_id))


class ModeloFormBinding(_FormModel):
    """One binding that feeds a field, with its source's policy and whether it resolved."""

    binding_id: BindingId
    policy: SourcePolicyV1
    resolved: bool


class ModeloFormBlocker(_FormModel):
    """One verification finding that blocks the field."""

    code: str = Field(min_length=1)


class ModeloFormEarlierFiling(_FormModel):
    """One earlier declaration a carried value is read from."""

    modelo: str = Field(min_length=1)
    #: The earlier declaration's filing year and period.
    period: Period


class ModeloFormValueSource(_FormModel):
    """Where a field's value comes from, named from its primary binding.

    ``family`` is the kind of place a filer thinks of: their records, a register
    they keep, their profile, an earlier filing, the AEAT tax data, a value they
    type, or a value the official form fixes. A value the calculation took from
    an imported AEAT draft reads as AEAT data, whatever its binding would
    otherwise fetch. ``earlier_filings`` names the declarations a carried value
    is read from when the binding identifies them, and is empty otherwise; it
    never guesses one. ``binding_id`` and ``source_kind`` are ``None`` only for a
    value the declared layout fixes without any binding.
    """

    family: SourceFamily
    binding_id: BindingId | None = None
    source_kind: BindingSourceKind | None = None
    earlier_filings: tuple[ModeloFormEarlierFiling, ...] = ()


class ModeloFormField(_FormModel):
    """One box or binding input, classified for an editor."""

    address: ModeloFormAddressV1
    box: str | None
    label: ModeloFormText
    help: str | None
    data_type: str = Field(min_length=1)
    value: ModeloFormScalar
    origin: ModeloFormOrigin
    editability: ModeloFormEditability
    not_writable_reason: str | None = None
    #: Whether the declaration needs this value from the filer, by the rule verification checks.
    required: bool
    role: CalculationReportRowRole | None = None
    #: The bindings that feed the field; on a bound casilla the first is the one an override replaces.
    bindings: tuple[ModeloFormBinding, ...] = ()
    #: Where the value comes from; ``None`` for a field no binding or declared constant feeds.
    source: ModeloFormValueSource | None = None
    formula_id: FormulaId | None = None
    formula_operands: tuple[str, ...] = ()
    blockers: tuple[ModeloFormBlocker, ...] = ()
    constraints: CasillaConstraints | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    also_appears_on: tuple[str, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _reason_only_when_not_writable(self) -> ModeloFormField:
        if (self.editability is ModeloFormEditability.NOT_WRITABLE) != (self.not_writable_reason is not None):
            raise ValueError("a not-writable reason belongs to, and only to, a not-writable field")
        return self


_OVERRIDE_EDITABILITIES = frozenset({ModeloFormEditability.OVERRIDABLE_SOURCE, ModeloFormEditability.EDITABLE_OVERRIDE})


def edit_address(field: ModeloFormField) -> ModeloFormAddressV1:
    """Return the address a change to ``field`` is submitted to.

    A bound casilla is shown by its box, but what the filer may replace is the
    value of the binding that feeds it, so an override is addressed to that
    binding; every other field is edited at its own address.
    """
    if (
        isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.editability in _OVERRIDE_EDITABILITIES
        and field.bindings
    ):
        return ModeloFormBindingAddressV1(binding_id=field.bindings[0].binding_id)
    return field.address


class ModeloFormCounts(_FormModel):
    """How many fields stand in each origin, for a section, a page or the form."""

    total: int = Field(ge=0)
    needs_input: int = Field(ge=0)
    entered: int = Field(ge=0)
    imported: int = Field(ge=0)
    calculated: int = Field(ge=0)
    overridden: int = Field(ge=0)
    default_to_confirm: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    blocked: int = Field(ge=0)


class ModeloFormFieldBlock(_FormModel):
    """One field on its own line."""

    kind: Literal["field"] = "field"
    id: str
    field: ModeloFormField


class ModeloFormGridColumn(_FormModel):
    """One official column heading."""

    key: str
    heading: ModeloFormText


class ModeloFormGridCell(_FormModel):
    """One grid cell: a field, the design's literal, or a blank where the paper form has no box."""

    kind: FormCellKind
    field: ModeloFormField | None = None
    literal: str | None = None


class ModeloFormGridRow(_FormModel):
    """One official printed row; ``cells`` align with the grid's columns."""

    key: str
    heading: ModeloFormText
    cells: tuple[ModeloFormGridCell, ...]


class ModeloFormGridBlock(_FormModel):
    """Official rows and columns, like the printed form's base, rate and amount lines."""

    kind: Literal["grid"] = "grid"
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    rows: tuple[ModeloFormGridRow, ...]


class ModeloFormRepeatingRow(_FormModel):
    """One detail row's values, aligned with the group's columns."""

    index: int = Field(ge=1)
    values: tuple[ModeloFormScalar, ...]


class ModeloFormRepeatingBlock(_FormModel):
    """An open set of detail rows, never flattened into single boxes.

    ``rows_known`` is false when this form cannot read the rows from their
    source, so an empty ``rows`` is never mistaken for a group with no rows.
    """

    kind: Literal["repeating"] = "repeating"
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    #: The casilla each column shows, aligned with ``columns``; ``None`` for a column no casilla owns.
    column_casilla_ids: tuple[str | None, ...]
    column_data_types: tuple[str, ...]
    min_rows: int = Field(ge=0)
    max_rows: int | None
    rows_known: bool
    rows: tuple[ModeloFormRepeatingRow, ...]


class ModeloFormBindingInputsBlock(_FormModel):
    """Values the filer supplies that no casilla owns."""

    kind: Literal["binding_inputs"] = "binding_inputs"
    id: str
    fields: tuple[ModeloFormField, ...]


type ModeloFormBlock = Annotated[
    ModeloFormFieldBlock | ModeloFormGridBlock | ModeloFormRepeatingBlock | ModeloFormBindingInputsBlock,
    Field(discriminator="kind"),
]


class ModeloFormSection(_FormModel):
    """One apartado with its heading, ordered blocks and counts."""

    id: str
    heading: ModeloFormText
    official_heading: str | None
    blocks: tuple[ModeloFormBlock, ...]
    counts: ModeloFormCounts


class ModeloFormPage(_FormModel):
    """One official page, whether it applies to this filing, and its sections."""

    id: str
    heading: ModeloFormText
    official_ref: str | None
    condition: FormPageCondition
    #: ``True`` applies, ``False`` does not, ``None`` may not apply and cannot be decided from the data.
    applies: bool | None
    sections: tuple[ModeloFormSection, ...]
    counts: ModeloFormCounts


class ModeloFormUnplacedField(_FormModel):
    """A casilla the layout could not position, and why."""

    field: ModeloFormField
    reason: FormUnplacedReason | None


class ModeloFormAttention(StrEnum):
    """How much a finding asks of the filer."""

    #: It must be resolved before the declaration can be recorded as filed.
    BLOCKS = "blocks"
    #: A warning worth checking; it does not stop the filing.
    CHECK = "check"
    #: An explanation of what the calculation did; nothing to act on.
    INFO = "info"


EXPLANATORY_FINDING_MESSAGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        # A dependency on an earlier period scoped out because the filer
        # declared a later activity start: it says why a filing is not needed.
        "application.modelo.findings.cross_period_operator_declared_suppression",
        # A first-year Modelo 202 instalment scoped out by the activity start.
        "application.modelo.findings.cross_period_first_year_fractional_suppression",
        # An earlier filing admitted because it carries zero into this one.
        "application.modelo.findings.cross_period_zero_value_previous_filing",
        # An earlier Modelo 111 admitted because it declares no withholdings.
        "application.modelo.findings.cross_period_m111_no_retenciones",
        # Source modelos this taxpayer does not file.
        "application.modelo.findings.cross_period_modelo_not_applicable.message",
    }
)
"""The advisory findings that explain a decision the verification already made.

Each is produced by the cross-period clean-state verification when a
dependency is admitted or scoped out on explicit evidence: the finding tells
the filer why, and asks nothing of them. Advisories outside this set, such as
a possibly missed reduction or a total resting on a non-official local chain,
remain worth checking. The set is closed and keyed on the producers' catalogue
keys; a key it names that no catalogue carries fails its guard test.
"""


def finding_attention(finding: ModeloVerificationFinding) -> ModeloFormAttention:
    """Classify one verification finding on the filer's attention scale.

    A blocking finding blocks. A warning is worth checking, unless it is an
    advisory the verification emits to explain an admitted or scoped-out
    dependency, which is for information only.
    """
    if finding.severity is ModeloVerificationFindingSeverity.BLOCKING:
        return ModeloFormAttention.BLOCKS
    if (
        finding.kind is ModeloVerificationFindingKind.ADVISORY
        and finding.message_locale_key in EXPLANATORY_FINDING_MESSAGE_KEYS
    ):
        return ModeloFormAttention.INFO
    return ModeloFormAttention.CHECK


def _issue_attention(data: dict[str, Any]) -> ModeloFormAttention:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's attention is derived from its finding")
    return finding_attention(finding)


class ModeloFormIssue(_FormModel):
    """One finding of the current calculation's latest verification, with the box it concerns.

    The finding keeps its catalogue key and typed facts, so the frontend renders
    it in the filer's language; ``box`` is the official box number when the
    finding names a casilla the form shows. ``attention`` places the finding on
    the filer's scale and is derived from the finding when not given.
    """

    finding: ModeloVerificationFinding
    box: str | None = None
    attention: ModeloFormAttention = Field(default_factory=_issue_attention)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _attention_matches_the_finding(self) -> ModeloFormIssue:
        if self.attention is not finding_attention(self.finding):
            raise ValueError("an issue's attention must be the one its finding classifies to")
        return self


class ModeloFormAeatData(_FormModel):
    """The AEAT tax data (borrador) the current calculation took values from.

    Recalculating replays the imported snapshot, so its values keep feeding the
    declaration until it is replaced. ``imported_at`` is when the data was
    imported, or ``None`` when this read could not open the snapshot's record;
    ``binding_ids`` are the bindings whose values the snapshot supplied.
    """

    snapshot_id: str = Field(min_length=1)
    imported_at: datetime | None = None
    binding_ids: tuple[BindingId, ...] = ()


class ModeloFormDeadline(_FormModel):
    """The last day of the voluntary filing window for this declaration.

    ``nominal_closes_on`` is the date the registry declares; ``closes_on`` is
    the date after the business-day shift, and ``holiday_coverage`` says which
    holidays that shift accounted for, so a date computed without the filer's
    regional holidays is never passed off as final. Exactly one of
    ``days_remaining`` and ``days_overdue`` is set, counted from
    ``reference_on``.
    """

    closes_on: date
    nominal_closes_on: date
    holiday_coverage: DeadlineHolidayCoverage
    reference_on: date
    days_remaining: int | None = Field(default=None, ge=0)
    days_overdue: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_posture(self) -> ModeloFormDeadline:
        if (self.days_remaining is None) == (self.days_overdue is None):
            raise ValueError("a deadline is either still open or passed, never both or neither")
        return self


class ModeloFormResultDirection(StrEnum):
    """Which way the declaration's result settles, as its official design declares it."""

    TO_PAY = "to_pay"
    TO_REFUND = "to_refund"
    TO_CARRY_FORWARD = "to_carry_forward"
    NIL = "nil"
    #: Nothing declares how this result settles, or it has no value yet.
    UNKNOWN = "unknown"


class ModeloFormResult(_FormModel):
    """The box that settles the declaration, its value and its direction.

    ``disposition`` is the official "tipo de declaración" code the result
    implies before any election the filer makes when filing; the direction is
    read from it and from nothing else, never from the sign alone. When the
    registry names the settlement box but declares no such rule, the direction
    is unknown. ``election_may_change`` says the filer's refund election can
    still turn a carried credit into a refund.
    """

    casilla_id: CasillaId
    box: str | None
    value: Decimal | None
    direction: ModeloFormResultDirection
    disposition: ResultDisposition | None = None
    election_may_change: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _direction_needs_a_value(self) -> ModeloFormResult:
        if self.value is None and self.direction is not ModeloFormResultDirection.UNKNOWN:
            raise ValueError("a result without a value has no direction")
        return self


class ModeloFormFiling(_FormModel):
    """The declaration is recorded in Cadrumo as filed; nothing was sent to AEAT from here."""

    #: When the filing was recorded, or ``None`` when the revision does not say.
    recorded_at: datetime | None = None


class ModeloFormEditClosure(StrEnum):
    """Why nothing on the form may be edited, whatever the edit admission says."""

    #: The declaration is recorded as filed; changing it starts a correction
    #: (a complementaria or a rectificativa), never an edit in place.
    RECORDED_AS_FILED = "recorded_as_filed"


class ModeloWorkForm(_FormModel):
    """The editor form of one work target in one language."""

    modelo: ModeloCode
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    work_unit_id: str
    calculation_revision_id: str | None
    language: OutputLanguage
    layout_provenance: ModeloFormLayoutProvenance
    inspection_reason: ModeloFormInspectionReason | None = None
    seed_source: FormLayoutSeedSource | None = None
    pages: tuple[ModeloFormPage, ...]
    working_figures: tuple[ModeloFormField, ...] = ()
    unplaced: tuple[ModeloFormUnplacedField, ...] = ()
    result_addresses: tuple[CasillaId, ...] = ()
    counts: ModeloFormCounts
    progress: ModeloWorkProgress
    operator_entries_known: bool
    edit_admitted: bool
    #: The current calculation's latest verification verdict; ``None`` when it has not been verified.
    verification: VerificationCompletenessStatus | None = None
    #: That verification's findings, blocking first, whether or not they name a casilla.
    issues: tuple[ModeloFormIssue, ...] = ()
    #: The settlement box and its direction; ``None`` when the registry names no settlement box.
    result: ModeloFormResult | None = None
    #: The last day to file; ``None`` when the registry declares no window for this declaration.
    deadline: ModeloFormDeadline | None = None
    #: The AEAT tax data the current calculation replayed; ``None`` when it replayed none.
    aeat_data: ModeloFormAeatData | None = None
    #: Set when the declaration is recorded as filed.
    filing: ModeloFormFiling | None = None
    #: Why nothing may be edited, when something other than the admission closes the form.
    edit_closure: ModeloFormEditClosure | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _inspection_reason_matches_provenance(self) -> ModeloWorkForm:
        inspecting = self.layout_provenance is ModeloFormLayoutProvenance.INSPECTION_ONLY
        if inspecting != (self.inspection_reason is not None):
            raise ValueError("an inspection reason belongs to, and only to, an inspection-only form")
        if self.edit_closure is not None and self.edit_admitted:
            raise ValueError("a form closed to editing admits no edit")
        return self

    def fields(self) -> tuple[ModeloFormField, ...]:
        """Return every field once, in reading order: pages, then working figures, then unplaced."""
        collected: list[ModeloFormField] = []
        for page in self.pages:
            for section in page.sections:
                collected.extend(section_fields(section))
        collected.extend(self.working_figures)
        collected.extend(item.field for item in self.unplaced)
        return tuple(collected)


def section_fields(section: ModeloFormSection) -> tuple[ModeloFormField, ...]:
    """Return a section's fields in reading order, grid rows left to right."""
    collected: list[ModeloFormField] = []
    for block in section.blocks:
        if isinstance(block, ModeloFormFieldBlock):
            collected.append(block.field)
        elif isinstance(block, ModeloFormGridBlock):
            collected.extend(cell.field for row in block.rows for cell in row.cells if cell.field is not None)
        elif isinstance(block, ModeloFormBindingInputsBlock):
            collected.extend(block.fields)
    return tuple(collected)


__all__ = [
    "ABSENT_FROM_ADMISSION",
    "EXPLANATORY_FINDING_MESSAGE_KEYS",
    "ModeloFormAddressV1",
    "ModeloFormAeatData",
    "ModeloFormAttention",
    "ModeloFormBinding",
    "ModeloFormBindingAddressV1",
    "ModeloFormBindingInputsBlock",
    "ModeloFormBlock",
    "ModeloFormBlocker",
    "ModeloFormCasillaAddressV1",
    "ModeloFormCounts",
    "ModeloFormDeadline",
    "ModeloFormEarlierFiling",
    "ModeloFormEditClosure",
    "ModeloFormEditability",
    "ModeloFormField",
    "ModeloFormFieldBlock",
    "ModeloFormFiling",
    "ModeloFormGridBlock",
    "ModeloFormGridCell",
    "ModeloFormGridColumn",
    "ModeloFormGridRow",
    "ModeloFormInspectionReason",
    "ModeloFormIssue",
    "ModeloFormLayoutProvenance",
    "ModeloFormOrigin",
    "ModeloFormPage",
    "ModeloFormRepeatingBlock",
    "ModeloFormRepeatingRow",
    "ModeloFormResult",
    "ModeloFormResultDirection",
    "ModeloFormScalar",
    "ModeloFormSection",
    "ModeloFormText",
    "ModeloFormTextDisclosure",
    "ModeloFormUnplacedField",
    "ModeloFormValueSource",
    "ModeloWorkForm",
    "address_key",
    "edit_address",
    "finding_attention",
    "section_fields",
]
