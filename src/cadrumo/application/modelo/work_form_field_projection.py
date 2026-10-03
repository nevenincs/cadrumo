"""Project reviewed scalar and binding values into work-form fields."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.modelo_localization import binding_locale_key, resolve_modelo_localization
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_form_layouts import FormPlacementDefinition
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.filing.schema import ModeloValueKind
from .printed_boxes import printed_box_number
from .source_policy import source_policy
from .work_form_errors import ModeloWorkFormLayoutError
from .work_form_field_state import (
    BINDING_DATA_TYPE,
    BOOLEAN_VALUE_TOKENS,
    NUMERIC_BINDING_TYPES,
    binding_input_editability,
    casilla_editability,
    casilla_field_role,
    casilla_origin,
    held_value_origin,
    summarize_bindings,
)
from .work_form_localization import (
    casilla_help,
    fed_box_label,
    localized_text,
    normalized_help_text,
    unnamed_casilla_label,
)
from .work_form_models import (
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormBlocker,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormText,
)
from .work_form_rates import parse_form_number
from .work_form_sources import bound_value_source
from .work_review import ModeloWorkReviewCasilla


def project_casilla_field(
    casilla_id: str,
    context: WorkFormContext,
    placement: FormPlacementDefinition | None,
    also_appears_on: tuple[str, ...] = (),
) -> ModeloFormField:
    """Build one classified casilla field."""
    row, casilla = _casilla_source(casilla_id, context)
    label = localized_text(casilla.localization_keys, context.language) or unnamed_casilla_label(context.language)
    required = casilla_id in context.required
    editability, reason = casilla_editability(row, context)
    origin = casilla_origin(row, context, required=required)
    value = row.value
    if casilla_id in context.unworked and origin not in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}:
        # The calculation said this box could not be worked out: whatever it holds is not a figure.
        origin, value = ModeloFormOrigin.CALCULATION_FAILED, None
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=row.casilla_id),
        box=printed_box_number(casilla, placement),
        label=label,
        help=casilla_help(casilla, label.text, context),
        data_type=str(row.data_type),
        value=value,
        origin=origin,
        editability=editability,
        not_writable_reason=reason,
        required=required,
        unattributed=origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        or (origin is ModeloFormOrigin.OPTIONAL_EMPTY and row.realised_kind is not ModeloValueKind.EMPTY),
        role=casilla_field_role(row),
        bindings=summarize_bindings(row),
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


def _casilla_source(casilla_id: str, context: WorkFormContext) -> tuple[ModeloWorkReviewCasilla, CasillaDefinition]:
    row = context.rows.get(casilla_id)
    casilla = context.casillas.get(casilla_id)
    if row is None or casilla is None:
        raise ModeloWorkFormLayoutError(f"the layout places casilla {casilla_id!r}, which the revision does not define")
    return row, casilla


def _binding_casillas(binding: BindingDefinition, context: WorkFormContext) -> tuple[CasillaDefinition, ...]:
    """Follow declared ownership, provider and unambiguous export coordinates, in that order."""
    ids = [context.casilla_by_binding.get(str(binding.id))]
    provider = binding.provider
    if isinstance(provider, ManualInputProvider):
        ids.append(None if provider.casilla_id is None else str(provider.casilla_id))
        if provider.record is not None and provider.offset is not None:
            positioned = context.casillas_by_export_position.get((provider.record, provider.offset), set())
            if len(positioned) == 1:
                ids.extend(positioned)
    return tuple(context.casillas[item] for item in dict.fromkeys(ids) if item is not None and item in context.casillas)


def _binding_presentation(
    binding: BindingDefinition,
    binding_id: str,
    context: WorkFormContext,
    casillas: tuple[CasillaDefinition, ...],
) -> tuple[ModeloFormText, str | None, str | None]:
    modelo = str(context.snapshot.modelo.id)
    label = _binding_field_label(modelo, binding_id, casillas, context)
    help_text = _binding_field_help(modelo, binding_id, casillas, label, context)
    box = _binding_field_box(modelo, binding_id, casillas, context)
    return label, help_text, box


def _binding_field_label(
    modelo: str, binding_id: str, casillas: tuple[CasillaDefinition, ...], context: WorkFormContext
) -> ModeloFormText:
    labels = (localized_text(casilla.localization_keys, context.language) for casilla in casillas)
    return (
        localized_text((binding_locale_key(modelo, binding_id, "label"),), context.language)
        or next((text for text in labels if text is not None), None)
        or fed_box_label(binding_id, context)
        or unnamed_casilla_label(context.language)
    )


def _binding_field_help(
    modelo: str,
    binding_id: str,
    casillas: tuple[CasillaDefinition, ...],
    label: ModeloFormText,
    context: WorkFormContext,
) -> str | None:
    help_text = resolve_modelo_localization(
        (binding_locale_key(modelo, binding_id, "help"),), locale=context.language.value
    ) or next((text for casilla in casillas if (text := casilla_help(casilla, label.text, context))), None)
    if help_text and normalized_help_text(help_text) == normalized_help_text(label.text):
        help_text = None
    return help_text


def _binding_field_box(
    modelo: str, binding_id: str, casillas: tuple[CasillaDefinition, ...], context: WorkFormContext
) -> str | None:
    return resolve_modelo_localization(
        (binding_locale_key(modelo, binding_id, "box_number"),), locale=context.language.value
    ) or next(
        (
            number
            for casilla in casillas
            if (number := context.placed_boxes.get(str(casilla.id)) or printed_box_number(casilla, None))
        ),
        None,
    )


def _binding_value_state(
    binding: BindingDefinition,
    binding_id: str,
    raw: str | None,
    data_type: str,
    context: WorkFormContext,
) -> tuple[ModeloFormScalar, ModeloFormOrigin, bool]:
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
        origin = held_value_origin(value, required=False)
    return value, origin, typed_unattributed


def project_binding_field(binding_id: str, context: WorkFormContext) -> ModeloFormField:
    """Build one field for a binding input no casilla owns."""
    binding = context.bindings.get(binding_id)
    if binding is None:
        raise ModeloWorkFormLayoutError(f"the layout places binding {binding_id!r}, which the revision does not define")
    casillas = _binding_casillas(binding, context)
    label, help_text, box = _binding_presentation(binding, binding_id, context, casillas)
    raw = None if context.revision is None else context.revision.binding_overrides.get(binding.id)
    data_type = BINDING_DATA_TYPE.get(binding.value.data_type.value, "text")
    policy = source_policy(binding.source)
    editability, reason = binding_input_editability(binding_id, policy.override_policy, context)
    value, origin, typed_unattributed = _binding_value_state(binding, binding_id, raw, data_type, context)
    return ModeloFormField(
        address=ModeloFormBindingAddressV1(binding_id=binding.id),
        box=box,
        label=label,
        help=help_text,
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
        return BOOLEAN_VALUE_TOKENS.get(raw.strip().lower(), raw)
    if data_type in NUMERIC_BINDING_TYPES:
        amount = parse_form_number(raw.strip())
        return raw if amount is None else amount
    return raw
