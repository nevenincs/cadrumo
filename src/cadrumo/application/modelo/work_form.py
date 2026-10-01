"""Build the editor form of one modelo work target from the review and the declared layout.

:func:`build_modelo_work_form` is a pure join. It reads the canonical work
review for values and origins, the revision's declared form layout for pages,
sections, grids and placements, the registry snapshot for localized labels,
help, required inputs and bindings, the current calculation revision for what
the filer explicitly cleared, for detail rows, for the AEAT draft it replays and
for its filing state, and the edit admission's permitted
surface for what may be written. It derives no layout: a revision without a
usable declared layout becomes an inspection-only form that says why.

Classification is decided once, here, so every frontend shows the same states:

* the origin of each value -- entered, imported, calculated, needed, not
  applicable, cleared, or held without proof anyone entered it -- and
* the editability of each address -- typed, overridden with a reason, fixed at
  its source, corrected in the profile, calculated, or fixed by the design,
* where each bound value comes from, named by its primary binding's family,
  with the earlier declaration a carry reads and the AEAT tax data an imported
  draft supplied,
* whether a box needs the filer's value, by the same rule verification checks,
* the one rate a printed rate box stands for, where its row's base binding
  declares exactly one, and the rate a box the design fixes prints, where its
  literal states a percentage or its export field declares the scale, never
  from a literal of zeros,
* for a repeating column the design leaves unnamed, the label of the box it
  shows, and for an input no box owns that feeds exactly one numbered box, the
  words "additional data for" that box,
* the settlement box and which way it settles,
* what the latest calculation noticed, on the same scale as the check's
  findings and without repeating one of them, and which box a note says could
  not be worked out, which then reads as not calculated rather than as zero, and
* whether the declaration is recorded as filed, which closes it to editing and
  leaves nothing counted as still to do.

"Entered by the filer" is only ever claimed from the operator's own recorded
entries. A revision that predates them has an unknown operator record, and a
value it holds for a box the filer types is never shown as entered. It is one
to confirm where it could under-declare, in a box verification requires or
when it is not zero; an optional box holding zero reads as optional and empty.
Either way the field says the value is unattributed, because a recalculation
returns it to what the calculation gives.

The form is total: every casilla of the revision appears exactly once, on a
page, among the working figures, or in the unplaced list with its reason. A
layout that would drop or repeat a casilla is refused rather than rendered.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation, tr
from ...domain.calculations.registry.export_field_casilla import (
    export_field_casilla_id,
    layout_fields_in_emission_order,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_iva_bindings import LedgerIvaProvider
from ...domain.calculations.registry.modelo_localization import modelo_localization_source, resolve_modelo_localization
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_base import CasillaDataType
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
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
    FormSectionDefinition,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.filing.schema import ModeloValueKind
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .calculation_notes import BLOCKING_REASONS, CHECK_REFUSED_REASONS, UNWORKED_BOX_REASONS, note_attention
from .calculation_report import CalculationReportRowRole, calculation_report_row_role
from .caller_context import caller_context_of
from .edit_models import (
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .edit_value_grammar import ModeloEditRatioUnit, ratio_unit
from .printed_boxes import printed_box_number
from .required_inputs import filer_required_casilla_ids
from .source_policy import SourceOverridePolicy, source_policy
from .work_form_models import (
    ABSENT_FROM_ADMISSION,
    ModeloFormAeatData,
    ModeloFormAttention,
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormBindingInputsBlock,
    ModeloFormBlock,
    ModeloFormBlocker,
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormCounts,
    ModeloFormDeadline,
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormFiling,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormInspectionReason,
    ModeloFormIssue,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormPrintedRate,
    ModeloFormRate,
    ModeloFormRepeatingBlock,
    ModeloFormRepeatingRow,
    ModeloFormResult,
    ModeloFormScalar,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloFormUnplacedField,
    ModeloWorkForm,
    section_fields,
)
from .work_form_result import settlement_result
from .work_form_sources import FIXED_BY_THE_FORM, bound_value_source
from .work_review import ModeloWorkOriginAnomaly, ModeloWorkReview, ModeloWorkReviewCasilla

_SPANISH: Final[str] = OutputLanguage.ES.value
_INSPECTION_PAGE_ID: Final[str] = "inspection"
_INSPECTION_HEADING_LOCALE_KEY: Final[str] = "application.modelo.work_form.inspection_heading"
_UNNAMED_LOCALE_KEY: Final[str] = "application.modelo.work_form.unnamed_box"
"""The label of a box the form gives no name, in the filer's words."""
_FEEDS_BOX_LOCALE_KEY: Final[str] = "application.modelo.work_form.additional_data_for_box"
"""The label of an input no box owns that feeds exactly one numbered box, named after that box."""
_BOX_LOCATOR_HELP_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "application.modelo.work_form.box_locator_help.one_year",
    "application.modelo.work_form.box_locator_help.year_span",
    "application.modelo.work_form.box_locator_help.onwards",
)
"""The catalogue's sentences that only say which box of which modelo and year a casilla is."""
_BOX_SLOT: Final[str] = "\ue000"
_YEARS_SLOT: Final[str] = "\ue001"
"""Placeholders no catalogue text contains, standing where a locator names its box and its year."""
_FIGURES: Final[str] = "[0-9-]+"
"""What fills a locator's box and year: digits and the hyphen of a range, never words."""
_BINDING_DATA_TYPE: Final[Mapping[str, str]] = {
    "money": "money",
    "decimal": "decimal",
    "integer": "integer",
    "boolean": "boolean",
    "text": "text",
    "date": "date",
    "enum": "text",
}


