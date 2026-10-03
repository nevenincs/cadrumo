"""Strict public projection of one declaration's workbench reads.

The workbench form is an owner read model: a password-authenticated human CLI
or TUI session may receive it through the verified local transport, and no
agent or off-host destination may. Its canonical models are not all shaped for
a registered operation result -- a modelo code and a period customise their
core schema, a field's scalar value reads a decimal back as text through strict
JSON, a verification finding serialises its facts -- so exactly those nodes are
mirrored here, through the shared public-mirror engine, and restored afterwards.

Projection proves itself: the restored canonical read must equal the original,
so a mirror that loses a type, a precision or a field fails before anything is
stored. The canonical models' own excluded fields are an empty, reviewed
inventory; a new excluded field fails the projection until it is reviewed.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
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
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ..operations.public_mirror import (
    PublicScalarValueV1,
    excluded_canonical_fields,
    project_public_mirror,
    restore_public_mirror,
)
from ..operations.public_period import PublicPeriod
from ..workbench_generation_modelo_contracts import PublicCasillaConstraints, PublicModeloVerificationFinding
from .calculation_report import CalculationReportRowRole
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_models import ModeloEditAdmittedV1, ModeloEditRefusedV1
from .source_policy import SourceFamily
from .work_form_models import (
    ModeloFormAddressV1,
    ModeloFormAeatData,
    ModeloFormAttention,
    ModeloFormBinding,
    ModeloFormBlocker,
    ModeloFormCalculationNote,
    ModeloFormCounts,
    ModeloFormDeadline,
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormExport,
    ModeloFormFiling,
    ModeloFormGridColumn,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormRateUnit,
    ModeloFormResultDirection,
    ModeloFormText,
)
from .work_form_service import ModeloWorkFormLoadV1
from .work_review import ModeloWorkProgress
from .workbench_read import ModeloWorkbenchFormReadV1


class PublicModeloFormEarlierFiling(BaseModel):
    """Typed local-human workbench view of ModeloFormEarlierFiling."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    period: PublicPeriod


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


class PublicModeloFormResult(BaseModel):
    """Typed local-human workbench view of ModeloFormResult; the value keeps its exact decimal text."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    box: str | None
    value: str | None
    direction: ModeloFormResultDirection
    disposition: ResultDisposition | None
    election_may_change: bool


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


class PublicModeloFormFieldBlock(BaseModel):
    """Typed local-human workbench view of ModeloFormFieldBlock."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["field"]
    id: str
    field: PublicModeloFormField


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
    | PublicModeloFormBindingInputsBlock,
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


class PublicModeloWorkForm(BaseModel):
    """Typed local-human workbench view of ModeloWorkForm."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: PublicPeriod
    registry_revision_id: str
    work_unit_id: str
    calculation_revision_id: str | None
    language: OutputLanguage
    layout_provenance: ModeloFormLayoutProvenance
    inspection_reason: ModeloFormInspectionReason | None
    seed_source: FormLayoutSeedSource | None
    pages: tuple[PublicModeloFormPage, ...]
    working_figures: tuple[PublicModeloFormField, ...]
    unplaced: tuple[PublicModeloFormUnplacedField, ...]
    result_addresses: tuple[CasillaId, ...]
    counts: ModeloFormCounts
    progress: ModeloWorkProgress
    operator_entries_known: bool
    edit_admitted: bool
    verification: VerificationCompletenessStatus | None
    issues: tuple[PublicModeloFormIssue, ...]
    calculation_notes: tuple[ModeloFormCalculationNote, ...]
    calculation_notes_held: bool
    result: PublicModeloFormResult | None
    deadline: ModeloFormDeadline | None
    aeat_data: ModeloFormAeatData | None
    filing: ModeloFormFiling | None
    last_export: ModeloFormExport | None
    edit_closure: ModeloFormEditClosure | None


class PublicModeloWorkFormLoadV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkFormLoadV1."""

    model_config = STRICT_FROZEN_CONFIG

    form: PublicModeloWorkForm
    verified: bool
    filed: bool


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
    nie_prefix_substitutions: tuple[tuple[str, str], ...]
    cif_digit_only_kinds: str
    cif_letter_only_kinds: str
    cif_letter_table: str


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
    calculation_revision_id: str | None
    verification_report_id: str | None
    asks_m303_evidence: bool
    asks_modelo_390: bool
    registry_revision_id: str
    tax_id_format: PublicSpanishTaxIdFormat

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


