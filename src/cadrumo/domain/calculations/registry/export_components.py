"""Reconstruct whole semantic values from adjacent declared export wire components."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .errors import RegistryValidationError
from .export_parse_models import ParsedExportFieldValue
from .export_value_policy import ExportValuePolicy
from .schema_exports import ExportFieldDefinition


def reconstruct_component_values(
    fields: tuple[ExportFieldDefinition, ...], parsed: list[ParsedExportFieldValue]
) -> None:
    """Recombine complete source-ordered components without discarding their raw bytes."""
    for index, field in enumerate(fields):
        if field.value_policy is ExportValuePolicy.INTEGER_PART:
            _reconstruct_unsigned_component_pair(fields, parsed, index)
        if field.value_policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN:
            if (
                index + 1 < len(fields)
                and fields[index + 1].value_policy is ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE
            ):
                _reconstruct_signed_component_pair(parsed, index)
            else:
                _reconstruct_signed_component_triplet(fields, parsed, index)
        if field.value_policy is ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
            _reconstruct_signed_component_triplet(fields, parsed, index)
        if field.value_policy is ExportValuePolicy.YYYYMMDD_TEXT_YEAR:
            _reconstruct_text_date_components(fields, parsed, index)


def _same_component_target(integer_field: ExportFieldDefinition, fraction_field: ExportFieldDefinition) -> bool:
    """Require the same nonempty semantic owner before combining two wire fragments."""
    integer_target = (
        integer_field.kind,
        integer_field.casilla_id,
        integer_field.binding,
        integer_field.producer_key,
        integer_field.projection_ref,
        integer_field.draft_attribute,
        integer_field.computed_key,
    )
    fraction_target = (
        fraction_field.kind,
        fraction_field.casilla_id,
        fraction_field.binding,
        fraction_field.producer_key,
        fraction_field.projection_ref,
        fraction_field.draft_attribute,
        fraction_field.computed_key,
    )
    return integer_target == fraction_target and any(item is not None for item in integer_target[1:])


def _adjacent_components(integer_field: ExportFieldDefinition, fraction_field: ExportFieldDefinition) -> bool:
    """Require complete integer geometry immediately followed by the fraction slot."""
    return (
        integer_field.offset is not None
        and integer_field.length is not None
        and fraction_field.offset == integer_field.offset + integer_field.length
    )


def _reconstruct_unsigned_component_pair(
    fields: tuple[ExportFieldDefinition, ...], parsed: list[ParsedExportFieldValue], index: int
) -> None:
    """Recover a complete contiguous amount only from components of one declared target."""
    if index + 1 >= len(fields):
        return
    integer_field, fraction_field = fields[index : index + 2]
    if fraction_field.value_policy is not ExportValuePolicy.FRACTIONAL_DIGITS:
        return
    if not _same_component_target(integer_field, fraction_field):
        return
    if not _adjacent_components(integer_field, fraction_field):
        return
    integer, fraction = parsed[index : index + 2]
    if integer.value is None or fraction.value is None:
        return
    if not all(part.raw.isascii() and part.raw.isdigit() for part in (integer, fraction)):
        raise RegistryValidationError("unsigned source amount has malformed component bytes")
    amount = Decimal(f"{integer.raw}.{fraction.raw}")
    parsed[index] = integer.model_copy(update={"value": amount})
    parsed[index + 1] = fraction.model_copy(update={"value": amount})


def _reconstruct_signed_component_triplet(
    fields: tuple[ExportFieldDefinition, ...], parsed: list[ParsedExportFieldValue], index: int
) -> None:
    group = fields[index : index + 3]
    if (
        tuple(part.value_policy for part in group)
        != (
            fields[index].value_policy,
            ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
            ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
        )
        or len(group) != 3
    ):
        raise RegistryValidationError("signed source amount has incomplete sign/integer/fraction components")
    sign, integer, fraction = parsed[index : index + 3]
    allowed_signs = (
        {"0", "N"} if fields[index].value_policy is ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN else {" ", "N"}
    )
    _require_signed_component_bytes(sign, integer, fraction, allowed_signs)
    magnitude = Decimal(f"{integer.raw}.{fraction.raw}")
    if _impossible_signed_magnitude(sign.raw, magnitude):
        raise RegistryValidationError("signed source amount has impossible sign/magnitude combination")
    amount = -magnitude if sign.raw == "N" else magnitude
    for part_index in range(index, index + 3):
        parsed[part_index] = parsed[part_index].model_copy(update={"value": amount})


def _reconstruct_signed_component_pair(parsed: list[ParsedExportFieldValue], index: int) -> None:
    """Recombine a sign/magnitude pair while preserving both raw source slots."""
    sign, magnitude = parsed[index : index + 2]
    if sign.raw not in {" ", "N"} or not magnitude.raw.isascii() or not magnitude.raw.isdigit():
        raise RegistryValidationError("signed component pair has invalid sign or magnitude")
    magnitude_amount = Decimal(magnitude.raw).scaleb(-2)
    if sign.raw == "N" and magnitude_amount == 0:
        raise RegistryValidationError("signed component pair cannot encode negative zero")
    amount = -magnitude_amount if sign.raw == "N" else magnitude_amount
    parsed[index] = sign.model_copy(update={"value": amount})
    parsed[index + 1] = magnitude.model_copy(update={"value": amount})


def _reconstruct_text_date_components(
    fields: tuple[ExportFieldDefinition, ...], parsed: list[ParsedExportFieldValue], index: int
) -> None:
    """Reconstruct absence or a real calendar date from all three adjacent raw slots."""
    group = fields[index : index + 3]
    if tuple(part.value_policy for part in group) != (
        ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
        ExportValuePolicy.YYYYMMDD_TEXT_MONTH,
        ExportValuePolicy.YYYYMMDD_TEXT_DAY,
    ):
        raise RegistryValidationError("text YYYYMMDD date has incomplete adjacent components")
    parts = parsed[index : index + 3]
    raw = "".join(part.raw for part in parts)
    if raw == "00000000":
        if any(part.required for part in group):
            raise RegistryValidationError("required text YYYYMMDD date is absent from all three source slots")
        for part_index in range(index, index + 3):
            parsed[part_index] = parsed[part_index].model_copy(update={"value": None})
        return
    try:
        date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError as exc:
        raise RegistryValidationError("text YYYYMMDD components do not form a real calendar date") from exc
    for part_index in range(index, index + 3):
        parsed[part_index] = parsed[part_index].model_copy(update={"value": raw})


def _require_signed_component_bytes(
    sign: ParsedExportFieldValue,
    integer: ParsedExportFieldValue,
    fraction: ParsedExportFieldValue,
    allowed_signs: set[str],
) -> None:
    if (
        sign.raw not in allowed_signs
        or not integer.raw.isascii()
        or not integer.raw.isdigit()
        or not fraction.raw.isascii()
        or not fraction.raw.isdigit()
    ):
        raise RegistryValidationError("signed source amount has malformed component bytes")


def _impossible_signed_magnitude(sign: str, magnitude: Decimal) -> bool:
    return (sign == "N" and magnitude == 0) or (sign == "0" and magnitude != 0)
