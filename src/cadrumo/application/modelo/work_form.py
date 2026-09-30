"""Build the editor form of one modelo work target from the review and the declared layout.

:func:`build_modelo_work_form` is a pure join. It reads the canonical work
review for values and origins, the revision's declared form layout for pages,
sections, grids and placements, the registry snapshot for localized labels,
help, completeness and bindings, the current calculation revision for what the
filer explicitly cleared and for detail rows, and the edit admission's permitted
surface for what may be written. It derives no layout: a revision without a
usable declared layout becomes an inspection-only form that says why.

Classification is decided once, here, so every frontend shows the same states:

* the origin of each value -- entered, imported, calculated, needed, not
  applicable, cleared, or held without proof anyone entered it -- and
* the editability of each address -- typed, overridden with a reason, fixed at
  its source, corrected in the profile, calculated, or fixed by the design.

"Entered by the filer" is only ever claimed from the operator's own recorded
entries. A revision that predates them has an unknown operator record, and a
value it holds for a manual box is shown as one to confirm, never as entered.

The form is total: every casilla of the revision appears exactly once, on a
page, among the working figures, or in the unplaced list with its reason. A
layout that would drop or repeat a casilla is refused rather than rendered.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.modelo_localization import modelo_localization_source, resolve_modelo_localization
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormCellKind,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormPageCondition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
    FormSectionDefinition,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.filing.schema import ModeloValueKind
from ...domain.modelos.calculation_revision import CalculationRevision
from .calculation_report import CalculationReportRowRole, calculation_report_row_role
from .edit_models import (
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .source_policy import SourceOverridePolicy, source_policy
from .work_form_models import (
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormBindingInputsBlock,
    ModeloFormBlock,
    ModeloFormBlocker,
    ModeloFormCasillaAddressV1,
    ModeloFormCounts,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormRepeatingBlock,
    ModeloFormRepeatingRow,
    ModeloFormScalar,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloFormUnplacedField,
    ModeloWorkForm,
    section_fields,
)
from .work_review import ModeloWorkOriginAnomaly, ModeloWorkReview, ModeloWorkReviewCasilla

_SPANISH: Final[str] = OutputLanguage.ES.value
_INSPECTION_PAGE_ID: Final[str] = "inspection"
_INSPECTION_HEADING_LOCALE_KEY: Final[str] = "application.modelo.work_form.inspection_heading"
_BOX_LOCATOR_HELP: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^Casilla [\d-]+ del modelo \d+, ejercicios? [\d-]+( y siguientes)?\.$"),
    re.compile(r"^Box [\d-]+ of [Mm]odelo \d+, tax years? [\d-]+( onwards)?\.$"),
    re.compile(r"^Casella [\d-]+ del model \d+, exercicis? [\d-]+( i posteriors)?\.$"),
    re.compile(r"^A \d+-\w+ nyomtatvány [\d-]+\. (rovata|mezője), [\d-]+\. (adóév|és az azt követő adóévek)\.$"),
)
"""Help sentences that only say which box of which modelo and year a casilla is, in each language."""
_BINDING_DATA_TYPE: Final[Mapping[str, str]] = {
    "money": "money",
    "decimal": "decimal",
    "integer": "integer",
    "boolean": "boolean",
    "text": "text",
    "date": "date",
    "enum": "text",
}


class ModeloWorkFormLayoutError(ValueError):
    """A declared layout does not account for every casilla exactly once."""


class _FormContext:
    """Everything one form build reads, indexed once."""

    def __init__(
        self,
        *,
        review: ModeloWorkReview,
        snapshot: RegistrySnapshot,
        revision: CalculationRevision | None,
        permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None,
        entered_casilla_ids: frozenset[CasillaId] | None,
        overridden_binding_ids: frozenset[BindingId] | None,
        language: OutputLanguage,
    ) -> None:
        self.review = review
        self.language = language
        self.revision = revision
        self.rows: dict[str, ModeloWorkReviewCasilla] = {str(row.casilla_id): row for row in review.casillas}
        self.casillas: dict[str, CasillaDefinition] = {str(item.id): item for item in snapshot.revision.casillas}
        self.bindings: dict[str, BindingDefinition] = {str(item.id): item for item in snapshot.revision.bindings}
        manifest = snapshot.revision.completeness_manifest
        self.manifest: frozenset[str] = (
            frozenset() if manifest is None else frozenset(str(item.casilla_id) for item in manifest.casillas)
        )
        self.surface: dict[tuple[str, str], ModeloEditPermittedSurfaceEntryV1] | None = (
            None if permitted_surface is None else {_surface_key(entry): entry for entry in permitted_surface}
        )
        self.entered = entered_casilla_ids
        self.overridden = overridden_binding_ids
        self.cleared: frozenset[str] = frozenset(
            () if revision is None else (str(item) for item in revision.cleared_casilla_ids)
        )
        self.casilla_by_binding: dict[str, str] = {}
        for casilla in snapshot.revision.casillas:
            for binding_id in (casilla.binding, *casilla.alternate_bindings):
                if binding_id is not None:
                    self.casilla_by_binding.setdefault(str(binding_id), str(casilla.id))


def _surface_key(entry: ModeloEditPermittedSurfaceEntryV1) -> tuple[str, str]:
    if isinstance(entry, (ModeloEditWritableScalarSurfaceEntryV1, ModeloEditNonWritableScalarSurfaceEntryV1)):
        return ("casilla", str(entry.casilla_id))
    if isinstance(
        entry, (ModeloEditWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
    ):
        return ("binding", str(entry.binding_id))
    return (entry.kind, "")


def _localized(keys: tuple[str, ...], language: OutputLanguage) -> ModeloFormText | None:
    """Resolve a modelo catalogue chain and say which language actually served it."""
    source = modelo_localization_source(keys, locale=language.value)
    text = resolve_modelo_localization(keys, locale=language.value)
    if source is None or not text:
        return None
    served_locale = source[1]
    disclosure = (
        ModeloFormTextDisclosure.LOCALIZED
        if served_locale == language.value
        else ModeloFormTextDisclosure.SPANISH_FALLBACK
    )
    return ModeloFormText(text=text, disclosure=disclosure)


def _heading(key: str, official: str | None, technical: str, language: OutputLanguage) -> ModeloFormText:
    """Resolve a layout heading: the translation, then Spanish, then the design's words, then a name."""
    translated = lookup_translation(key, locale=language.value)
    if translated:
        return ModeloFormText(text=translated, disclosure=ModeloFormTextDisclosure.LOCALIZED)
    spanish = lookup_translation(key, locale=_SPANISH)
    if spanish:
        disclosure = (
            ModeloFormTextDisclosure.LOCALIZED
            if language is OutputLanguage.ES
            else ModeloFormTextDisclosure.SPANISH_FALLBACK
        )
        return ModeloFormText(text=spanish, disclosure=disclosure)
    if official:
        return ModeloFormText(text=official, disclosure=ModeloFormTextDisclosure.OFFICIAL_SPANISH)
    return ModeloFormText(text=technical, disclosure=ModeloFormTextDisclosure.TECHNICAL)


