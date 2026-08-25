"""Registry formula runtime input-validation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..formula_text_inputs import validated_text_input_casilla_ids
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ._formula_runtime_support import (
    _M130_AGRARIAN_VOLUME_CASILLA,
    _M130_AGRARIAN_WITHHELD_CASILLA,
    _M130_GASTOS_CASILLA,
    _M130_HOME_DEDUCTION_CASILLA,
    _M130_INGRESOS_CASILLA,
    _M130_PAGO_FRACCIONADO_CASILLA,
    _M130_PRIOR_RETURN_RESULT_CASILLA,
    _M130_RETENCIONES_CASILLA,
    _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING,
    _PREVIOUS_YEAR_NET_INCOME_BINDING,
    _modelo_180_snapshot_with_inactive_relation_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_formula_runtime_rejects_non_decimal_input(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="must be a Decimal"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={_M130_INGRESOS_CASILLA: 100},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_non_string_input_key_at_entry(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match=r"input keys must be canonical casilla\.id strings"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={1: Decimal("1")},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_noncanonical_text_input_keys_at_entry(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match=r"text_input keys must be canonical casilla\.id strings"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            text_inputs={1: "general"},
            date_context={"filing_period": date(2026, 3, 31)},
        )

    with pytest.raises(RegistryValidationError, match=r"text_input keys must be canonical casilla\.id strings"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            text_inputs={"bad key": "general"},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_validated_text_inputs_strip_operator_whitespace_before_runtime_use() -> None:
    """Direct service callers get the same stripped text-casilla semantics as CLI callers."""

    assert validated_text_input_casilla_ids({"tipo_renta": " inmobiliaria "}) == {"tipo_renta": "inmobiliaria"}


def test_validated_text_inputs_reject_blank_after_stripping() -> None:
    """Whitespace-only text values cannot silently enter formula or verification channels."""

    with pytest.raises(RegistryValidationError, match="must be a non-empty string"):
        validated_text_input_casilla_ids({"tipo_renta": "   "})


def test_registry_formula_runtime_rejects_binding_id_supplied_as_casilla_input(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry input casilla ids"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_unknown_binding_values(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry binding ids"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                "unknown-binding": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_unknown_relation_values(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            committed_modelo_180_snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 12, 31)},
            relation_values={
                "modelo-180-rel-115-base-anual": Decimal("550.00"),
                "modelo-180-rel-115-retenciones-anual": Decimal("114.00"),
                "unknown-relation": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_relation_values_inactive_for_snapshot_period(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    snapshot = _modelo_180_snapshot_with_inactive_relation_period(registry_tree)

    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 4, 20)},
            relation_values={"modelo-180-rel-115-base-anual": Decimal("1")},
        )


def test_registry_formula_runtime_defaults_filing_period_axis_from_snapshot(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("100"),
            _M130_GASTOS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        date_context={},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert _M130_PAGO_FRACCIONADO_CASILLA in result.values
    assert _M130_PAGO_FRACCIONADO_CASILLA in {entry.target_casilla_id for entry in result.entries}


def test_registry_formula_runtime_rejects_missing_non_snapshot_parameter_axis(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    target = committed_modelo_130_snapshot.revision.parameters[0]
    values = tuple(value.model_copy(update={"date_axis": "devengo_date"}) for value in target.values)
    parameters = (
        target.model_copy(update={"values": values}),
        *committed_modelo_130_snapshot.revision.parameters[1:],
    )
    mutated_revision = committed_modelo_130_snapshot.revision.model_copy(update={"parameters": parameters})
    mutated_snapshot = committed_modelo_130_snapshot.model_copy(update={"revision": mutated_revision})

    with pytest.raises(RegistryValidationError, match="requires date axis 'devengo_date'"):
        calculate_registry_snapshot(
            mutated_snapshot,
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("100"),
                _M130_GASTOS_CASILLA: Decimal("0"),
                _M130_RETENCIONES_CASILLA: Decimal("0"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
            },
            date_context={},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
            },
        )
