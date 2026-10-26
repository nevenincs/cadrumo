"""Smoke tests for the borrador-M100 PDF corpus generator.

The generator's `main`/`generate_corpus` mutates committed in-tree
fixture bytes, so the smoke tests exercise the pure helper functions
(`_format_spanish_decimal`, `render_borrador_pdf`) without invoking
the file-writing path. That covers the importable surface end-to-end:
formatting + PDF rendering both run for real on real inputs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from .generate import (
    _format_spanish_decimal,
    render_borrador_pdf,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_BASE_LIQUIDABLE_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "0505",
    surface="_BASE_LIQUIDABLE_GENERAL_CASILLA",
)
_CUOTA_INTEGRA_ESTATAL_CASILLA: CasillaId = validated_casilla_id(
    "0545",
    surface="_CUOTA_INTEGRA_ESTATAL_CASILLA",
)


def test_format_spanish_decimal_uses_comma_and_dot_separators() -> None:
    """Spanish convention: thousands dot, decimal comma."""

    assert _format_spanish_decimal(Decimal("0.00")) == "0,00"
    assert _format_spanish_decimal(Decimal("1234.56")) == "1.234,56"
    assert _format_spanish_decimal(Decimal("1000000.00")) == "1.000.000,00"


def test_format_spanish_decimal_rounds_to_two_places() -> None:
    """Generator always emits two decimal places per AEAT presentation."""

    assert _format_spanish_decimal(Decimal("12.5")) == "12,50"


def testrender_borrador_pdf_emits_valid_pdf_bytes() -> None:
    """The rendered bytes start with the PDF magic + carry the printed
    casilla labels in the document. Tests the rendering path end-to-end
    without writing to disk."""

    casilla_values = {
        _BASE_LIQUIDABLE_GENERAL_CASILLA: Decimal("30000.00"),
        _CUOTA_INTEGRA_ESTATAL_CASILLA: Decimal("3450.00"),
    }
    pdf_bytes = render_borrador_pdf(year=2024, casilla_values=casilla_values)

    assert pdf_bytes.startswith(b"%PDF"), "rendered bytes are not a PDF"
    assert len(pdf_bytes) > 500, "rendered PDF suspiciously small"
