"""Project reviewed scalar and binding values into work-form fields."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from ...core.absence_attestation_family import AbsenceAttestationFamily
from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.modelo_localization import binding_locale_key, resolve_modelo_localization
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_form_layouts import FormPlacementDefinition
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.filing.schema import ModeloValueKind
from .printed_boxes import printed_box_number
from .source_policy import source_policy
from .work_form_binding_statement import with_binding_statements
from .work_form_errors import ModeloWorkFormLayoutError
from .work_form_facts import ModeloFormFieldFacts
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
from .work_form_field_vocabulary import (
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormBlocker,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormText,
    ModeloFormValueSource,
    field_standing,
)
from .work_form_localization import (
    casilla_help,
    fed_box_label,
    localized_casilla_label,
    localized_text,
    normalized_help_text,
    unnamed_casilla_label,
)
from .work_form_models import ModeloFormField, revised_field
from .work_form_rates import parse_form_number
from .work_form_sources import FIXED_BY_THE_FORM, bound_value_source, resolver_value_source
from .work_review import ModeloWorkReviewCasilla


def casilla_facts(
    casilla_id: str, context: WorkFormContext, placement: FormPlacementDefinition | None
) -> ModeloFormFieldFacts:
    """Classify one casilla: its printed box, its value, where the value stands and what blocks it."""
    row, casilla = _casilla_source(casilla_id, context)
    required = casilla_id in context.required
    origin = casilla_origin(row, context, required=required or casilla_id in context.calculation_required.casilla_ids)
    origin, value = _unworked_origin(casilla_id, origin, row.value, context)
    blockers = tuple(ModeloFormBlocker(code=blocker.native_code) for blocker in row.blocked_by)
    return ModeloFormFieldFacts(
        address=ModeloFormCasillaAddressV1(casilla_id=row.casilla_id),
        box=printed_box_number(casilla, placement),
        value=value,
        origin=origin,
        standing=field_standing(origin, blockers, recorded=context.filed),
        blockers=blockers,
        first_binding_id=row.concrete_bindings[0].binding_id if row.concrete_bindings else None,
    )


def design_constant_facts(
    facts: ModeloFormFieldFacts, fixed: ModeloFormScalar, *, recorded: bool
) -> ModeloFormFieldFacts:
    """A casilla whose value the official design fixes: informational, holding the design's figure."""
    return replace(
        facts,
        origin=ModeloFormOrigin.INFORMATIONAL,
        value=fixed,
        standing=field_standing(ModeloFormOrigin.INFORMATIONAL, facts.blockers, recorded=recorded),
        design_constant=True,
    )


def casilla_label(casilla: CasillaDefinition, context: WorkFormContext) -> ModeloFormText:
    """A casilla's label in the form's language, a rotating slot naming its own year; an unnamed box otherwise."""
    ejercicio = context.review.period.filing_year
    return localized_casilla_label(casilla, context.language, ejercicio=ejercicio) or unnamed_casilla_label(
        context.language
    )


def project_casilla_field(
    facts: ModeloFormFieldFacts,
    context: WorkFormContext,
    placement: FormPlacementDefinition | None,
    also_appears_on: tuple[str, ...] = (),
) -> ModeloFormField:
    """Present one classified casilla as a field: its words, its edit controls and where its value comes from.

    A box the design fixes is presented from its own classification and then
    fixed, so it keeps every mark its own value gives and shows the design's.
    """
    if not facts.design_constant:
        return _casilla_field(facts, context, placement, also_appears_on)
    own = casilla_facts(facts_casilla_id(facts), context, placement)
    return revised_field(
        _casilla_field(own, context, placement, also_appears_on),
        editability=ModeloFormEditability.DESIGN_CONSTANT,
        not_writable_reason=None,
        origin=facts.origin,
        unattributed=False,
        value=facts.value,
        source=FIXED_BY_THE_FORM,
        standing=facts.standing,
    )


def facts_casilla_id(facts: ModeloFormFieldFacts) -> str:
    """The casilla a casilla's facts classify."""
    address = facts.address
    if not isinstance(address, ModeloFormCasillaAddressV1):
        raise TypeError("a casilla field is presented from a casilla's facts")
    return str(address.casilla_id)


def _casilla_field(
    facts: ModeloFormFieldFacts,
    context: WorkFormContext,
    placement: FormPlacementDefinition | None,
    also_appears_on: tuple[str, ...],
) -> ModeloFormField:
    row, casilla = _casilla_source(facts_casilla_id(facts), context)
    label = casilla_label(casilla, context)
    origin = facts.origin
    editability, reason = casilla_editability(row, context)
    field = ModeloFormField(
        address=facts.address,
        box=facts.box,
        label=label,
        help=casilla_help(casilla, label.text, context),
        data_type=row.data_type,
        value=facts.value,
        origin=origin,
        editability=editability,
        not_writable_reason=reason,
        required=row.casilla_id in context.required,
        unattributed=_unattributed(origin, row),
        role=casilla_field_role(row),
        bindings=summarize_bindings(row),
        source=_value_source(row, context),
        formula_id=row.formula_id,
        formula_operands=() if row.concrete_formula is None else row.concrete_formula.operand_refs,
        blockers=facts.blockers,
        constraints=row.constraints,
        legal_refs=row.legal_refs,
        also_appears_on=also_appears_on,
        standing=facts.standing,
        stated_absent=_stated_absence(origin, row, context),
    )
    return with_binding_statements(field, context)


