"""Static completeness gate for the explicit IVA ledger observation role cutover."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CADRUMO_ROOT = Path(__file__).parents[4]
_MODELOS_ROOT = _CADRUMO_ROOT / "_data" / "registry" / "aeat" / "modelos"
_INFORMATIONAL_BINDING_IDS = frozenset(
    {
        "modelo-303-criterio-caja-entregas-art75-base",
        "modelo-303-criterio-caja-entregas-art75-cuota",
        "modelo-303-criterio-caja-adquisiciones-base",
        "modelo-303-criterio-caja-adquisiciones-cuota",
    }
)
_MONETARY_TREATMENTS = ["none", "taxpayer_regime", "supplier_regime"]


def _constructor_calls(name: str) -> Iterator[ast.Call]:
    for path in _CADRUMO_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            constructor_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            if constructor_name == name:
                yield node


def _binding_records(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        if value.get("source") == "ledger_iva_aggregation":
            yield value
        for child in value.values():
            yield from _binding_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _binding_records(child)


def test_direct_iva_ledger_constructors_declare_the_required_role() -> None:
    expected_counts = {
        "IvaLedgerObservation": 51,
        "IvaLedgerCandidate": 14,
    }

    for name, expected_count in expected_counts.items():
        calls = tuple(_constructor_calls(name))
        missing = [call for call in calls if not any(keyword.arg == "observation_role" for keyword in call.keywords)]
        assert len(calls) == expected_count
        assert missing == []


def test_every_ledger_iva_aggregation_selector_declares_role_and_treatment() -> None:
    bindings = tuple(
        binding
        for path in _MODELOS_ROOT.rglob("*.toml")
        for binding in _binding_records(tomllib.loads(path.read_text(encoding="utf-8")))
    )

    assert len(bindings) == 259

    informational = []
    for binding in bindings:
        binding_id = binding["id"]
        assert isinstance(binding_id, str)
        selector = binding["selector"]
        assert isinstance(selector, dict)
        assert "observation_roles" in selector
        assert "cash_accounting_treatments" in selector
        if binding_id in _INFORMATIONAL_BINDING_IDS:
            informational.append(binding_id)
            assert selector["observation_roles"] == ["operation_informational"]
        else:
            assert selector["observation_roles"] == ["settlement"]
            assert selector["cash_accounting_treatments"] == _MONETARY_TREATMENTS

    assert len(informational) == 24
