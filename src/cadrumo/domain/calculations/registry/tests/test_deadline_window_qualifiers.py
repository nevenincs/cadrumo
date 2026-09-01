"""Typed deadline-window qualifier schema tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .....core.irnr import M210_TIPO_RENTA_CODE_PROJECTION, TipoRentaIrnr
from .....core.result_disposition import ResultDisposition
from ..errors import RegistryValidationError
from ..schema_deadlines import DeadlineWindowDefinition

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


@pytest.mark.parametrize("disposition", tuple(ResultDisposition))
def test_deadline_window_accepts_canonical_result_disposition_members(disposition: ResultDisposition) -> None:
    qualified = _window(resultado_scope=disposition)

    assert qualified.resultado_scope is disposition


def test_deadline_window_preserves_official_codes_that_share_one_rate_concept() -> None:
    assert M210_TIPO_RENTA_CODE_PROJECTION["01"] is TipoRentaIrnr.GENERAL
    assert M210_TIPO_RENTA_CODE_PROJECTION["03"] is TipoRentaIrnr.GENERAL

    qualified = _window(tipo_renta_scope=("01", "03"))

    assert qualified.tipo_renta_scope == ("01", "03")


@pytest.mark.parametrize("conceptual_key", [TipoRentaIrnr.GENERAL, TipoRentaIrnr.GENERAL.value])
def test_deadline_window_rejects_lossy_conceptual_tipo_authoring(conceptual_key: object) -> None:
    with pytest.raises((RegistryValidationError, ValidationError), match="unknown official Modelo 210 codes"):
        _window(tipo_renta_scope=(conceptual_key,))


@pytest.mark.parametrize("tipo_renta_scope", [(), ("01", "01"), ("1",), ("99",)])
def test_deadline_window_rejects_invalid_official_tipo_renta_scope(tipo_renta_scope: tuple[str, ...]) -> None:
    with pytest.raises((RegistryValidationError, ValidationError), match="tipo_renta_scope"):
        _window(tipo_renta_scope=tipo_renta_scope)