_BOOLEAN_TOKENS: Final[Mapping[str, bool]] = {"true": True, "1": True, "false": False, "0": False}
"""The spellings a yes-or-no binding value is stored under."""
_NUMERIC_BINDING_TYPES: Final[frozenset[str]] = frozenset({"money", "decimal", "integer"})
"""The binding data types whose stored digits stand for a number."""
_FILED_STATES: Final[frozenset[CalculationRevisionState]] = frozenset(
    {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
)
"""The lifecycle states of a calculation recorded as filed."""
_TO_DO_TALLIES: Final[tuple[str, ...]] = ("needs_input", "default_to_confirm")
"""The counts of what the filer still has to enter or confirm."""
_PERCENT_LITERAL: Final[re.Pattern[str]] = re.compile(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*%\s*")
"""A design literal that states a percentage outright, such as ``21 %`` or ``1,75%``."""
_DIGIT_LITERAL: Final[re.Pattern[str]] = re.compile(r"[0-9]+")
_FINDINGS_OF_THE_SAME_CAUSE: Final[Mapping[str, frozenset[str]]] = {
    "unresolved_binding": frozenset({"application.modelo.findings.missing_required_casilla"}),
    "unresolved_derived_binding": frozenset({"application.modelo.findings.missing_required_casilla"}),
    "unrouted_observation": frozenset(
        {
            "application.modelo.findings.cuota_less_ledger_row_base_missing",
            "application.modelo.findings.oss_source_unrouted",
        }
    ),
    "unrouted_declarable_quantity": frozenset({"application.modelo.findings.cuota_less_ledger_row_base_missing"}),
    "iva_selected_scope_evidence_failure": frozenset(
        {"application.modelo.findings.iva_selected_scope_evidence_failure"}
    ),
    "iva_compensation_annual_source_evidence_failure": frozenset(
        {"application.modelo.findings.iva_compensation_annual_source_evidence_failure"}
    ),
    "withholding_detail_absent": frozenset(
        {
            "application.modelo.findings.withholding_detail_absent_unproven",
            "application.modelo.findings.withholding_detail_absent_against_ledger_evidence",
            "application.modelo.findings.withholding_detail_absent_attested",
        }
    ),
    "missing_transaction_evidence": frozenset(
        {
            "application.modelo.findings.transaction_evidence_missing_deductible",
            "application.modelo.findings.transaction_evidence_missing_output",
        }
    ),
}
"""The check's findings that say the same thing as a calculation note, by the note's reason."""
_ATTENTION_ORDER: Final[tuple[ModeloFormAttention, ...]] = tuple(ModeloFormAttention)


class ModeloWorkFormLayoutError(InternalInvariantError):
    """A declared layout does not account for every casilla exactly once."""


class _FormContext:
    """Everything one form build reads, indexed once."""

    def export_decimals(self, casilla_id: str) -> int | None:
        """The implied decimals of the export field that emits one casilla, read once per form."""
        if self._export_decimals is None:
            decimals: dict[str, int] = {}
            for layout in self.snapshot.revision.export_layouts:
                for record, field in layout_fields_in_emission_order(layout):
                    target = export_field_casilla_id(record, field, bindings=self.bindings)
                    if target is not None and field.decimals is not None:
                        decimals.setdefault(str(target), field.decimals)
            self._export_decimals = decimals
        return self._export_decimals.get(casilla_id)

    @property
    def box_locators(self) -> tuple[re.Pattern[str], ...]:
        """The modelo's box-locator help sentences, rendered once per form."""
        if self._box_locators is None:
            self._box_locators = _render_box_locators(str(self.snapshot.modelo.id))
        return self._box_locators

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
        unworked_casilla_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.review = review
        self.unworked = unworked_casilla_ids
        self.language = language
        self.revision = revision
        self.rows: dict[str, ModeloWorkReviewCasilla] = {str(row.casilla_id): row for row in review.casillas}
        self.casillas: dict[str, CasillaDefinition] = {str(item.id): item for item in snapshot.revision.casillas}
        self.bindings: dict[str, BindingDefinition] = {str(item.id): item for item in snapshot.revision.bindings}
        self.snapshot = snapshot
        self._export_decimals: dict[str, int] | None = None
        self._box_locators: tuple[re.Pattern[str], ...] | None = None
        self.required: frozenset[str] = frozenset(str(item) for item in filer_required_casilla_ids(snapshot.revision))
        self.filed = review.lifecycle_state in _FILED_STATES
        self.surface: dict[tuple[str, str], ModeloEditPermittedSurfaceEntryV1] | None = (
            None
            if permitted_surface is None or self.filed
            else {_surface_key(entry): entry for entry in permitted_surface}
        )
        self.aeat_data_bindings: frozenset[str] = frozenset(
            ()
            if revision is None or caller_context_of(revision).borrador_snapshot_id is None
            else (str(item) for item in revision.bindings_sourced_from_borrador)
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
        self.fed_casillas: dict[str, set[str]] = {}
        for row in review.casillas:
            refs = (
                *(str(origin.binding_id) for origin in row.concrete_bindings),
                *(() if row.concrete_formula is None else (str(ref) for ref in row.concrete_formula.operand_refs)),
            )
            for ref in refs:
                self.fed_casillas.setdefault(ref, set()).add(str(row.casilla_id))
        self.placed_boxes: dict[str, str] = {}


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


def _unnamed(language: OutputLanguage) -> ModeloFormText:
    """The label of a box the form gives no name: plain words saying so, never its identifier."""
    text = lookup_translation(_UNNAMED_LOCALE_KEY, locale=language.value) or lookup_translation(
        _UNNAMED_LOCALE_KEY, locale=_SPANISH
    )
    if not text:
        raise InternalInvariantError(f"the catalogue has no text for {_UNNAMED_LOCALE_KEY!r}")
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.UNNAMED)


def _fed_box_label(binding_id: str, context: _FormContext) -> ModeloFormText | None:
    """Name an input no box owns after the one numbered box it feeds, or ``None`` when it feeds none or several."""
    fed = context.fed_casillas.get(binding_id, set())
    if len(fed) != 1:
        return None
    (casilla_id,) = fed
    box = context.placed_boxes.get(casilla_id) or printed_box_number(context.casillas.get(casilla_id), None)
    if box is None:
        return None
    for locale, disclosure in (
        (context.language.value, ModeloFormTextDisclosure.LOCALIZED),
        (_SPANISH, ModeloFormTextDisclosure.SPANISH_FALLBACK),
    ):
        if lookup_translation(_FEEDS_BOX_LOCALE_KEY, locale=locale):
            return ModeloFormText(text=tr(_FEEDS_BOX_LOCALE_KEY, locale=locale, box=box), disclosure=disclosure)
    raise InternalInvariantError(f"the catalogue has no text for {_FEEDS_BOX_LOCALE_KEY!r}")


def _help(casilla: CasillaDefinition, label: str, context: _FormContext) -> str | None:
    """Return the casilla's help unless it only restates the label or names the box."""
    keys = tuple(f"{key.removesuffix('.label')}.help" for key in casilla.localization_keys)
    text = resolve_modelo_localization(keys, locale=context.language.value)
    if not text:
        return None
    if _normalized(text) == _normalized(label) or _names_only_its_box(text, context.box_locators):
        return None
    return text


def _render_box_locators(modelo: str) -> tuple[re.Pattern[str], ...]:
    """The sentences that only say which box of ``modelo`` and which year a help is about, in every language.

    Each is the catalogue's own sentence rendered for the modelo, so a reworded
    catalogue is followed rather than missed. The box and the year are taken as
    written, as figures: help an edition inherits names the year of the edition
    that stated it, and some name the box by its record positions.
    """
    locators: list[re.Pattern[str]] = []
    for language in OutputLanguage:
        for key in _BOX_LOCATOR_HELP_LOCALE_KEYS:
            rendered = re.escape(tr(key, locale=language.value, modelo=modelo, box=_BOX_SLOT, years=_YEARS_SLOT))
            figures = rendered.replace(_BOX_SLOT, _FIGURES).replace(_YEARS_SLOT, _FIGURES)
            locators.append(re.compile(figures))
    return tuple(locators)


def _names_only_its_box(text: str, locators: tuple[re.Pattern[str], ...]) -> bool:
    """Whether a help text is one of ``locators``' sentences and says nothing else."""
    stated = text.strip()
    return any(locator.fullmatch(stated) for locator in locators)


def _normalized(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text).strip().casefold()


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
    return _held_origin(row.value, required=required)


def _held_origin(value: ModeloFormScalar, *, required: bool) -> ModeloFormOrigin:
    """Classify a value the filer types that the calculation holds and nobody is recorded as entering.

    It is assumed, and waits for the filer to confirm it, only where it could
    under-declare: in a box the declaration requires, or when it is not zero.
    An optional box holding zero asks nothing of the filer.
    """
    if required or not _holds_nothing(value):
        return ModeloFormOrigin.DEFAULT_TO_CONFIRM
    return ModeloFormOrigin.OPTIONAL_EMPTY


def _holds_nothing(value: ModeloFormScalar) -> bool:
    """Whether a held value is zero or nothing: no amount, a zero amount, a blank text or an unmarked choice."""
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, str) and not value.strip():
        return True
    amount = _numeric(value)
    return amount is not None and amount == 0


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
    return ModeloFormEditability.NOT_WRITABLE, ABSENT_FROM_ADMISSION


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
    return ModeloFormEditability.NOT_WRITABLE, ABSENT_FROM_ADMISSION


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
    label = _localized(casilla.localization_keys, context.language) or _unnamed(context.language)
    required = casilla_id in context.required
    editability, reason = _casilla_editability(row, context)
    origin = _casilla_origin(row, context, required=required)
    value = row.value
    if casilla_id in context.unworked and origin not in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}:
        # The calculation said this box could not be worked out: whatever it holds is not a figure.
        origin, value = ModeloFormOrigin.CALCULATION_FAILED, None
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=row.casilla_id),
        box=printed_box_number(casilla, placement),
        label=label,
        help=_help(casilla, label.text, context),
        data_type=str(row.data_type),
        value=value,
        origin=origin,
        editability=editability,
        not_writable_reason=reason,
        required=required,
        unattributed=origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        or (origin is ModeloFormOrigin.OPTIONAL_EMPTY and row.realised_kind is not ModeloValueKind.EMPTY),
        role=_role(row),
        bindings=_bindings(row),
        source=bound_value_source(
            tuple(origin.binding_id for origin in row.concrete_bindings),
            bindings=context.bindings,
            aeat_data_binding_ids=context.aeat_data_bindings,
            target=context.review.period,
        ),
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
        (None if owner_casilla is None else _localized(owner_casilla.localization_keys, context.language))
        or _fed_box_label(binding_id, context)
        or _unnamed(context.language)
    )
    raw = None if context.revision is None else context.revision.binding_overrides.get(binding.id)
    data_type = _BINDING_DATA_TYPE.get(binding.value.data_type.value, "text")
    policy = source_policy(binding.source)
    editability, reason = _binding_input_editability(binding_id, policy.override_policy, context)
    overridden = context.overridden is not None and binding_id in context.overridden
    value = _binding_value(raw, data_type)
    typed_unattributed = not overridden and raw is not None and binding.source is BindingSourceKind.MANUAL_INPUT
    if overridden:
        origin = ModeloFormOrigin.ENTERED
    elif raw is None:
        origin = ModeloFormOrigin.OPTIONAL_EMPTY
    elif binding.source is not BindingSourceKind.MANUAL_INPUT:
        origin = ModeloFormOrigin.IMPORTED
    else:
        origin = _held_origin(value, required=False)
    return ModeloFormField(
        address=ModeloFormBindingAddressV1(binding_id=binding.id),
        box=None,
        label=label,
        help=None,
        data_type=data_type,
        value=value,
        origin=origin,
        editability=editability,
        not_writable_reason=reason,
        required=False,
        unattributed=typed_unattributed,
        bindings=(ModeloFormBinding(binding_id=binding.id, policy=policy, resolved=raw is not None),),
        source=bound_value_source(
            (binding.id,),
            bindings=context.bindings,
            aeat_data_binding_ids=context.aeat_data_bindings,
            target=context.review.period,
        ),
        legal_refs=tuple(binding.legal_refs),
    )