def _help(casilla: CasillaDefinition, label: str, language: OutputLanguage) -> str | None:
    """Return the casilla's help unless it only restates the label or names the box."""
    keys = tuple(f"{key.removesuffix('.label')}.help" for key in casilla.localization_keys)
    text = resolve_modelo_localization(keys, locale=language.value)
    if not text:
        return None
    normalized = _normalized(text)
    if normalized == _normalized(label) or any(pattern.match(text.strip()) for pattern in _BOX_LOCATOR_HELP):
        return None
    return text


def _normalized(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text).strip().casefold()


def _box(casilla: CasillaDefinition | None, placement: FormPlacementDefinition | None) -> str | None:
    """Return the official printed box number, never a semantic id."""
    if placement is not None and placement.box_number is not None:
        return placement.box_number
    if casilla is not None:
        if casilla.form_number is not None:
            return casilla.form_number
        if casilla.number.isdigit():
            return casilla.number
    return None


def _bindings(row: ModeloWorkReviewCasilla) -> tuple[ModeloFormBinding, ...]:
    return tuple(
        ModeloFormBinding(binding_id=origin.binding_id, policy=source_policy(origin.source), resolved=origin.resolved)
        for origin in row.concrete_bindings
    )


def _casilla_origin(row: ModeloWorkReviewCasilla, context: _FormContext, *, required: bool) -> ModeloFormOrigin:
    """Classify where one casilla's value stands; first match wins."""
    casilla_id = str(row.casilla_id)
    kind = row.declared_input_kind
    empty = row.realised_kind is ModeloValueKind.EMPTY
    if row.absent_by_design:
        return ModeloFormOrigin.NOT_APPLICABLE
    overridden_binding = context.overridden is not None and any(
        str(origin.binding_id) in context.overridden for origin in row.concrete_bindings
    )
    if kind is InputKind.BOUND and overridden_binding:
        return ModeloFormOrigin.OVERRIDES_SOURCE
    if row.origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE:
        return ModeloFormOrigin.OVERRIDES_SOURCE
    if kind is InputKind.COMPUTED:
        if not empty:
            return ModeloFormOrigin.CALCULATED
        if context.review.calculation_revision_id is None:
            return ModeloFormOrigin.NOT_CALCULATED_YET
        return ModeloFormOrigin.CALCULATION_FAILED
    if kind in {InputKind.INFORMATIONAL, InputKind.PROJECTION_ONLY}:
        return ModeloFormOrigin.INFORMATIONAL
    if kind is InputKind.BOUND:
        return ModeloFormOrigin.NOT_IMPORTED_YET if empty else ModeloFormOrigin.IMPORTED
    if casilla_id in context.cleared:
        return ModeloFormOrigin.CLEARED
    if context.entered is not None and casilla_id in context.entered:
        return ModeloFormOrigin.ENTERED
    if empty:
        return ModeloFormOrigin.NEEDS_INPUT if required else ModeloFormOrigin.OPTIONAL_EMPTY
    return ModeloFormOrigin.DEFAULT_TO_CONFIRM


