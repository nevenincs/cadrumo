"""Smoke tests for the synthetic PDF generator family.

Each generator exposes a pure `generate(params) -> (bytes, ground_truth)`
function. The smoke tests exercise that API end-to-end with minimal
parameter sets, verifying valid PDF bytes + a paired ground-truth
manifest, without touching committed fixture artifacts.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ......domain.calculations.registry import CasillaId, validated_casilla_id
from ._generic_quarterly_generator import (
    QuarterlyGenParams,
)
from ._generic_quarterly_generator import (
    generate as generate_quarterly,
)
from .modelo_100_generator import (
    Modelo100GenParams,
)
from .modelo_100_generator import (
    generate as generate_modelo_100,
)
from .modelo_130_generator import (
    Modelo130GenParams,
)
from .modelo_130_generator import (
    generate as generate_modelo_130,
)
from .modelo_303_generator import (
    Modelo303GenParams,
)
from .modelo_303_generator import (
    generate as generate_modelo_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]
_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_CASILLA_01")
_CASILLA_0505: CasillaId = validated_casilla_id("0505", surface="_CASILLA_0505")


def _assert_pdf(pdf_bytes: bytes) -> None:
    assert pdf_bytes.startswith(b"%PDF"), "rendered bytes are not a PDF"
    assert len(pdf_bytes) > 500, "rendered PDF suspiciously small"


def test_generic_quarterly_generator_round_trip() -> None:
    """generate() emits a real PDF + a populated ground-truth manifest."""

    params = QuarterlyGenParams(
        modelo="131",
        año=2024,
        template_revision="2024",
        tax_id="00000000T",
        ejercicio="2024",
        period_printed="1T",
        labels={_CASILLA_01: "Casilla 01"},
        casilla_values={_CASILLA_01: Decimal("100.00")},
    )
    pdf_bytes, ground_truth = generate_quarterly(params)
    _assert_pdf(pdf_bytes)
    assert ground_truth.params == params
    assert ground_truth.expected_values_by_casilla_id


def test_modelo_100_generator_round_trip() -> None:
    """M100 renta synthetic generator emits a real PDF."""

    params = Modelo100GenParams(
        año=2024,
        ejercicio="2024",
        tax_id="00000000T",
        casilla_values={_CASILLA_0505: Decimal("30000.00")},
        artefact_kind="BORRADOR",
    )
    pdf_bytes, ground_truth = generate_modelo_100(params)
    _assert_pdf(pdf_bytes)
    assert ground_truth.params == params


def test_modelo_130_generator_round_trip() -> None:
    """M130 pago fraccionado synthetic generator emits a real PDF."""

    params = Modelo130GenParams(
        año=2024,
        template_revision="2024",
        tax_id="00000000T",
        ejercicio="2024",
        period_printed="1T",
        casilla_values={_CASILLA_01: Decimal("5000.00")},
    )
    pdf_bytes, ground_truth = generate_modelo_130(params)
    _assert_pdf(pdf_bytes)
    assert ground_truth.params == params


def test_modelo_303_generator_round_trip() -> None:
    """M303 IVA synthetic generator emits a real PDF."""

    params = Modelo303GenParams(
        año=2024,
        template_revision="2024",
        tax_id="00000000T",
        ejercicio="2024",
        period_printed="1T",
        casilla_values={_CASILLA_01: Decimal("10000.00")},
    )
    pdf_bytes, ground_truth = generate_modelo_303(params)
    _assert_pdf(pdf_bytes)
    assert ground_truth.params == params