def _binding_value(raw: str | None, data_type: str) -> ModeloFormScalar:
    """Read a stored binding value as the value it stands for.

    A binding value is stored as text: a yes-or-no as a token, and an amount
    or a count as its digits. Each is read back as the typed value it holds,
    the one the filer's own entry would have, so keeping it unchanged
    confirms exactly that value.
    """
    if raw is None:
        return None
    if data_type == "boolean":
        return _BOOLEAN_TOKENS.get(raw.strip().lower(), raw)
    if data_type in _NUMERIC_BINDING_TYPES:
        amount = _numeric(raw.strip())
        return raw if amount is None else amount
    return raw


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
    return ModeloFormEditability.NOT_WRITABLE, ABSENT_FROM_ADMISSION


def _counts(fields: Iterable[ModeloFormField], *, filed: bool) -> ModeloFormCounts:
    """Tally fields by origin; a declaration recorded as filed has nothing left to enter or confirm."""
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
    if filed:
        tallies.update(dict.fromkeys(_TO_DO_TALLIES, 0))
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


def _grounded_rate(field: ModeloFormField, context: _FormContext) -> ModeloFormRate | None:
    """The one rate the bindings filling a base box declare, or ``None`` when they do not declare exactly one.

    Every binding that fills the box must be a rate-specific IVA ledger
    aggregate: a rate-blind binding admits records at any rate of its tier, so
    a box it fills is not grounded on one rate, however the others read.
    """
    if not isinstance(field.address, ModeloFormCasillaAddressV1):
        return None
    casilla = context.casillas.get(str(field.address.casilla_id))
    if casilla is None:
        return None
    binding_ids = tuple(item for item in (casilla.binding, *casilla.alternate_bindings) if item is not None)
    rates: set[Decimal] = set()
    for binding_id in binding_ids:
        binding = context.bindings.get(str(binding_id))
        provider = None if binding is None else binding.provider
        if not isinstance(provider, LedgerIvaProvider) or provider.applied_rates is None:
            return None
        rates.update(provider.applied_rates)
    if len(rates) != 1:
        return None
    return ModeloFormRate(ratio=rates.pop(), binding_id=binding_ids[0])