def _casilla_editability(
    row: ModeloWorkReviewCasilla, context: _FormContext
) -> tuple[ModeloFormEditability, str | None]:
    """Classify what may be done about one casilla's value, with the admission's reason when read-only."""
    kind = row.declared_input_kind
    if kind is InputKind.COMPUTED:
        return ModeloFormEditability.CALCULATED, None
    if kind in {InputKind.INFORMATIONAL, InputKind.PROJECTION_ONLY}:
        return ModeloFormEditability.INFORMATIONAL, None
    if kind is InputKind.BOUND:
        return _bound_editability(row, context)
    if context.surface is None:
        return ModeloFormEditability.NO_ADMISSION, None
    entry = context.surface.get(("casilla", str(row.casilla_id)))
    if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1):
        return ModeloFormEditability.EDITABLE_VALUE, None
    if isinstance(entry, ModeloEditNonWritableScalarSurfaceEntryV1):
        return ModeloFormEditability.NOT_WRITABLE, entry.reason.value
    return ModeloFormEditability.NOT_WRITABLE, "absent_from_admission"


def _bound_editability(row: ModeloWorkReviewCasilla, context: _FormContext) -> tuple[ModeloFormEditability, str | None]:
    """Classify a bound casilla by its primary source's policy and the admission."""
    if not row.concrete_bindings:
        return ModeloFormEditability.SOURCE_POLICY_UNDECIDED, None
    primary = row.concrete_bindings[0]
    policy = source_policy(primary.source).override_policy
    fixed = {
        SourceOverridePolicy.FIX_AT_SOURCE: ModeloFormEditability.LOCKED_SOURCE,
        SourceOverridePolicy.EDIT_AT_HOME: ModeloFormEditability.EDIT_AT_PROFILE,
        SourceOverridePolicy.FIXED: ModeloFormEditability.DESIGN_CONSTANT,
        SourceOverridePolicy.UNDECIDED: ModeloFormEditability.SOURCE_POLICY_UNDECIDED,
    }.get(policy)
    if fixed is not None:
        return fixed, None
    if context.surface is None:
        return ModeloFormEditability.NO_ADMISSION, None
    entry = context.surface.get(("binding", str(primary.binding_id)))
    if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
        editable = (
            ModeloFormEditability.OVERRIDABLE_SOURCE
            if policy is SourceOverridePolicy.OVERRIDE_WITH_REASON
            else ModeloFormEditability.EDITABLE_OVERRIDE
        )
        return editable, None
    if isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1):
        return ModeloFormEditability.NOT_WRITABLE, entry.reason.value
    return ModeloFormEditability.NOT_WRITABLE, "absent_from_admission"


