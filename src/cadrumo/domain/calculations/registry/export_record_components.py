"""Complete adjacent wire components bound to one canonical semantic value."""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING, cast

from ..export_field_kind import CasillaFieldKind
from .errors import RegistryValidationError
from .export_value_policy import ExportValuePolicy

if TYPE_CHECKING:
    from .schema_exports import ExportFieldDefinition, ExportRecordDefinition


def validate_export_record_components(record: ExportRecordDefinition) -> None:
    """Require complete adjacent components bound to one semantic value."""
    fields = tuple(sorted(record.fields, key=lambda field: field.offset or 0))
    component_policies = frozenset(
        {
            ExportValuePolicy.SIGNED_COMPONENT_SIGN,
            ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE,
            ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN,
            ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
            ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
            ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
            ExportValuePolicy.YYYYMMDD_TEXT_MONTH,
            ExportValuePolicy.YYYYMMDD_TEXT_DAY,
        }
    )
    covered: set[int] = set()
    for index, first in enumerate(fields):
        if first.value_policy not in {
            ExportValuePolicy.SIGNED_COMPONENT_SIGN,
            ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN,
            ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
        }:
            continue
        policies, lengths = _component_grammar(fields, index)
        group = fields[index : index + len(policies)]
        _require_component_group(group, policies, lengths, first)
        covered.update(id(field) for field in group)
    if any(id(field) not in covered for field in fields if field.value_policy in component_policies):
        raise RegistryValidationError("component export fields have an unpaired member")


def _component_grammar(
    fields: tuple[ExportFieldDefinition, ...], index: int
) -> tuple[tuple[ExportValuePolicy | None, ...], set[tuple[int, ...]]]:
    first = fields[index]
    lengths: set[tuple[int, ...]]
    if first.value_policy is ExportValuePolicy.YYYYMMDD_TEXT_YEAR:
        policies = (
            ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
            ExportValuePolicy.YYYYMMDD_TEXT_MONTH,
            ExportValuePolicy.YYYYMMDD_TEXT_DAY,
        )
        lengths = {(4, 2, 2)}
    elif index + 1 < len(fields) and fields[index + 1].value_policy is ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE:
        policies = (ExportValuePolicy.SIGNED_COMPONENT_SIGN, ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE)
        lengths = {(1, 13)}
    else:
        policies = (
            first.value_policy,
            ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
            ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
        )
        lengths = {(1, 13, 2), (1, 8, 2)}
    return policies, lengths


def _require_component_group(
    group: tuple[ExportFieldDefinition, ...],
    policies: tuple[ExportValuePolicy | None, ...],
    lengths: set[tuple[int, ...]],
    first: ExportFieldDefinition,
) -> None:
    endpoint = (first.kind, first.casilla_id, first.binding)
    if (
        _component_shape_differs(group, policies, lengths, first)
        or any((field.kind, field.casilla_id, field.binding) != endpoint for field in group)
        or _component_positions_incomplete(group)
        or any(right.offset != cast(int, left.offset) + cast(int, left.length) for left, right in pairwise(group))
    ):
        raise RegistryValidationError(
            f"export field {first.id!r} requires complete adjacent components of one semantic value"
        )


def _component_shape_differs(
    group: tuple[ExportFieldDefinition, ...],
    policies: tuple[ExportValuePolicy | None, ...],
    lengths: set[tuple[int, ...]],
    first: ExportFieldDefinition,
) -> bool:
    return (
        len(group) != len(policies)
        or first.kind not in {CasillaFieldKind.CASILLA, CasillaFieldKind.BINDING}
        or tuple(field.value_policy for field in group) != policies
        or tuple(field.length for field in group) not in lengths
    )


def _component_positions_incomplete(group: tuple[ExportFieldDefinition, ...]) -> bool:
    return any(field.offset is None or field.length is None for field in group)