def _with_grounded_rate(cells: tuple[ModeloFormGridCell, ...], context: _FormContext) -> tuple[ModeloFormGridCell, ...]:
    """Give an official row's rate box the one rate its base box is grounded on.

    The row must print exactly one rate box, and its other boxes must be
    grounded on exactly one rate between them; any other row is left as it is,
    with no rate claimed for its rate box.
    """
    rate_indexes = [
        index
        for index, cell in enumerate(cells)
        if cell.field is not None and cell.field.data_type == CasillaDataType.RATIO.value
    ]
    if len(rate_indexes) != 1:
        return cells
    (rate_index,) = rate_indexes
    if _placeholder_literal(cells[rate_index]):
        # The design prints zeros where this row's rate would stand: it prints no rate, so none is claimed.
        return cells
    grounded: dict[Decimal, ModeloFormRate] = {}
    for index, cell in enumerate(cells):
        rate = None if index == rate_index or cell.field is None else _grounded_rate(cell.field, context)
        if rate is not None:
            grounded.setdefault(rate.ratio, rate)
    rate_cell = cells[rate_index]
    if len(grounded) != 1 or rate_cell.field is None:
        return cells
    (rate,) = grounded.values()
    field = rate_cell.field.model_copy(update={"grounded_rate": rate})
    return tuple(
        rate_cell.model_copy(update={"field": field}) if index == rate_index else cell
        for index, cell in enumerate(cells)
    )