def _casilla_field(
    casilla_id: str,
    context: _FormContext,
    placement: FormPlacementDefinition | None,
    also_appears_on: tuple[str, ...] = (),
) -> ModeloFormField:
    """Build one classified casilla field."""
    row = context.rows.get(casilla_id)
    casilla = context.casillas.get(casilla_id)
    if row is None or casilla is None:
        raise ModeloWorkFormLayoutError(f"the layout places casilla {casilla_id!r}, which the revision does not define")
    label = _localized(casilla.localization_keys, context.language) or ModeloFormText(
        text=casilla_id, disclosure=ModeloFormTextDisclosure.TECHNICAL
    )
    required = casilla_id in context.manifest or casilla.required
    editability, reason = _casilla_editability(row, context)
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=row.casilla_id),
        box=_box(casilla, placement),
        label=label,
        help=_help(casilla, label.text, context.language),
        data_type=str(row.data_type),
        value=row.value,
        origin=_casilla_origin(row, context, required=required),
        editability=editability,
        not_writable_reason=reason,
        required=required,
        role=_role(row),
        bindings=_bindings(row),
        formula_id=row.formula_id,
        formula_operands=() if row.concrete_formula is None else row.concrete_formula.operand_refs,
        blockers=tuple(ModeloFormBlocker(code=blocker.native_code) for blocker in row.blocked_by),
        constraints=row.constraints,
        legal_refs=row.legal_refs,
        also_appears_on=also_appears_on,
    )


def _role(row: ModeloWorkReviewCasilla) -> CalculationReportRowRole | None:
    try:
        return calculation_report_row_role(declared_input_kind=row.declared_input_kind, semantic_role=row.semantic_role)
    except ValueError:
        return None


def _binding_field(binding_id: str, context: _FormContext) -> ModeloFormField:
    """Build one field for a binding input no casilla owns."""
    binding = context.bindings.get(binding_id)
    if binding is None:
        raise ModeloWorkFormLayoutError(f"the layout places binding {binding_id!r}, which the revision does not define")
    owner = context.casilla_by_binding.get(binding_id)
    owner_casilla = None if owner is None else context.casillas.get(owner)
    label = (
        None if owner_casilla is None else _localized(owner_casilla.localization_keys, context.language)
    ) or ModeloFormText(text=binding_id, disclosure=ModeloFormTextDisclosure.TECHNICAL)
    raw = None if context.revision is None else context.revision.binding_overrides.get(binding.id)
    policy = source_policy(binding.source)
    editability, reason = _binding_input_editability(binding_id, policy.override_policy, context)
    overridden = context.overridden is not None and binding_id in context.overridden
    origin = (
        ModeloFormOrigin.ENTERED
        if overridden
        else (
            ModeloFormOrigin.OPTIONAL_EMPTY
            if raw is None
            else (
                ModeloFormOrigin.IMPORTED
                if binding.source is not BindingSourceKind.MANUAL_INPUT
                else ModeloFormOrigin.DEFAULT_TO_CONFIRM
            )
        )
    )
    return ModeloFormField(
        address=ModeloFormBindingAddressV1(binding_id=binding.id),
        box=None,
        label=label,
        help=None,
        data_type=_BINDING_DATA_TYPE.get(binding.value.data_type.value, "text"),
        value=raw,
        origin=origin,
        editability=editability,
        not_writable_reason=reason,
        required=False,
        bindings=(ModeloFormBinding(binding_id=binding.id, policy=policy, resolved=raw is not None),),
        legal_refs=tuple(binding.legal_refs),
    )