def _value_source(row: ModeloWorkReviewCasilla, context: WorkFormContext) -> ModeloFormValueSource | None:
    """Name where a box's value comes from: its bindings, else the resolver that supplied the box directly."""
    from_bindings = bound_value_source(
        tuple(origin.binding_id for origin in row.concrete_bindings),
        bindings=context.bindings,
        aeat_data_binding_ids=context.aeat_data_bindings,
        target=context.review.period,
    )
    supplied = context.source_supplied.get(row.casilla_id)
    if from_bindings is None and supplied is not None:
        return resolver_value_source(supplied)
    return from_bindings


def _unworked_origin(
    casilla_id: str, origin: ModeloFormOrigin, value: ModeloFormScalar | None, context: WorkFormContext
) -> tuple[ModeloFormOrigin, ModeloFormScalar | None]:
    if casilla_id in context.unworked and origin not in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}:
        # The calculation said this box could not be worked out: whatever it holds is not a figure.
        return ModeloFormOrigin.CALCULATION_FAILED, None
    return origin, value


def _unattributed(origin: ModeloFormOrigin, row: ModeloWorkReviewCasilla) -> bool:
    return origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM or (
        origin is ModeloFormOrigin.OPTIONAL_EMPTY and row.realised_kind is not ModeloValueKind.EMPTY
    )


def _stated_absence(
    origin: ModeloFormOrigin, row: ModeloWorkReviewCasilla, context: WorkFormContext
) -> AbsenceAttestationFamily | None:
    if origin not in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}:
        return None
    return next(
        (context.stated[bound.binding_id] for bound in row.concrete_bindings[:1] if bound.binding_id in context.stated),
        None,
    )


def _casilla_source(casilla_id: str, context: WorkFormContext) -> tuple[ModeloWorkReviewCasilla, CasillaDefinition]:
    row = context.rows.get(casilla_id)
    casilla = context.casillas.get(casilla_id)
    if row is None or casilla is None:
        raise ModeloWorkFormLayoutError(
            f"the layout places casilla {casilla_id!r}, which the revision does not define",
            translated_message="application.modelo.errors.work_form_layout_casilla_undefined",
            context={"casilla_id": str(casilla_id)},
        )
    return row, casilla


def _binding_casillas(binding: BindingDefinition, context: WorkFormContext) -> tuple[CasillaDefinition, ...]:
    """Follow declared ownership, provider and unambiguous export coordinates, in that order."""
    ids = [context.casilla_by_binding.get(binding.id)]
    provider = binding.provider
    if isinstance(provider, ManualInputProvider):
        ids.append(provider.casilla_id)
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
    modelo = context.snapshot.modelo.id
    label = _binding_field_label(modelo, binding_id, casillas, context)
    help_text = _binding_field_help(modelo, binding_id, casillas, label, context)
    box = _binding_field_box(modelo, binding_id, casillas, context)
    return label, help_text, box


def _binding_field_label(
    modelo: str, binding_id: str, casillas: tuple[CasillaDefinition, ...], context: WorkFormContext
) -> ModeloFormText:
    ejercicio = context.review.period.filing_year
    labels = (localized_casilla_label(casilla, context.language, ejercicio=ejercicio) for casilla in casillas)
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
    ) or next(
        (text for casilla in casillas if ((text := casilla_help(casilla, label.text, context)) is not None and text)),
        None,
    )
    if (help_text is not None and help_text) and normalized_help_text(help_text) == normalized_help_text(label.text):
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
            if (
                (number := context.placed_boxes.get(casilla.id) or printed_box_number(casilla, None)) is not None
                and number
            )
        ),
        None,
    )


def _binding_value_state(
    binding: BindingDefinition,
    binding_id: str,
    raw: str | None,
    data_type: str,
    context: WorkFormContext,
) -> tuple[ModeloFormScalar, ModeloFormOrigin]:
    value = _binding_value(raw, data_type)
    if context.overridden is not None and binding_id in context.overridden:
        return value, ModeloFormOrigin.ENTERED
    if raw is None:
        needed = binding_id in context.calculation_required.binding_ids or _feeds_an_unworked_box(binding_id, context)
        return value, ModeloFormOrigin.NEEDS_INPUT if needed else ModeloFormOrigin.OPTIONAL_EMPTY
    return value, _held_binding_origin(binding, binding_id, value, context)