def _rate_literal(cell: ModeloFormGridCell) -> str | None:
    """The literal of a rate box the design fixes, or ``None`` for any other cell."""
    field = cell.field
    if cell.kind is not FormCellKind.DESIGN_CONSTANT or field is None or cell.literal is None:
        return None
    return cell.literal if field.data_type == CasillaDataType.RATIO.value else None


def _placeholder_literal(cell: ModeloFormGridCell) -> bool:
    """Whether a rate box the design fixes holds only zeros, the design's placeholder where no rate is printed."""
    literal = _rate_literal(cell)
    return literal is not None and _DIGIT_LITERAL.fullmatch(literal) is not None and int(literal) == 0


def _stated_percent(literal: str) -> Decimal | None:
    """A literal that states a percentage outright, as a fraction of one."""
    match = _PERCENT_LITERAL.fullmatch(literal)
    if match is None:
        return None
    return Decimal(match.group(1).replace(",", ".")).scaleb(-2)


def _declared_scale_rate(field: ModeloFormField) -> Decimal | None:
    """A fixed rate box's figure read at the scale its export field declares, as a fraction of one.

    The box holds a figure only when the export field declares its implied
    decimals; the casilla's declared bounds then say whether that figure is a
    percentage or a fraction. Without both, the literal's scale is unknown and
    no rate is read from it.
    """
    value = field.value
    if not isinstance(value, Decimal):
        return None
    maximum = None if field.constraints is None else field.constraints.max_value
    unit = ratio_unit(field.data_type, maximum)
    if unit is ModeloEditRatioUnit.PERCENT:
        return value.scaleb(-2)
    if unit is ModeloEditRatioUnit.FRACTION:
        return value
    return None


def _printed_rate(cell: ModeloFormGridCell) -> ModeloFormPrintedRate | None:
    """The rate a fixed rate box prints, where its literal states it or its export field declares the scale.

    Nothing is inferred from other rows: a literal whose scale is not declared
    prints no rate Cadrumo can state.
    """
    literal = _rate_literal(cell)
    if literal is None or cell.field is None or _placeholder_literal(cell):
        return None
    ratio = _stated_percent(literal)
    if ratio is None:
        ratio = _declared_scale_rate(cell.field)
    if ratio is None or not Decimal(0) < ratio <= 1:
        return None
    return ModeloFormPrintedRate(ratio=ratio.normalize(), literal=literal)