def _binding_input_editability(
    binding_id: str, policy: SourceOverridePolicy, context: _FormContext
) -> tuple[ModeloFormEditability, str | None]:
    if policy is SourceOverridePolicy.FIX_AT_SOURCE:
        return ModeloFormEditability.LOCKED_SOURCE, None
    if policy is SourceOverridePolicy.UNDECIDED:
        return ModeloFormEditability.SOURCE_POLICY_UNDECIDED, None
    if context.surface is None:
        return ModeloFormEditability.NO_ADMISSION, None
    entry = context.surface.get(("binding", binding_id))
    if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
        editable = (
            ModeloFormEditability.OVERRIDABLE_SOURCE
            if policy is SourceOverridePolicy.OVERRIDE_WITH_REASON
            else ModeloFormEditability.EDITABLE_OVERRIDE
        )
        return editable, None
    if isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1):
        return ModeloFormEditability.NOT_WRITABLE, entry.reason.value
    return ModeloFormEditability.NOT_WRITABLE, "absent_from_admission"


def _counts(fields: Iterable[ModeloFormField]) -> ModeloFormCounts:
    tallies = {
        "total": 0,
        "needs_input": 0,
        "entered": 0,
        "imported": 0,
        "calculated": 0,
        "overridden": 0,
        "default_to_confirm": 0,
        "not_applicable": 0,
        "blocked": 0,
    }
    by_origin = {
        ModeloFormOrigin.NEEDS_INPUT: "needs_input",
        ModeloFormOrigin.ENTERED: "entered",
        ModeloFormOrigin.IMPORTED: "imported",
        ModeloFormOrigin.CALCULATED: "calculated",
        ModeloFormOrigin.OVERRIDES_SOURCE: "overridden",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "default_to_confirm",
        ModeloFormOrigin.NOT_APPLICABLE: "not_applicable",
    }
    for field in fields:
        tallies["total"] += 1
        bucket = by_origin.get(field.origin)
        if bucket is not None:
            tallies[bucket] += 1
        if field.blockers:
            tallies["blocked"] += 1
    return ModeloFormCounts(**tallies)


def _numeric(value: ModeloFormScalar) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (Decimal, int)):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None


def _page_applies(
    page: FormPageDefinition, context: _FormContext, sections: tuple[ModeloFormSection, ...]
) -> bool | None:
    """Decide from declared facts alone whether a page applies; ``None`` when the data cannot say."""
    if page.condition is FormPageCondition.ALWAYS:
        return True
    if page.condition is FormPageCondition.PERIOD_RESTRICTED:
        return context.review.period.registry_token in page.condition_periods
    if page.condition is FormPageCondition.REQUIRES_POSITIVE_CASILLA and page.condition_casilla_id is not None:
        row = context.rows.get(str(page.condition_casilla_id))
        amount = None if row is None else _numeric(row.value)
        return None if amount is None else amount > 0
    has_value = any(
        field.origin in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.IMPORTED, ModeloFormOrigin.OVERRIDES_SOURCE}
        for section in sections
        for field in section_fields(section)
    )
    return True if has_value else None


