"""Typed deadline-window qualifier schema tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.core import ResultDisposition

from .. import DeadlineWindowDefinition, RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _window(**updates: object) -> DeadlineWindowDefinition:
    payload: dict[str, object] = {
        "id": "dw-qualified",
        "filing_year": 2025,
        "period": "2025 0A",
        "period_kind": "annual",
        "opens_on": date(2026, 1, 1),
        "closes_on": date(2026, 1, 20),
        "legal_refs": ("legal.test",),
        "source_refs": ("source-test",),
    }
    payload.update(updates)
    return DeadlineWindowDefinition.model_validate(payload)


def test_deadline_window_qualifiers_are_optional_and_typed() -> None:
    assert _window().resultado_scope is None
    assert _window().tipo_renta_scope is None

    qualified = _window(resultado_scope="I", tipo_renta_scope=("01", "35"))

    assert qualified.resultado_scope is ResultDisposition.INGRESO
    assert qualified.tipo_renta_scope == ("01", "35")


@pytest.mark.parametrize("tipo_renta_scope", [(), ("01", "01"), ("1",), ("99",)])
def test_deadline_window_rejects_invalid_official_tipo_renta_scope(tipo_renta_scope: tuple[str, ...]) -> None:
    with pytest.raises((RegistryValidationError, ValidationError), match="tipo_renta_scope"):
        _window(tipo_renta_scope=tipo_renta_scope)