def _with_printed_rates(rows: tuple[ModeloFormGridRow, ...]) -> tuple[ModeloFormGridRow, ...]:
    """Give each rate box the design fixes the rate its literal prints, where that reading is declared."""
    updated: list[ModeloFormGridRow] = []
    for row in rows:
        cells: list[ModeloFormGridCell] = []
        for cell in row.cells:
            printed = _printed_rate(cell)
            if printed is None or cell.field is None:
                cells.append(cell)
                continue
            field = cell.field.model_copy(update={"printed_rate": printed})
            cells.append(cell.model_copy(update={"field": field}))
        updated.append(row.model_copy(update={"cells": tuple(cells)}))
    return tuple(updated)


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

    def casilla(self, casilla_id: str, *, design_constant: str | None = None) -> ModeloFormField:
        """Show one placed casilla; a box whose value the official design fixes is never editable.

        Its value is the design's literal read at the export field's declared
        scale. A literal whose scale the registry does not declare is shown as
        fixed without a number: neither the literal's raw digits nor the
        engine's own figure for the box is what the filed fichero carries.
        """
        if casilla_id in self.seen:
            raise ModeloWorkFormLayoutError(f"the layout places casilla {casilla_id!r} more than once")
        placement = self.placements.get(casilla_id)
        if placement is None or placement.kind is not FormPlacementKind.ON_FORM:
            raise ModeloWorkFormLayoutError(f"casilla {casilla_id!r} sits on a page without an on-form placement")
        self.seen.add(casilla_id)
        field = _casilla_field(casilla_id, self.context, placement, self.aliases.get(casilla_id, ()))
        if design_constant is None:
            return field
        fixed = _design_value(design_constant, self.context.export_decimals(casilla_id))
        return field.model_copy(
            update={
                "editability": ModeloFormEditability.DESIGN_CONSTANT,
                "not_writable_reason": None,
                "origin": ModeloFormOrigin.INFORMATIONAL,
                "unattributed": False,
                "value": fixed,
                "source": FIXED_BY_THE_FORM,
            }
        )

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
            counts=_counts(
                (field for section in sections for field in section_fields(section)), filed=self.context.filed
            ),
        )

    def section(self, page_id: str, section: FormSectionDefinition) -> ModeloFormSection:
        blocks = tuple(self.block(block) for block in section.blocks)
        form_section = ModeloFormSection(
            id=f"{page_id}.{section.id}",
            heading=_heading(section.heading_key, section.official_heading, section.id, self.context.language),
            official_heading=section.official_heading,
            blocks=blocks,
            counts=_counts((), filed=self.context.filed),
        )
        return form_section.model_copy(
            update={"counts": _counts(section_fields(form_section), filed=self.context.filed)}
        )

    def block(
        self, block: FormFieldBlock | FormGridBlock | FormRepeatingGroupBlock | FormBindingInputsBlock
    ) -> ModeloFormBlock:
        language = self.context.language
        if isinstance(block, FormFieldBlock):
            field = (
                self.casilla(str(block.casilla_id), design_constant=block.design_constant)
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
                    cells=_with_grounded_rate(
                        tuple(
                            self.cell(cell.kind, cell.casilla_id, cell.binding_id, cell.literal) for cell in row.cells
                        ),
                        self.context,
                    ),
                )
                for row in block.rows
            )
            return ModeloFormGridBlock(id=block.id, columns=columns, rows=_with_printed_rates(rows))
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
        if kind is FormCellKind.DESIGN_CONSTANT and casilla_id is not None:
            return ModeloFormGridCell(
                kind=kind, field=self.casilla(str(casilla_id), design_constant=literal), literal=literal
            )
        return ModeloFormGridCell(kind=kind, literal=literal)

    def repeating(self, block: FormRepeatingGroupBlock) -> ModeloFormRepeatingBlock:
        columns = tuple(
            ModeloFormGridColumn(key=column.key, heading=self.repeating_heading(column)) for column in block.columns
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
            column_casilla_ids=column_casillas,
            column_data_types=data_types,
            min_rows=block.min_rows,
            max_rows=block.max_rows,
            rows_known=block.row_source is FormRepeatingRowSource.EXPORT_RECORD and self.context.revision is not None,
            rows=self.repeating_rows(block, column_casillas),
        )

    def repeating_heading(self, column: FormRepeatingColumn) -> ModeloFormText:
        """A repeating column's heading; one the design does not name reads as the label of the box it shows."""
        language = self.context.language
        heading = _heading(column.heading_key, column.official_heading, column.key, language)
        if heading.disclosure is not ModeloFormTextDisclosure.TECHNICAL or column.casilla_id is None:
            return heading
        casilla = self.context.casillas.get(str(column.casilla_id))
        label = None if casilla is None else _localized(casilla.localization_keys, language)
        return heading if label is None else label

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
    deadline: ModeloFormDeadline | None = None,
    aeat_data_imported_at: datetime | None = None,
    calculation_diagnostics: tuple[CalculationSourceDiagnostic, ...] | None = None,
) -> ModeloWorkForm:
    """Join one work review with its revision's declared layout into a classified editor form.

    ``entered_casilla_ids`` and ``overridden_binding_ids`` are the operator's own
    recorded entries on the current revision; ``None`` means the revision does
    not record them, which is different from recording none. ``permitted_surface``
    is the current edit admission's surface, or ``None`` when no admission is
    available, in which case nothing is offered for editing. A declaration
    recorded as filed offers nothing for editing whatever the admission says,
    because changing it starts a correction.

    ``deadline`` is the resolved filing deadline, and ``aeat_data_imported_at``
    when the AEAT tax data the revision replays was imported; the caller reads
    both, since neither is a fact of the review or the layout.

    ``calculation_diagnostics`` are the diagnostics the latest calculation
    raised, when this session ran it; ``None`` when it did not, in which case
    only the notes that persist with the calculation are known.

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.
    """
    sources = _note_sources(revision, calculation_diagnostics)
    context = _FormContext(
        review=review,
        snapshot=snapshot,
        revision=revision,
        permitted_surface=permitted_surface,
        entered_casilla_ids=entered_casilla_ids,
        overridden_binding_ids=overridden_binding_ids,
        language=language,
        unworked_casilla_ids=frozenset(
            casilla_id for reason, casilla_id in sources if reason in UNWORKED_BOX_REASONS and casilla_id is not None
        ),
    )
    held = calculation_diagnostics is not None
    if layout is None or str(layout.revision_id) != str(snapshot.revision.id):
        reason = (
            ModeloFormInspectionReason.LAYOUT_ABSENT
            if layout is None
            else ModeloFormInspectionReason.LAYOUT_FOR_ANOTHER_REVISION
        )
        return _inspection_form(
            context,
            snapshot,
            reason,
            deadline=deadline,
            aeat_data_imported_at=aeat_data_imported_at,
            notes=(sources, held),
        )
    context.placed_boxes = {
        str(placement.casilla_id): placement.box_number
        for placement in layout.placements
        if placement.box_number is not None
    }
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
    every_field = [*form_fields, *working, *(item.field for item in unplaced)]
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
        counts=_counts(every_field, filed=context.filed),
        progress=review.progress,
        operator_entries_known=entered_casilla_ids is not None,
        edit_admitted=context.surface is not None,
        verification=review.verification_outcome,
        issues=_issues(review, every_field),
        calculation_notes=_calculation_notes(context, sources, every_field),
        calculation_notes_held=held,
        result=_result(context, every_field),
        deadline=deadline,
        aeat_data=_aeat_data(context, aeat_data_imported_at),
        filing=_filing(context),
        edit_closure=ModeloFormEditClosure.RECORDED_AS_FILED if context.filed else None,
    )