class _LayoutWalk:
    """Turn a declared layout into form pages while accounting for every placement."""

    def __init__(self, layout: FormLayoutDefinition, context: _FormContext) -> None:
        self.layout = layout
        self.context = context
        self.placements: dict[str, FormPlacementDefinition] = {str(item.casilla_id): item for item in layout.placements}
        self.aliases: dict[str, tuple[str, ...]] = {
            str(item.casilla_id): tuple(alias.official_ref or alias.page_id for alias in item.aliases)
            for item in layout.placements
        }
        self.seen: set[str] = set()

    def casilla(self, casilla_id: str) -> ModeloFormField:
        if casilla_id in self.seen:
            raise ModeloWorkFormLayoutError(f"the layout places casilla {casilla_id!r} more than once")
        placement = self.placements.get(casilla_id)
        if placement is None or placement.kind is not FormPlacementKind.ON_FORM:
            raise ModeloWorkFormLayoutError(f"casilla {casilla_id!r} sits on a page without an on-form placement")
        self.seen.add(casilla_id)
        return _casilla_field(casilla_id, self.context, placement, self.aliases.get(casilla_id, ()))

    def page(self, page: FormPageDefinition) -> ModeloFormPage:
        language = self.context.language
        sections = tuple(self.section(page.id, section) for section in page.sections)
        return ModeloFormPage(
            id=page.id,
            heading=_heading(page.heading_key, page.official_heading, page.official_ref or page.id, language),
            official_ref=page.official_ref,
            condition=page.condition,
            applies=_page_applies(page, self.context, sections),
            sections=sections,
            counts=_counts(field for section in sections for field in section_fields(section)),
        )

    def section(self, page_id: str, section: FormSectionDefinition) -> ModeloFormSection:
        blocks = tuple(self.block(block) for block in section.blocks)
        form_section = ModeloFormSection(
            id=f"{page_id}.{section.id}",
            heading=_heading(section.heading_key, section.official_heading, section.id, self.context.language),
            official_heading=section.official_heading,
            blocks=blocks,
            counts=_counts(()),
        )
        return form_section.model_copy(update={"counts": _counts(section_fields(form_section))})

    def block(
        self, block: FormFieldBlock | FormGridBlock | FormRepeatingGroupBlock | FormBindingInputsBlock
    ) -> ModeloFormBlock:
        language = self.context.language
        if isinstance(block, FormFieldBlock):
            field = (
                self.casilla(str(block.casilla_id))
                if block.casilla_id is not None
                else _binding_field(str(block.binding_id), self.context)
            )
            return ModeloFormFieldBlock(id=block.id, field=field)
        if isinstance(block, FormGridBlock):
            columns = tuple(
                ModeloFormGridColumn(
                    key=column.key, heading=_heading(column.heading_key, column.official_heading, column.key, language)
                )
                for column in block.columns
            )
            rows = tuple(
                ModeloFormGridRow(
                    key=row.key,
                    heading=_heading(row.heading_key, row.official_heading, row.key, language),
                    cells=tuple(
                        self.cell(cell.kind, cell.casilla_id, cell.binding_id, cell.literal) for cell in row.cells
                    ),
                )
                for row in block.rows
            )
            return ModeloFormGridBlock(id=block.id, columns=columns, rows=rows)
        if isinstance(block, FormRepeatingGroupBlock):
            return self.repeating(block)
        return ModeloFormBindingInputsBlock(
            id=block.id, fields=tuple(_binding_field(str(binding_id), self.context) for binding_id in block.binding_ids)
        )

    def cell(
        self, kind: FormCellKind, casilla_id: CasillaId | None, binding_id: BindingId | None, literal: str | None
    ) -> ModeloFormGridCell:
        if kind is FormCellKind.CASILLA and casilla_id is not None:
            return ModeloFormGridCell(kind=kind, field=self.casilla(str(casilla_id)))
        if kind is FormCellKind.BINDING_INPUT and binding_id is not None:
            return ModeloFormGridCell(kind=kind, field=_binding_field(str(binding_id), self.context))
        return ModeloFormGridCell(kind=kind, literal=literal)

    def repeating(self, block: FormRepeatingGroupBlock) -> ModeloFormRepeatingBlock:
        language = self.context.language
        columns = tuple(
            ModeloFormGridColumn(
                key=column.key, heading=_heading(column.heading_key, column.official_heading, column.key, language)
            )
            for column in block.columns
        )
        column_casillas = tuple(
            None if column.casilla_id is None else str(column.casilla_id) for column in block.columns
        )
        for casilla_id in column_casillas:
            if casilla_id is not None and casilla_id not in self.seen:
                placement = self.placements.get(casilla_id)
                if placement is not None and placement.kind is FormPlacementKind.ON_FORM:
                    self.seen.add(casilla_id)
        data_types = tuple(
            "text"
            if casilla_id is None or casilla_id not in self.context.rows
            else str(self.context.rows[casilla_id].data_type)
            for casilla_id in column_casillas
        )
        return ModeloFormRepeatingBlock(
            id=block.id,
            columns=columns,
            column_data_types=data_types,
            min_rows=block.min_rows,
            max_rows=block.max_rows,
            rows_known=block.row_source is FormRepeatingRowSource.EXPORT_RECORD and self.context.revision is not None,
            rows=self.repeating_rows(block, column_casillas),
        )

    def repeating_rows(
        self, block: FormRepeatingGroupBlock, column_casillas: tuple[str | None, ...]
    ) -> tuple[ModeloFormRepeatingRow, ...]:
        revision = self.context.revision
        if revision is None or block.row_source is not FormRepeatingRowSource.EXPORT_RECORD:
            return ()
        by_row: dict[int, dict[str, Decimal]] = {}
        for (casilla_id, row_index), amount in revision.row_casilla_values.items():
            if str(casilla_id) in column_casillas:
                by_row.setdefault(row_index, {})[str(casilla_id)] = amount
        return tuple(
            ModeloFormRepeatingRow(
                index=index,
                values=tuple(None if casilla_id is None else values.get(casilla_id) for casilla_id in column_casillas),
            )
            for index, values in sorted(by_row.items())
        )