_REVIEWED_EXCLUDED_FIELDS: frozenset[tuple[type[BaseModel], str]] = frozenset[tuple[type[BaseModel], str]]()
"""No canonical workbench form field is excluded from its own serializer today."""


def _require_reviewed_exclusions() -> None:
    if excluded_canonical_fields(ModeloWorkFormLoadV1) != _REVIEWED_EXCLUDED_FIELDS:
        raise ValueError("workbench form excluded-field inventory changed")


def _project_form(load: ModeloWorkFormLoadV1) -> PublicModeloWorkFormLoadV1:
    projected = project_public_mirror(load, ModeloWorkFormLoadV1, PublicModeloWorkFormLoadV1)
    if not isinstance(projected, PublicModeloWorkFormLoadV1):
        raise TypeError("workbench form public projection failed")
    return projected


def _restore_form(public: PublicModeloWorkFormLoadV1) -> ModeloWorkFormLoadV1:
    restored = restore_public_mirror(public, ModeloWorkFormLoadV1, PublicModeloWorkFormLoadV1)
    if not isinstance(restored, ModeloWorkFormLoadV1):
        raise TypeError("workbench form canonical restoration failed")
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


def _restore(projection: ModeloWorkbenchFormProjectionV1) -> ModeloWorkbenchFormReadV1:
    baseline = projection.admitted_baseline
    admission = (
        ModeloEditAdmittedV1(baseline=baseline.to_baseline())
        if baseline is not None
        else cast(ModeloEditRefusedV1, projection.admission_refusal)
    )
    return ModeloWorkbenchFormReadV1(
        load=_restore_form(projection.form),
        admission=admission,
        calculation_revision_id=projection.calculation_revision_id,
        verification_report_id=projection.verification_report_id,
        asks_m303_evidence=projection.asks_m303_evidence,
        asks_modelo_390=projection.asks_modelo_390,
        registry_revision_id=projection.registry_revision_id,
        tax_id_format=_restore_tax_id_format(projection.tax_id_format),
    )


def project_modelo_workbench_form(
    profile_id: UUID, work_unit_id: str, read: ModeloWorkbenchFormReadV1
) -> ModeloWorkbenchFormProjectionV1:
    """Project one workbench read for its exact profile and prove nothing was lost."""
    _require_reviewed_exclusions()
    admission = read.admission
    projection = ModeloWorkbenchFormProjectionV1(
        result_version=1,
        profile_id=profile_id,
        work_unit_id=work_unit_id,
        form=_project_form(read.load),
        admitted_baseline=(
            ModeloEditApplyBaselineV1.from_baseline(admission.baseline)
            if isinstance(admission, ModeloEditAdmittedV1)
            else None
        ),
        admission_refusal=admission if isinstance(admission, ModeloEditRefusedV1) else None,
        calculation_revision_id=read.calculation_revision_id,
        verification_report_id=read.verification_report_id,
        asks_m303_evidence=read.asks_m303_evidence,
        asks_modelo_390=read.asks_modelo_390,
        registry_revision_id=read.registry_revision_id,
        tax_id_format=_project_tax_id_format(read.tax_id_format),
    )
    if _restore(projection) != read:
        raise ValueError("workbench form public projection changed canonical meaning")
    return projection


def restore_modelo_workbench_form(projection: ModeloWorkbenchFormProjectionV1) -> ModeloWorkbenchFormReadV1:
    """Rebuild the canonical workbench read and prove it projects back unchanged."""
    _require_reviewed_exclusions()
    restored = _restore(projection)
    if _project_form(restored.load) != projection.form:
        raise ValueError("workbench form public projection changed canonical meaning")
    return restored


__all__ = [
    "ModeloWorkbenchFormProjectionV1",
    "PublicModeloFormBindingInputsBlock",
    "PublicModeloFormEarlierFiling",
    "PublicModeloFormField",
    "PublicModeloFormFieldBlock",
    "PublicModeloFormGridBlock",
    "PublicModeloFormGridCell",
    "PublicModeloFormGridRow",
    "PublicModeloFormIssue",
    "PublicModeloFormPage",
    "PublicModeloFormPrintedRate",
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
    "project_modelo_workbench_form",
    "restore_modelo_workbench_form",
]
