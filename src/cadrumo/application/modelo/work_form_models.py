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
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.ids import BindingId, FormulaId, LegalRefId, RevisionId
from ...domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormLayoutSeedSource,
    FormPageCondition,
    FormUnplacedReason,
)
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints
from ...domain.modelos.codes import ModeloCode
from .calculation_report import CalculationReportRowRole
from .source_policy import SourcePolicyV1
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
    required: bool
    role: CalculationReportRowRole | None = None
    bindings: tuple[ModeloFormBinding, ...] = ()
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

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _inspection_reason_matches_provenance(self) -> ModeloWorkForm:
        inspecting = self.layout_provenance is ModeloFormLayoutProvenance.INSPECTION_ONLY
        if inspecting != (self.inspection_reason is not None):
            raise ValueError("an inspection reason belongs to, and only to, an inspection-only form")
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
    "ModeloFormAddressV1",
    "ModeloFormBinding",
    "ModeloFormBindingAddressV1",
    "ModeloFormBindingInputsBlock",
    "ModeloFormBlock",
    "ModeloFormBlocker",
    "ModeloFormCasillaAddressV1",
    "ModeloFormCounts",
    "ModeloFormEditability",
    "ModeloFormField",
    "ModeloFormFieldBlock",
    "ModeloFormGridBlock",
    "ModeloFormGridCell",
    "ModeloFormGridColumn",
    "ModeloFormGridRow",
    "ModeloFormInspectionReason",
    "ModeloFormLayoutProvenance",
    "ModeloFormOrigin",
    "ModeloFormPage",
    "ModeloFormRepeatingBlock",
    "ModeloFormRepeatingRow",
    "ModeloFormScalar",
    "ModeloFormSection",
    "ModeloFormText",
    "ModeloFormTextDisclosure",
    "ModeloFormUnplacedField",
    "ModeloWorkForm",
    "address_key",
    "section_fields",
]