def build_modelo_work_form(
    *,
    review: ModeloWorkReview,
    snapshot: RegistrySnapshot,
    layout: FormLayoutDefinition | None,
    revision: CalculationRevision | None,
    permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None,
    entered_casilla_ids: frozenset[CasillaId] | None,
    overridden_binding_ids: frozenset[BindingId] | None,
    language: OutputLanguage,
) -> ModeloWorkForm:
    """Join one work review with its revision's declared layout into a classified editor form.

    ``entered_casilla_ids`` and ``overridden_binding_ids`` are the operator's own
    recorded entries on the current revision; ``None`` means the revision does
    not record them, which is different from recording none. ``permitted_surface``
    is the current edit admission's surface, or ``None`` when no admission is
    available, in which case nothing is offered for editing.

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.
    """
    context = _FormContext(
        review=review,
        snapshot=snapshot,
        revision=revision,
        permitted_surface=permitted_surface,
        entered_casilla_ids=entered_casilla_ids,
        overridden_binding_ids=overridden_binding_ids,
        language=language,
    )
    if layout is None or str(layout.revision_id) != str(snapshot.revision.id):
        reason = (
            ModeloFormInspectionReason.LAYOUT_ABSENT
            if layout is None
            else ModeloFormInspectionReason.LAYOUT_FOR_ANOTHER_REVISION
        )
        return _inspection_form(context, snapshot, reason)
    walk = _LayoutWalk(layout, context)
    pages = tuple(walk.page(page) for page in layout.pages)
    working: list[ModeloFormField] = []
    unplaced: list[ModeloFormUnplacedField] = []
    for placement in layout.placements:
        casilla_id = str(placement.casilla_id)
        if placement.kind is FormPlacementKind.WORKING_FIGURE:
            working.append(_casilla_field(casilla_id, context, placement))
        elif placement.kind is FormPlacementKind.UNPLACED:
            unplaced.append(
                ModeloFormUnplacedField(
                    field=_casilla_field(casilla_id, context, placement), reason=placement.unplaced_reason
                )
            )
        elif casilla_id not in walk.seen:
            raise ModeloWorkFormLayoutError(f"casilla {casilla_id!r} is placed on the form but no page shows it")
    placed = walk.seen | {
        str(field.address.casilla_id) for field in working if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    placed |= {
        str(item.field.address.casilla_id)
        for item in unplaced
        if isinstance(item.field.address, ModeloFormCasillaAddressV1)
    }
    missing = sorted(set(context.rows) - placed)
    if missing:
        raise ModeloWorkFormLayoutError(f"the layout gives no placement to casillas {missing[:10]!r}")
    provenance = (
        ModeloFormLayoutProvenance.REVIEWED
        if layout.review.state is FormLayoutReviewState.REVIEWED
        else ModeloFormLayoutProvenance.GENERATED
    )
    form_fields = [field for page in pages for section in page.sections for field in section_fields(section)]
    return ModeloWorkForm(
        modelo=review.modelo,
        filing_year=review.filing_year,
        period=review.period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id=str(review.work_unit_id),
        calculation_revision_id=None if review.calculation_revision_id is None else str(review.calculation_revision_id),
        language=language,
        layout_provenance=provenance,
        seed_source=layout.seed_source,
        pages=pages,
        working_figures=tuple(working),
        unplaced=tuple(unplaced),
        result_addresses=_results(context),
        counts=_counts([*form_fields, *working, *(item.field for item in unplaced)]),
        progress=review.progress,
        operator_entries_known=entered_casilla_ids is not None,
        edit_admitted=permitted_surface is not None,
    )


def _results(context: _FormContext) -> tuple[CasillaId, ...]:
    return tuple(row.casilla_id for row in context.review.casillas if _role(row) is CalculationReportRowRole.RESULT)


def _box_order(field: ModeloFormField) -> tuple[int, int, str]:
    box = field.box
    label = field.label.text
    return (0, int(box), label) if box is not None else (1, 0, label)


def _inspection_form(
    context: _FormContext, snapshot: RegistrySnapshot, reason: ModeloFormInspectionReason
) -> ModeloWorkForm:
    """Show every casilla read-only in official box order when no usable layout exists."""
    fields = sorted(
        (
            _casilla_field(casilla_id, context, None).model_copy(
                update={"editability": ModeloFormEditability.INFORMATIONAL, "not_writable_reason": None}
            )
            for casilla_id in context.rows
        ),
        key=_box_order,
    )
    blocks = tuple(ModeloFormFieldBlock(id=f"field-{index}", field=field) for index, field in enumerate(fields))
    heading = _heading(_INSPECTION_HEADING_LOCALE_KEY, None, _INSPECTION_PAGE_ID, context.language)
    section = ModeloFormSection(
        id=f"{_INSPECTION_PAGE_ID}.all", heading=heading, official_heading=None, blocks=blocks, counts=_counts(fields)
    )
    page = ModeloFormPage(
        id=_INSPECTION_PAGE_ID,
        heading=heading,
        official_ref=None,
        condition=FormPageCondition.ALWAYS,
        applies=True,
        sections=(section,),
        counts=_counts(fields),
    )
    review = context.review
    return ModeloWorkForm(
        modelo=review.modelo,
        filing_year=review.filing_year,
        period=review.period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id=str(review.work_unit_id),
        calculation_revision_id=None if review.calculation_revision_id is None else str(review.calculation_revision_id),
        language=context.language,
        layout_provenance=ModeloFormLayoutProvenance.INSPECTION_ONLY,
        inspection_reason=reason,
        pages=(page,),
        result_addresses=_results(context),
        counts=_counts(fields),
        progress=review.progress,
        operator_entries_known=context.entered is not None,
        edit_admitted=False,
    )


__all__ = ["ModeloWorkFormLayoutError", "build_modelo_work_form"]
