"""Unit checks for the Renta WEB Open Sede driver."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....domain.calculations.registry import (
    RENTA_WEB_OPEN_APP_URL,
    RentaWebOpenLivePayload,
    equivalent_renta_web_open_value,
)
from ._renta_web_open import (
    RentaWebOpenSedeDriver,
    extract_renta_web_open_summary_value,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_renta_web_open_driver_plans_real_app_navigation_and_summary_scrapes() -> None:
    payload = RentaWebOpenLivePayload().model_dump_json().encode("utf-8")
    plan = RentaWebOpenSedeDriver().planned_operations(
        payload,
        expected={"Resultado de la declaración": Decimal("0.00"), "Mínimo personal y familiar": Decimal("5550.00")},
    )

    assert plan[0].kind == "http"
    assert plan[0].url == RENTA_WEB_OPEN_APP_URL
    actions = tuple(operation.action for operation in plan if operation.kind == "browser_action")
    assert "start-open-simulator" in actions
    assert "fill-synthetic-profile" in actions
    assert "accept-identification" in actions
    assert "scrape-summary-field:Resultado de la declaración" in actions


def test_summary_extractor_reads_same_line_and_following_line_amounts() -> None:
    body_text = (
        "Resultado de la declaración\t0,00\n"
        "Mínimo personal y familiar. Parte estatal\n"
        "5.550,00\n"
    )

    assert extract_renta_web_open_summary_value(body_text, "Resultado de la declaración") == "0,00"
    assert extract_renta_web_open_summary_value(body_text, "Mínimo personal y familiar. Parte estatal") == "5.550,00"


def test_spanish_numeric_output_matches_decimal_expected_value() -> None:
    assert equivalent_renta_web_open_value("5550.00", "5.550,00") is True
    assert equivalent_renta_web_open_value("0.00", "0,00") is True
    assert equivalent_renta_web_open_value("849.99", "850,00") is False
