"""The existing spreadsheet parity scenario decoder, now owned by application."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.coercion import coerce_decimal
from ...core.type_guards import is_object_dict
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId, RelationId
from ..storage.calc_sheets.parity_harness import OperatorInputScenario


def _scenario_decimal_value(value: object) -> Decimal:
    """Decode a scenario scalar through the shared decimal coercion boundary."""
    return coerce_decimal(value) or Decimal("0")


def _scenario_binding_id(value: object, adapter: TypeAdapter[str]) -> BindingId:
    """Decode one canonical binding identifier or retain the registry refusal."""
    try:
        return adapter.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"scenario binding key must be canonical: {value!r}") from exc


def _scenario_relation_id(value: object, adapter: TypeAdapter[str]) -> RelationId:
    """Decode one canonical relation identifier or retain the registry refusal."""
    try:
        return adapter.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"scenario relation key must be canonical: {value!r}") from exc


def _scenario_casilla_decimal_map(node: object) -> dict[CasillaId, Decimal]:
    """Decode an optional casilla-to-decimal scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {
        validated_casilla_id(k, surface="spreadsheet verify scenario casilla.id"): _scenario_decimal_value(v)
        for k, v in node.items()
    }


def _scenario_binding_decimal_map(node: object, adapter: TypeAdapter[str]) -> dict[BindingId, Decimal]:
    """Decode an optional numeric binding scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {_scenario_binding_id(k, adapter): _scenario_decimal_value(v) for k, v in node.items()}


def _scenario_enum_binding_map(node: object, adapter: TypeAdapter[str]) -> dict[BindingId, str]:
    """Decode an optional enum binding scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {_scenario_binding_id(k, adapter): str(v) for k, v in node.items()}


def _scenario_relation_decimal_map(node: object, adapter: TypeAdapter[str]) -> dict[RelationId, Decimal]:
    """Decode an optional relation-to-decimal scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {_scenario_relation_id(k, adapter): _scenario_decimal_value(v) for k, v in node.items()}


def decode_modelo_spreadsheet_scenario(source: bytes | None, *, source_path: Path | None) -> OperatorInputScenario:
    """Decode the existing source shape after the operation proves its digest."""
    if source is None:
        return OperatorInputScenario(scenario_label="empty-defaults")
    if source_path is None:
        raise ValueError("scenario bytes require their source path")
    raw = json.loads(source.decode("utf-8"))
    binding_id_adapter: TypeAdapter[str] = TypeAdapter(BindingId)
    relation_id_adapter: TypeAdapter[str] = TypeAdapter(RelationId)
    return OperatorInputScenario(
        inputs_by_casilla_id=_scenario_casilla_decimal_map(raw.get("inputs_by_casilla_id")),
        bindings=_scenario_binding_decimal_map(raw.get("bindings"), binding_id_adapter),
        enum_bindings=_scenario_enum_binding_map(raw.get("enum_bindings"), binding_id_adapter),
        relation_values=_scenario_relation_decimal_map(raw.get("relation_values"), relation_id_adapter),
        expected_by_casilla_id=_scenario_casilla_decimal_map(raw.get("expected_by_casilla_id")),
        scenario_label=str(raw.get("scenario_label") or source_path.stem),
    )


__all__ = ["decode_modelo_spreadsheet_scenario"]
