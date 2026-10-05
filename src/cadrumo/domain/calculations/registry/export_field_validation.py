"""Validation rules for registry-declared export fields."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from ..export_field_kind import CasillaFieldKind
from .errors import RegistryValidationError
from .export_semantics import ExportSemanticPayloadAxis, export_semantic_payload_axis
from .export_value_policy import ExportValuePolicy, export_value_policy_wire_length
from .fixed_width_codec import validate_fixed_width_shape

if TYPE_CHECKING:
    from .schema_exports import ExportFieldDefinition


_VALUE_POLICY_SHAPES: Mapping[ExportValuePolicy, tuple[str, str, str, bool, str | None]] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.UNSIGNED_INTEGER: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.ENUMERATED_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.FOUR_DIGIT_YEAR: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.TWO_DIGIT_MONTH: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.TWO_DIGIT_DAY: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.IMPLIED_DECIMAL: ("decimal", "left_zero", "right", True, None),
    ExportValuePolicy.INTEGER_PART: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.FRACTIONAL_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.YYYYMMDD: ("date", "none", "none", False, "aaaammdd"),
    ExportValuePolicy.DDMMYYYY: ("date", "none", "none", False, "ddmmaaaa"),
    ExportValuePolicy.DIGIT_STRING: ("text", "none", "none", False, None),
    ExportValuePolicy.IDENTIFIER_DIGITS: ("text", "none", "none", False, None),
    ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT: ("text", "right_space", "left", False, None),
    ExportValuePolicy.SIGNED_COMPONENT_SIGN: ("text", "none", "none", False, None),
    ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE: ("money", "left_zero", "right", False, None),
    ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN: ("text", "none", "none", False, None),
    ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.YYYYMMDD_TEXT_YEAR: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.YYYYMMDD_TEXT_MONTH: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.YYYYMMDD_TEXT_DAY: ("integer", "left_zero", "right", False, None),
}


_VALUE_POLICY_UNRENDERABLE_KINDS = frozenset(
    {CasillaFieldKind.FILLER, CasillaFieldKind.LITERAL, CasillaFieldKind.CHECKSUM},
)


_SIGN_BEARING_DATA_TYPES: Final[frozenset[str]] = frozenset({"money", "decimal", "integer"})


_SCALED_AMOUNT_DOMAIN_SHAPE: Final[tuple[str, str, str, bool, str | None]] = (
    "decimal",
    "left_zero",
    "right",
    True,
    None,
)


_SIGNED_MONEY_DOMAIN_SHAPE: Final[tuple[str, str, str, bool, str | None]] = (
    "money",
    "left_zero",
    "right",
    False,
    None,
)


_MONEY_IMPLIED_DECIMALS: Final[int] = 2


def validate_export_field_kind(field: ExportFieldDefinition) -> None:
    """Validate semantic payload, render shape and taxpayer-specific requirements."""
    _validate_field_semantic_payload(field)
    if field.literal_fact is not None and field.kind != CasillaFieldKind.LITERAL:
        raise RegistryValidationError(
            f"export field {field.id!r} declares literal_fact on kind {field.kind.value!r}; only a literal can",
        )
    _validate_field_render_shape(field)
    _validate_required_for(field)
    _validate_required_with(field)
    _validate_design_type(field)


def export_field_wire_shape(field: ExportFieldDefinition) -> tuple[str, str, str, bool, str | None]:
    """Project one field's declared shape onto policy-constrained wire axes."""
    return (
        field.data_type,
        field.padding,
        field.justification,
        field.decimals is not None,
        field.date_format,
    )


def validate_export_allowed_values(field: ExportFieldDefinition) -> None:
    """Constrain an exact reviewed semantic integer domain."""
    if failure := _allowed_values_failure(field):
        raise RegistryValidationError(failure)


