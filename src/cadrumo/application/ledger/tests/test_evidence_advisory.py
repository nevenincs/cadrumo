"""Tests for the printed-vs-derived IVA advisory cross-check."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..evidence_advisory import printed_iva_advisory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_no_advisory_without_evidence_or_derived() -> None:
    assert printed_iva_advisory(None, Decimal("21.00")) is None
    assert printed_iva_advisory("IVA 21,00", None) is None


def test_no_advisory_when_printed_matches_derived() -> None:
    assert printed_iva_advisory("Base 100,00 IVA 21,00 Total 121,00", Decimal("21.00")) is None


def test_advisory_fires_on_mismatch() -> None:
    advisory = printed_iva_advisory("Base 100,00 IVA 10,00 Total 110,00", Decimal("21.00"))
    assert advisory is not None
    assert "10.00" in advisory
    assert "21.00" in advisory
    assert "advisory only" in advisory


def test_parses_spanish_thousands_format() -> None:
    # 1.234,56 -> 1234.56; mismatch vs derived 21.00 -> advisory.
    advisory = printed_iva_advisory("IVA 1.234,56", Decimal("21.00"))
    assert advisory is not None
    assert "1234.56" in advisory


def test_parses_dot_decimal_format() -> None:
    advisory = printed_iva_advisory("IVA 10.50", Decimal("21.00"))

    assert advisory is not None
    assert "10.50" in advisory


def test_unparseable_or_absent_printed_iva_yields_no_advisory() -> None:
    assert printed_iva_advisory("no tax figures here", Decimal("21.00")) is None
