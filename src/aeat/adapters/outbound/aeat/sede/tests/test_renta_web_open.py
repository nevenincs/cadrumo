"""Unit checks for the Renta WEB Open Sede driver."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ......core.config import Settings
from ......domain.calculations.registry import (
    CasillaId,
    RentaWebOpenLivePayload,
    equivalent_renta_web_open_value,
    validated_casilla_id,
)
from ..._playwright import PlaywrightTimeoutError
from .._errors import SedeFailureMode, SedeParseError
from .._renta_web_open import (
    RentaWebOpenSedeDriver,
    _playwright_stage,
    extract_renta_web_open_summary_value,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RENTA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("0670", surface="_RENTA_RESULTADO_CASILLA")
_RENTA_MINIMO_ESTATAL_CASILLA: CasillaId = validated_casilla_id("0519", surface="_RENTA_MINIMO_ESTATAL_CASILLA")


def test_renta_web_open_driver_plans_real_app_navigation_and_summary_scrapes() -> None:
    payload = (
        RentaWebOpenLivePayload(
            summary_labels_by_casilla_id={
                _RENTA_RESULTADO_CASILLA: "Resultado de la declaración",
                _RENTA_MINIMO_ESTATAL_CASILLA: "Mínimo personal y familiar",
            },
        )
        .model_dump_json()
        .encode("utf-8")
    )
    plan = RentaWebOpenSedeDriver().planned_operations(
        payload,
        expected={
            _RENTA_RESULTADO_CASILLA: Decimal("0.00"),
            _RENTA_MINIMO_ESTATAL_CASILLA: Decimal("5550.00"),
        },
    )

    _ext = Settings.external_constants()
    expected_app_url = _ext.aeat.oracles.renta_web_open_app_template.format(year=2025)
    assert plan[0].kind == "http"
    assert str(plan[0].url) == expected_app_url
    actions = tuple(operation.action for operation in plan if operation.kind == "browser_action")
    assert "start-open-simulator" in actions
    assert "fill-synthetic-profile" in actions
    assert "accept-identification" in actions
    assert "scrape-summary-field:Resultado de la declaración" in actions


def test_summary_extractor_reads_same_line_and_following_line_amounts() -> None:
    body_text = "Resultado de la declaración\t0,00\nMínimo personal y familiar. Parte estatal\n5.550,00\n"

    assert extract_renta_web_open_summary_value(body_text, "Resultado de la declaración") == "0,00"
    assert extract_renta_web_open_summary_value(body_text, "Mínimo personal y familiar. Parte estatal") == "5.550,00"


def test_spanish_numeric_output_matches_decimal_expected_value() -> None:
    assert equivalent_renta_web_open_value("5550.00", "5.550,00") is True
    assert equivalent_renta_web_open_value("0.00", "0,00") is True
    assert equivalent_renta_web_open_value("849.99", "850,00") is False


@pytest.mark.asyncio
async def test_renta_web_open_expected_element_timeout_reports_shape_drift() -> None:
    """Expected-control timeouts should surface as explicit Sede shape drift."""

    async def missing_element() -> None:
        raise PlaywrightTimeoutError("selector was not visible")

    with pytest.raises(SedeParseError, match="expected page element") as excinfo:
        await _playwright_stage(
            missing_element(),
            stage="start-open-simulator",
            description="Nueva declaración modal button",
            timeout_ms=250,
            timeout_is_shape_change=True,
        )

    assert excinfo.value.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == SedeFailureMode.EXTERNAL_SHAPE_CHANGED
    assert excinfo.value.context["stage"] == "start-open-simulator"