def validate_export_value_policy(field: ExportFieldDefinition) -> None:
    """Require each explicit policy to match its complete fixed-width shape."""
    if field.value_policy is None:
        return
    if field.kind in _VALUE_POLICY_UNRENDERABLE_KINDS:
        raise RegistryValidationError(
            f"export field {field.id!r} cannot declare value_policy on kind {field.kind!r}",
        )
    if field.signed or _VALUE_POLICY_SHAPES.get(field.value_policy) != field.wire_shape():
        raise RegistryValidationError(
            f"export field {field.id!r} value_policy {field.value_policy.value!r} conflicts with its field shape",
        )
    expected_length = export_value_policy_wire_length(field.value_policy)
    if expected_length is not None and field.length != expected_length:
        raise RegistryValidationError(
            f"export field {field.id!r} value_policy {field.value_policy!r} requires length {expected_length}",
        )
    if field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS and field.allowed_values is None:
        raise RegistryValidationError(
            f"export field {field.id!r} value_policy {field.value_policy.value!r} requires allowed_values",
        )


def validate_export_field_decimals(field: ExportFieldDefinition) -> None:
    """Require an explicit scale on every decimal field."""
    if field.kind == CasillaFieldKind.FILLER:
        return
    if _validate_literal_export_field_decimals(field):
        return
    if field.data_type == "decimal":
        _validate_decimal_export_field_decimals(field)
    elif field.decimals is not None:
        raise RegistryValidationError(
            f"export field {field.id!r} declares decimals but its data_type is {field.data_type!r}",
        )


def _validate_literal_export_field_decimals(field: ExportFieldDefinition) -> bool:
    if field.kind != CasillaFieldKind.LITERAL or field.data_type != "text" or field.decimals is None:
        return False
    literal = field.literal
    if literal is None or not literal.isascii() or not literal.isdigit() or field.decimals >= len(literal):
        raise RegistryValidationError(f"literal export field {field.id!r} declares an invalid numeric scale")
    return True


def _validate_decimal_export_field_decimals(field: ExportFieldDefinition) -> None:
    if field.decimals is None:
        raise RegistryValidationError(f"decimal export field {field.id!r} must declare decimals")
    if field.length is not None and field.decimals >= field.length:
        raise RegistryValidationError(
            f"decimal export field {field.id!r} declares {field.decimals} decimals "
            f"which leaves no integer digits in its {field.length}-byte slot",
        )


def _field_semantic_payloads(field: ExportFieldDefinition) -> dict[ExportSemanticPayloadAxis, object | None]:
    return {
        ExportSemanticPayloadAxis.CASILLA_ID: field.casilla_id,
        ExportSemanticPayloadAxis.BINDING: field.binding,
        ExportSemanticPayloadAxis.LITERAL: field.literal,
        ExportSemanticPayloadAxis.PRODUCER_KEY: field.producer_key,
        ExportSemanticPayloadAxis.PROJECTION_REF: field.projection_ref,
        ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE: field.draft_attribute,
        ExportSemanticPayloadAxis.COMPUTED_KEY: field.computed_key,
    }


def _validate_design_type(field: ExportFieldDefinition) -> None:
    """Refuse a sign that contradicts the type the official design prints."""
    if field.design_type is None:
        return
    if str(field.data_type) not in _SIGN_BEARING_DATA_TYPES:
        raise RegistryValidationError(
            f"export field {field.id!r} declares design_type but carries {field.data_type!r}, which has no sign",
        )
    if field.design_type == "N" and not field.signed:
        raise RegistryValidationError(
            f"export field {field.id!r} is typed N (numerico con signo) by its design but declares unsigned",
        )
    if field.design_type == "Num" and field.signed:
        raise RegistryValidationError(
            f"export field {field.id!r} is typed Num (numerico sin signo) by its design but declares signed",
        )


def _validate_required_for(field: ExportFieldDefinition) -> None:
    """Admit a legal-form requirement only where the export can evaluate it."""
    if field.required_for is None:
        return
    if field.kind != CasillaFieldKind.HEADER:
        raise RegistryValidationError(
            f"export field {field.id!r} can declare required_for only on a header field, not {field.kind.value!r}",
        )
    if field.required:
        raise RegistryValidationError(
            f"export field {field.id!r} is required unconditionally and cannot also declare required_for",
        )


def _validate_required_with(field: ExportFieldDefinition) -> None:
    """Admit a block anchor only on a casilla the export can read beside its anchor."""
    if field.required_with is None:
        return
    if field.kind != CasillaFieldKind.CASILLA:
        raise RegistryValidationError(
            f"export field {field.id!r} can declare required_with only on a casilla field, not {field.kind.value!r}",
        )


