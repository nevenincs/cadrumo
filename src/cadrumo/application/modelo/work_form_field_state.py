"""Classify work-form values by origin and editing authority."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from collections.abc import Mapping
from typing import Final

from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.filing.schema import ModeloValueKind
from .calculation_report import CalculationReportRowRole, calculation_report_row_role
from .edit_models import (
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .source_policy import SourceOverridePolicy, source_policy
from .work_form_models import (
    ABSENT_FROM_ADMISSION,
    ModeloFormBinding,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormScalar,
)
from .work_form_rates import parse_form_number
from .work_review import ModeloWorkOriginAnomaly, ModeloWorkReviewCasilla

BINDING_DATA_TYPE: Final[Mapping[str, str]] = {
    "money": "money",
    "decimal": "decimal",
    "integer": "integer",
    "boolean": "boolean",
    "text": "text",
    "date": "date",
    "enum": "text",
}

BOOLEAN_VALUE_TOKENS: Final[Mapping[str, bool]] = {"true": True, "1": True, "false": False, "0": False}

"""The spellings a yes-or-no binding value is stored under."""

NUMERIC_BINDING_TYPES: Final[frozenset[str]] = frozenset({"money", "decimal", "integer"})

"""The binding data types whose stored digits stand for a number."""


def summarize_bindings(row: ModeloWorkReviewCasilla) -> tuple[ModeloFormBinding, ...]:
    """Project the reviewed binding provenance into the form's binding summaries."""
    return tuple(
        ModeloFormBinding(binding_id=origin.binding_id, policy=source_policy(origin.source), resolved=origin.resolved)
        for origin in row.concrete_bindings
    )


def casilla_origin(row: ModeloWorkReviewCasilla, context: WorkFormContext, *, required: bool) -> ModeloFormOrigin:
    """Classify where one casilla's value stands; first match wins."""
    if row.absent_by_design:
        return ModeloFormOrigin.NOT_APPLICABLE
    for classify in (_source_override_origin, _computed_origin, _declared_origin):
        origin = classify(row, context)
        if origin is not None:
            return origin
    return _operator_entry_origin(row, context, required=required)


def _source_override_origin(row: ModeloWorkReviewCasilla, context: WorkFormContext) -> ModeloFormOrigin | None:
    overridden_binding = context.overridden is not None and any(
        str(origin.binding_id) in context.overridden for origin in row.concrete_bindings
    )
    if row.declared_input_kind is InputKind.BOUND and overridden_binding:
        return ModeloFormOrigin.OVERRIDES_SOURCE
    if row.origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE:
        return ModeloFormOrigin.OVERRIDES_SOURCE
    return None


def _computed_origin(row: ModeloWorkReviewCasilla, context: WorkFormContext) -> ModeloFormOrigin | None:
    if row.declared_input_kind is not InputKind.COMPUTED:
        return None
    if row.realised_kind is not ModeloValueKind.EMPTY:
        return ModeloFormOrigin.CALCULATED
    if context.review.calculation_revision_id is None:
        return ModeloFormOrigin.NOT_CALCULATED_YET
    return ModeloFormOrigin.CALCULATION_FAILED


def _declared_origin(row: ModeloWorkReviewCasilla, context: WorkFormContext) -> ModeloFormOrigin | None:
    kind = row.declared_input_kind
    if kind in {InputKind.INFORMATIONAL, InputKind.PROJECTION_ONLY}:
        return ModeloFormOrigin.INFORMATIONAL
    if kind is InputKind.BOUND:
        return (
            ModeloFormOrigin.NOT_IMPORTED_YET
            if row.realised_kind is ModeloValueKind.EMPTY
            else ModeloFormOrigin.IMPORTED
        )
    return None


def _operator_entry_origin(
    row: ModeloWorkReviewCasilla, context: WorkFormContext, *, required: bool
) -> ModeloFormOrigin:
    casilla_id = str(row.casilla_id)
    if casilla_id in context.cleared:
        return ModeloFormOrigin.CLEARED
    if context.entered is not None and casilla_id in context.entered:
        return ModeloFormOrigin.ENTERED
    if row.realised_kind is ModeloValueKind.EMPTY:
        return ModeloFormOrigin.NEEDS_INPUT if required else ModeloFormOrigin.OPTIONAL_EMPTY
    return held_value_origin(row.value, required=required)


def held_value_origin(value: ModeloFormScalar, *, required: bool) -> ModeloFormOrigin:
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
    amount = parse_form_number(value)
    return amount is not None and amount == 0


def casilla_editability(
    row: ModeloWorkReviewCasilla, context: WorkFormContext
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


def _bound_editability(
    row: ModeloWorkReviewCasilla, context: WorkFormContext
) -> tuple[ModeloFormEditability, str | None]:
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


def casilla_field_role(row: ModeloWorkReviewCasilla) -> CalculationReportRowRole | None:
    """Resolve the row's declared semantic role, leaving unknown mappings unclassified."""
    try:
        return calculation_report_row_role(declared_input_kind=row.declared_input_kind, semantic_role=row.semantic_role)
    except ValueError:
        return None


def binding_input_editability(
    binding_id: str, policy: SourceOverridePolicy, context: WorkFormContext
) -> tuple[ModeloFormEditability, str | None]:
    """Classify whether an unowned binding input can be overridden under its admitted policy."""
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
