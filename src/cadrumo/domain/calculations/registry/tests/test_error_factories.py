"""Tests for the typed-context factories on registry error classes.

Pins the contract from the linkage-design audit decision (`registry-error-typed-context-factories`):
each
canonical raise scenario is a classmethod factory; the resulting
error carries a pinned ``context`` dict with named keys downstream
consumers (locale templates, CLI JSON emit) can rely on.

Tests assert against the EXTERNAL contract (the context dict's
keys and the translated_message identifier) rather than the
factory's internal implementation, satisfying the no-tautological-
tests rule.
"""

from __future__ import annotations

import pytest

from .....core import CasillaId, validated_casilla_id
from ..errors import RegistrySnapshotError, RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_REFERENCED_BEFORE_EVALUATION_CASILLA: CasillaId = validated_casilla_id(
    "0719",
    surface="_REFERENCED_BEFORE_EVALUATION_CASILLA",
)


def test_for_unsupported_op_pins_op_key() -> None:
    err = RegistryValidationError.for_unsupported_op("frobulate")
    assert err.context == {"op": "frobulate"}
    assert err.translated_message == "errors.calc.unsupported_op"


def test_for_unsupported_comparison_op_pins_op_key() -> None:
    err = RegistryValidationError.for_unsupported_comparison_op("notequal")
    assert err.context == {"op": "notequal"}
    assert err.translated_message == "errors.calc.unsupported_comparison_op"


def test_for_unknown_parameter_pins_parameter_id_key() -> None:
    err = RegistryValidationError.for_unknown_parameter(parameter_id="irpf-estatal-base")
    assert err.context == {"parameter_id": "irpf-estatal-base"}
    assert err.translated_message == "errors.calc.parameter_unknown"


def test_for_dispatch_key_unknown_pins_full_dispatch_envelope() -> None:
    err = RegistryValidationError.for_dispatch_key_unknown(
        op="lookup_bracket_by_ccaa",
        binding_id="profile.ccaa",
        dispatch_key="MD",
        available_keys=("CT", "AN", "VC"),
    )
    assert err.context == {
        "op": "lookup_bracket_by_ccaa",
        "binding_id": "profile.ccaa",
        "dispatch_key": "MD",
        "available_keys": "AN,CT,VC",  # sorted+joined
    }
    assert err.translated_message == "errors.calc.dispatch_key_unknown"


def test_for_lookup_dispatch_arg_kind_pins_position_and_kind() -> None:
    err = RegistryValidationError.for_lookup_dispatch_arg_kind(
        op="lookup_bracket_by_entity_type",
        position="args[1]",
        expected_kind="binding",
    )
    assert err.context == {
        "op": "lookup_bracket_by_entity_type",
        "position": "args[1]",
        "expected_kind": "binding",
    }


def test_for_lookup_dispatch_arg_count_pins_expected_arity() -> None:
    err = RegistryValidationError.for_lookup_dispatch_arg_count(
        op="lookup_parameter_by_entity_type",
        expected="3",
    )
    assert err.context == {"op": "lookup_parameter_by_entity_type", "expected": "3"}


def test_for_dispatch_parameter_kind_pins_parameter_and_op() -> None:
    err = RegistryValidationError.for_dispatch_parameter_kind(
        parameter_id="is-tipo-general",
        op="lookup_parameter_by_entity_type",
    )
    assert err.context == {
        "parameter_id": "is-tipo-general",
        "op": "lookup_parameter_by_entity_type",
    }


def test_for_enum_binding_value_missing_pins_binding_and_op() -> None:
    err = RegistryValidationError.for_enum_binding_value_missing(binding_id="profile.ccaa", op="lookup_bracket_by_ccaa")
    assert err.context == {"binding_id": "profile.ccaa", "op": "lookup_bracket_by_ccaa"}


def test_for_binding_value_missing_pins_binding_id_only() -> None:
    err = RegistryValidationError.for_binding_value_missing(binding_id="irpf.previous_year")
    assert err.context == {"binding_id": "irpf.previous_year"}


def test_for_relation_value_missing_pins_relation_id() -> None:
    err = RegistryValidationError.for_relation_value_missing(relation_id="iva.annual.q1q4")
    assert err.context == {"relation_id": "iva.annual.q1q4"}


def test_for_casilla_referenced_before_evaluation_pins_casilla_id() -> None:
    err = RegistryValidationError.for_casilla_referenced_before_evaluation(
        casilla_id=_REFERENCED_BEFORE_EVALUATION_CASILLA,
    )
    assert err.context == {"casilla_id": _REFERENCED_BEFORE_EVALUATION_CASILLA}


def test_for_unknown_input_casilla_ids_sorts_and_joins() -> None:
    err = RegistryValidationError.for_unknown_input_casilla_ids(casilla_ids=("9999999", "0001", "0002"))
    assert err.context == {"casilla_ids": "0001,0002,9999999"}
    assert err.translated_message == "errors.calc.unknown_input_casillas"


def test_for_computed_supplied_as_input_sorts_and_joins() -> None:
    err = RegistryValidationError.for_computed_supplied_as_input(casilla_ids=("0719", "0511"))
    assert err.context == {"casilla_ids": "0511,0719"}


def test_for_bracket_no_window_pins_parameter_and_as_of() -> None:
    err = RegistryValidationError.for_bracket_no_window(parameter_id="irpf-2024-estatal", as_of="2026-03-31")
    assert err.context == {"parameter_id": "irpf-2024-estatal", "as_of": "2026-03-31"}


def test_for_bracket_no_coverage_pins_parameter_and_base() -> None:
    err = RegistryValidationError.for_bracket_no_coverage(parameter_id="irpf-2024-estatal", base="999999.99")
    assert err.context == {"parameter_id": "irpf-2024-estatal", "base": "999999.99"}


def test_for_bracket_negative_base_pins_parameter_and_base() -> None:
    err = RegistryValidationError.for_bracket_negative_base(parameter_id="irpf-2024-estatal", base="-500.00")
    assert err.context == {"parameter_id": "irpf-2024-estatal", "base": "-500.00"}


def test_for_divide_by_zero_has_no_context_keys() -> None:
    err = RegistryValidationError.for_divide_by_zero()
    assert err.context is None
    assert err.translated_message == "errors.calc.divide_by_zero"


def test_for_empty_expression_has_no_context_keys() -> None:
    err = RegistryValidationError.for_empty_expression()
    assert err.context is None
    assert err.translated_message == "errors.calc.empty_expression"


def test_snapshot_error_factory_pins_modelo_id() -> None:
    err = RegistrySnapshotError.for_modelo_not_registered(modelo_id="999")
    assert err.context == {"modelo_id": "999"}
    assert err.translated_message == "errors.snapshot.modelo_not_registered"


def test_factories_return_correct_subclass_instances() -> None:
    """Each factory returns its declaring subclass (Self), not the base."""
    assert isinstance(RegistryValidationError.for_unsupported_op("x"), RegistryValidationError)
    assert isinstance(
        RegistrySnapshotError.for_modelo_not_registered(modelo_id="999"),
        RegistrySnapshotError,
    )