def _validate_field_semantic_payload(field: ExportFieldDefinition) -> None:
    payloads = _field_semantic_payloads(field)
    required = export_semantic_payload_axis(field.kind)
    declared = tuple(axis for axis, value in payloads.items() if value is not None)
    if failure := _semantic_payload_failure(field, required=required, declared=declared):
        raise RegistryValidationError(failure)
    if field.kind == CasillaFieldKind.FILLER and field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} filler must declare length")


def _semantic_payload_failure(
    field: ExportFieldDefinition,
    *,
    required: ExportSemanticPayloadAxis | None,
    declared: tuple[ExportSemanticPayloadAxis, ...],
) -> str | None:
    if required is None:
        if declared:
            return (
                f"export field {field.id!r} kind {field.kind.value!r} must not declare semantic payloads: "
                f"{', '.join(axis.value for axis in declared)}"
            )
        return None
    if declared != (required,):
        declared_description = ", ".join(axis.value for axis in declared) if declared else "none"
        return (
            f"export field {field.id!r} kind {field.kind.value!r} must declare only {required.value}; "
            f"declared {declared_description}"
        )
    return None


def _validate_field_render_shape(field: ExportFieldDefinition) -> None:
    field.validate_decimals()
    validate_fixed_width_shape(field)
    field.validate_value_policy()
    field.validate_allowed_values()


def _allowed_values_declaration_failure(
    field: ExportFieldDefinition,
    allowed_values: tuple[str, ...],
) -> str | None:
    if field.value_policy is not None and field.value_policy is not ExportValuePolicy.ENUMERATED_DIGITS:
        return (
            f"export field {field.id!r} allowed_values requires value_policy "
            f"{ExportValuePolicy.ENUMERATED_DIGITS.value!r} or no value policy at all"
        )
    if not allowed_values or len(set(allowed_values)) != len(allowed_values):
        return f"export field {field.id!r} allowed_values must be non-empty and unique"
    if _allowed_values_shape_is_invalid(field):
        return (
            f"export field {field.id!r} allowed_values requires an unsigned right-justified "
            "left-zero-padded fixed-width integer, the same shape scaled by a declared decimal count, "
            "or a signed left-zero-padded money amount"
        )
    return None


def _allowed_values_member_failure(
    field: ExportFieldDefinition,
    allowed_values: tuple[str, ...],
) -> str | None:
    length = field.length
    if length is None:
        return f"export field {field.id!r} allowed_values requires a declared length"
    scale = _MONEY_IMPLIED_DECIMALS if field.data_type == "money" else (field.decimals or 0)
    unit_digit_budget = length - scale
    invalid = tuple(value for value in allowed_values if not _is_canonical_digit_run(value, unit_digit_budget))
    if invalid:
        return f"export field {field.id!r} allowed_values contains noncanonical or out-of-width entries: {invalid!r}"
    return None


def _allowed_values_failure(field: ExportFieldDefinition) -> str | None:
    """Return the first contradiction in a closed export value domain."""
    allowed_values = field.allowed_values
    if allowed_values is None:
        return None
    if failure := _allowed_values_declaration_failure(field, allowed_values):
        return failure
    return _allowed_values_member_failure(field, allowed_values)


def _allowed_values_shape_is_invalid(field: ExportFieldDefinition) -> bool:
    """Return whether a field cannot render a closed value domain canonically."""
    if field.kind in _VALUE_POLICY_UNRENDERABLE_KINDS or field.length is None:
        return True
    shape = export_field_wire_shape(field)
    if field.signed:
        return field.value_policy is not None or shape != _SIGNED_MONEY_DOMAIN_SHAPE
    if field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS:
        return shape != _VALUE_POLICY_SHAPES[ExportValuePolicy.ENUMERATED_DIGITS]
    return shape != _SCALED_AMOUNT_DOMAIN_SHAPE


def _is_canonical_digit_run(value: str, length: int) -> bool:
    """Accept only a zero-canonical ASCII digit run that fits the wire slot."""
    return bool(value) and value.isascii() and value.isdigit() and str(int(value)) == value and len(value) <= length
