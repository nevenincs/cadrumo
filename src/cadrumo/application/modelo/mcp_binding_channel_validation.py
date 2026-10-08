"""Scalar channel parsing and constraints for pinned binding values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import TypeAdapter

from ...domain.calculations.registry.binding_selector_utils import boolean_binding_encoded_values
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_scalars import CalendarDate, DecimalValue, validate_registry_text_scalar
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from .mcp_query_contracts import (
    ModeloBindingValueContractUnsupportedError,
    ModeloBindingValueInvalidError,
)

_DECIMAL = TypeAdapter[Decimal](DecimalValue)
_CALENDAR_DATE = TypeAdapter[str](CalendarDate)


def validate_binding_channel_value(
    binding: BindingDefinition,
    raw: str,
    targets: tuple[CasillaDefinition, ...],
) -> None:
    """Validate a value using its declared scalar channel and bound fields."""
    channel = binding.value.channel
    if channel is BindingValueChannel.DECIMAL:
        _validate_decimal_value(binding, raw, targets)
    elif channel is BindingValueChannel.INTEGER:
        _validate_integer_value(raw, targets)
    elif channel is BindingValueChannel.BOOLEAN:
        _validate_boolean_value(binding, raw)
    elif channel is BindingValueChannel.DATE:
        _validate_date_value(raw)
    elif channel in {BindingValueChannel.ENUM, BindingValueChannel.TEXT}:
        _validate_text_value(binding, raw, targets)
    else:
        raise ModeloBindingValueContractUnsupportedError()


def _validate_decimal_value(
    binding: BindingDefinition,
    raw: str,
    targets: tuple[CasillaDefinition, ...],
) -> None:
    if len(raw) > 128:
        raise ModeloBindingValueInvalidError()
    number = _DECIMAL.validate_python(raw)
    if not number.is_finite():
        raise ModeloBindingValueInvalidError()
    decimal_parts = number.as_tuple()
    if not isinstance(decimal_parts.exponent, int) or abs(decimal_parts.exponent) > 128:
        raise ModeloBindingValueInvalidError()
    if len(decimal_parts.digits) > 128 or len(format(number, "f")) > 128:
        raise ModeloBindingValueInvalidError()
    _validate_encoded_decimal(binding, raw)
    _validate_decimal_constraints(number, targets)


def _validate_encoded_decimal(binding: BindingDefinition, raw: str) -> None:
    encoded = boolean_binding_encoded_values(binding)
    if encoded and raw not in {row.encoded_value for row in encoded}:
        raise ModeloBindingValueInvalidError()


def _validate_decimal_constraints(number: Decimal, targets: tuple[CasillaDefinition, ...]) -> None:
    for target in targets:
        constraints = target.constraints
        if constraints is not None and constraints.violates(number) is not None:
            raise ModeloBindingValueInvalidError()


def _validate_integer_value(raw: str, targets: tuple[CasillaDefinition, ...]) -> None:
    if len(raw) > 64 or not raw.lstrip("-").isdigit() or raw.startswith("+"):
        raise ModeloBindingValueInvalidError()
    canonical_integer = Decimal(str(int(raw)))
    for target in targets:
        constraints = target.constraints
        if constraints is not None and constraints.violates(canonical_integer) is not None:
            raise ModeloBindingValueInvalidError()


def _validate_boolean_value(binding: BindingDefinition, raw: str) -> None:
    encoded = boolean_binding_encoded_values(binding)
    allowed = {row.encoded_value for row in encoded} if encoded else {"true", "false"}
    if raw not in allowed:
        raise ModeloBindingValueInvalidError()


def _validate_date_value(raw: str) -> None:
    declared = _CALENDAR_DATE.validate_python(raw)
    if len(declared) == 8 and declared.isdigit():
        date(int(declared[4:]), int(declared[2:4]), int(declared[:2]))
    else:
        date.fromisoformat(declared)


def _validate_text_value(
    binding: BindingDefinition,
    raw: str,
    targets: tuple[CasillaDefinition, ...],
) -> None:
    official = binding.value.channel is BindingValueChannel.ENUM and binding.value.typed_enum is not None
    for target in targets:
        official = _validate_text_target(target, raw) or official
    if not official:
        raise ModeloBindingValueContractUnsupportedError()


def _validate_text_target(target: CasillaDefinition, raw: str) -> bool:
    official = target.data_type.value != "text"
    if official:
        if target.data_type.value == "nif":
            raise ModeloBindingValueContractUnsupportedError()
        if validate_registry_text_scalar(target.data_type.value, raw) != raw:
            raise ModeloBindingValueInvalidError()
    constraints = target.constraints
    if constraints is not None and (constraints.enum is not None or constraints.pattern is not None):
        official = True
        if constraints.violates_text(raw) is not None:
            raise ModeloBindingValueInvalidError()
    return official