def _typed_unattributed(origin: ModeloFormOrigin, raw: str | None) -> bool:
    # Read from the classified origin, as the casilla side reads it (``_unattributed``): a value waiting to be
    # confirmed, or an optional box holding what the calculation gave it, is nobody's recorded entry.
    return origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM or (
        origin is ModeloFormOrigin.OPTIONAL_EMPTY and raw is not None
    )


def _held_binding_origin(
    binding: BindingDefinition, binding_id: str, value: ModeloFormScalar, context: WorkFormContext
) -> ModeloFormOrigin:
    """Classify a value the calculation holds for a binding nobody is recorded as entering."""
    if binding.source is not BindingSourceKind.MANUAL_INPUT:
        return ModeloFormOrigin.IMPORTED
    if context.source_supplied_bindings.get(binding_id) is not None and context.overridden is not None:
        # The revision's own source trace names the resolver that supplied this slot and the operator's
        # overrides are recorded, so the value is derived from the filer's records, not assumed. Absence of
        # a node proves nothing: a held value no resolver claims stays assumed, as it does on the casilla
        # side (``_operator_entry_origin``).
        return ModeloFormOrigin.IMPORTED
    return held_value_origin(value, required=binding_id in context.calculation_required.binding_ids)


def _feeds_an_unworked_box(binding_id: str, context: WorkFormContext) -> bool:
    """Whether the calculation could not work out a box this binding feeds, so its empty value is not optional.

    A box the calculation computes that holds nothing after a calculation, or one
    a calculation note says could not be worked out, waits on what feeds it.
    """
    if context.review.calculation_revision_id is None:
        return False
    for casilla_id in context.fed_casillas.get(binding_id, ()):
        row = context.rows.get(casilla_id)
        if casilla_id in context.unworked or (
            row is not None
            and row.declared_input_kind is InputKind.COMPUTED
            and row.realised_kind is ModeloValueKind.EMPTY
        ):
            return True
    return False


def binding_facts(binding_id: str, context: WorkFormContext) -> ModeloFormFieldFacts:
    """Classify one binding input no casilla owns: its value and where the value stands."""
    binding = _binding_definition(binding_id, context)
    raw = None if context.revision is None else context.revision.binding_overrides.get(binding.id)
    data_type = BINDING_DATA_TYPE.get(binding.value.data_type.value, "text")
    value, origin = _binding_value_state(binding, binding_id, raw, data_type, context)
    return ModeloFormFieldFacts(
        address=ModeloFormBindingAddressV1(binding_id=binding.id),
        box=None,
        value=value,
        origin=origin,
        standing=field_standing(origin, recorded=context.filed),
        blockers=(),
        first_binding_id=binding.id,
    )


def _binding_definition(binding_id: str, context: WorkFormContext) -> BindingDefinition:
    binding = context.bindings.get(binding_id)
    if binding is None:
        raise ModeloWorkFormLayoutError(
            f"the layout places binding {binding_id!r}, which the revision does not define",
            translated_message="application.modelo.errors.work_form_layout_binding_undefined",
            context={"binding_id": str(binding_id)},
        )
    return binding


def project_binding_field(facts: ModeloFormFieldFacts, context: WorkFormContext) -> ModeloFormField:
    """Present one classified binding input no casilla owns as a field."""
    address = facts.address
    if not isinstance(address, ModeloFormBindingAddressV1):
        raise TypeError("a binding field is presented from a binding's facts")
    binding_id = address.binding_id
    binding = _binding_definition(binding_id, context)
    casillas = _binding_casillas(binding, context)
    label, help_text, box = _binding_presentation(binding, binding_id, context, casillas)
    raw = None if context.revision is None else context.revision.binding_overrides.get(binding.id)
    policy = source_policy(binding.source)
    editability, reason = binding_input_editability(binding_id, policy.override_policy, context)
    origin = facts.origin
    field = ModeloFormField(
        address=address,
        box=box,
        label=label,
        help=help_text,
        data_type=BINDING_DATA_TYPE.get(binding.value.data_type.value, "text"),
        value=facts.value,
        origin=origin,
        editability=editability,
        not_writable_reason=reason,
        required=False,
        unattributed=_typed_unattributed(origin, raw),
        bindings=(ModeloFormBinding(binding_id=binding.id, policy=policy, resolved=raw is not None),),
        source=_binding_field_source(binding, origin, context),
        legal_refs=tuple(binding.legal_refs),
        standing=facts.standing,
        stated_absent=context.stated.get(binding.id) if origin is ModeloFormOrigin.ENTERED else None,
    )
    return with_binding_statements(field, context)


def _binding_field_source(
    binding: BindingDefinition, origin: ModeloFormOrigin, context: WorkFormContext
) -> ModeloFormValueSource | None:
    """Name where a binding field's value comes from: its own declaration, else the resolver that supplied it."""
    supplied = context.source_supplied_bindings.get(binding.id)
    if supplied is not None and origin is ModeloFormOrigin.IMPORTED:
        return resolver_value_source(supplied)
    return bound_value_source(
        (binding.id,),
        bindings=context.bindings,
        aeat_data_binding_ids=context.aeat_data_bindings,
        target=context.review.period,
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