def _note_sources(
    revision: CalculationRevision | None, diagnostics: tuple[CalculationSourceDiagnostic, ...] | None
) -> tuple[tuple[str, str | None], ...]:
    """Each latest-calculation reason with the box it names: every diagnostic when held, else the durable ones."""
    if diagnostics is not None:
        return tuple(
            (diagnostic.reason, None if diagnostic.casilla_id is None else str(diagnostic.casilla_id))
            for diagnostic in diagnostics
        )
    if revision is None:
        return ()
    return tuple(
        (issue.reason, None if issue.casilla_id is None else str(issue.casilla_id)) for issue in revision.source_issues
    )


def _said_by_a_finding(reason: str, casilla_id: str | None, findings: Iterable[ModeloVerificationFinding]) -> bool:
    """Whether a finding of the check already says what this note says, about the same box."""
    causes = _FINDINGS_OF_THE_SAME_CAUSE.get(reason, frozenset())
    return any(
        finding.message_locale_key in causes
        and (None if finding.casilla_id is None else str(finding.casilla_id)) == casilla_id
        for finding in findings
    )


def _calculation_notes(
    context: _FormContext, sources: tuple[tuple[str, str | None], ...], fields: Iterable[ModeloFormField]
) -> tuple[ModeloFormCalculationNote, ...]:
    """The latest calculation's notes on the filer's scale, once each, leaving out what a finding already says.

    A reason the check decides on its own evidence waits for the check: once
    the current calculation has been checked, the check's finding of the same
    cause is what stands, blocking where the check refused and worth checking
    where it accepted an attestation, so the note is left out.
    """
    checked = context.review.verification_outcome is not None
    boxes = {
        str(field.address.casilla_id): field.box
        for field in fields
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    notes: dict[tuple[str, str | None], ModeloFormCalculationNote] = {}
    for reason, casilla_id in sources:
        if (reason, casilla_id) in notes or _said_by_a_finding(reason, casilla_id, context.review.findings):
            continue
        if checked and reason in CHECK_REFUSED_REASONS:
            continue
        box = None if casilla_id is None else boxes.get(casilla_id)
        attention = note_attention(reason, box=box)
        notes[(reason, casilla_id)] = ModeloFormCalculationNote(
            reason=reason,
            attention=attention,
            casilla_id=casilla_id,
            box=box,
            durable=reason in BLOCKING_REASONS and attention is ModeloFormAttention.BLOCKS,
        )
    return tuple(sorted(notes.values(), key=lambda note: _ATTENTION_ORDER.index(note.attention)))


def _issues(review: ModeloWorkReview, fields: Iterable[ModeloFormField]) -> tuple[ModeloFormIssue, ...]:
    """The review's verification findings, blocking first, each with the box it names."""
    boxes = {
        str(field.address.casilla_id): field.box
        for field in fields
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    ordered = sorted(
        review.findings, key=lambda finding: finding.severity is not ModeloVerificationFindingSeverity.BLOCKING
    )
    return tuple(
        ModeloFormIssue(finding=finding, box=None if finding.casilla_id is None else boxes.get(str(finding.casilla_id)))
        for finding in ordered
    )


def _design_value(literal: str, decimals: int | None) -> Decimal | None:
    """Read a design literal as the fichero writes it: digits with the export field's implied decimals."""
    if decimals is None or not literal.isdigit():
        return None
    return Decimal(int(literal)).scaleb(-decimals)


def _results(context: _FormContext) -> tuple[CasillaId, ...]:
    return tuple(row.casilla_id for row in context.review.casillas if _role(row) is CalculationReportRowRole.RESULT)


def _result(context: _FormContext, fields: Iterable[ModeloFormField]) -> ModeloFormResult | None:
    """The settlement box, printed where the form shows it."""
    result = settlement_result(
        str(context.review.modelo), context.snapshot.revision, context.rows, context.review.period
    )
    if result is None:
        return None
    box = next(
        (
            field.box
            for field in fields
            if isinstance(field.address, ModeloFormCasillaAddressV1) and field.address.casilla_id == result.casilla_id
        ),
        None,
    )
    return result.model_copy(update={"box": box})


def _aeat_data(context: _FormContext, imported_at: datetime | None) -> ModeloFormAeatData | None:
    """The AEAT tax data the current calculation replays, when it replays any."""
    revision = context.revision
    snapshot_id = None if revision is None else caller_context_of(revision).borrador_snapshot_id
    if revision is None or snapshot_id is None:
        return None
    return ModeloFormAeatData(
        snapshot_id=snapshot_id, imported_at=imported_at, binding_ids=tuple(revision.bindings_sourced_from_borrador)
    )


def _filing(context: _FormContext) -> ModeloFormFiling | None:
    """The recorded filing, when the current calculation is recorded as filed."""
    if not context.filed:
        return None
    return ModeloFormFiling(recorded_at=None if context.revision is None else context.revision.filed_at)


def _box_order(field: ModeloFormField) -> tuple[int, int, str]:
    box = field.box
    label = field.label.text
    return (0, int(box), label) if box is not None else (1, 0, label)


def _inspection_form(
    context: _FormContext,
    snapshot: RegistrySnapshot,
    reason: ModeloFormInspectionReason,
    *,
    deadline: ModeloFormDeadline | None,
    aeat_data_imported_at: datetime | None,
    notes: tuple[tuple[tuple[str, str | None], ...], bool],
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
        id=f"{_INSPECTION_PAGE_ID}.all",
        heading=heading,
        official_heading=None,
        blocks=blocks,
        counts=_counts(fields, filed=context.filed),
    )
    page = ModeloFormPage(
        id=_INSPECTION_PAGE_ID,
        heading=heading,
        official_ref=None,
        condition=FormPageCondition.ALWAYS,
        applies=True,
        sections=(section,),
        counts=_counts(fields, filed=context.filed),
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
        counts=_counts(fields, filed=context.filed),
        progress=review.progress,
        operator_entries_known=context.entered is not None,
        edit_admitted=False,
        verification=review.verification_outcome,
        issues=_issues(review, fields),
        calculation_notes=_calculation_notes(context, notes[0], fields),
        calculation_notes_held=notes[1],
        result=_result(context, fields),
        deadline=deadline,
        aeat_data=_aeat_data(context, aeat_data_imported_at),
        filing=_filing(context),
        edit_closure=ModeloFormEditClosure.RECORDED_AS_FILED if context.filed else None,
    )


__all__ = ["ModeloWorkFormLayoutError", "build_modelo_work_form"]
