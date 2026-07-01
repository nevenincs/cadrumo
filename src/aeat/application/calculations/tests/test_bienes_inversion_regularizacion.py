"""Deferred-source advisory projection for capital-goods IVA regularización."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import BindingSourceKind
from ....domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionKind,
)
from .._bienes_inversion_regularizacion import (
    CASILLA_REGULARIZACION_BIENES_INVERSION,
    build_bienes_inversion_regularizacion_advisory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _register() -> BienesInversionIvaRegister:
    return BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier="bi-2022-maquina",
                description="Máquina afecta",
                acquisition_year=2022,
                cuota_soportada=Decimal("5000.00"),
                prorrata_inicial_pct=Decimal("80"),
                kind=BienInversionKind.MUEBLE,
            ),
        )
    )


def test_advisory_surfaces_proposed_casilla_43_for_in_window_goods() -> None:
    """An in-window good produces a non-blocking advisory naming the proposed value.

    cuota 5.000, 80→60 (20-point drop), efectuada 4.000 − procedente 3.000 = 1.000,
    ÷5 = 200,00 → proposed casilla 43.
    """
    projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        _register(),
        regularizacion_year=2024,
        prorrata_definitiva_by_identifier={"bi-2022-maquina": Decimal("60")},
    )
    assert projection.proposed_casilla_43 == Decimal("200.00")
    assert diagnostic is not None
    assert diagnostic.source_kind == BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value
    assert diagnostic.binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert CASILLA_REGULARIZACION_BIENES_INVERSION in diagnostic.message
    assert "200.00" in diagnostic.message


def test_advisory_fires_even_when_percentage_pending() -> None:
    """No-silent-under-declaration: in-window goods alert even without the percentage.

    The current-year definitive percentage is the deferred input; when it is absent
    the advisory still fires (the operator is told casilla 43 may be due), and the
    good is reported as pending rather than silently dropped.
    """
    projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        _register(),
        regularizacion_year=2024,
        prorrata_definitiva_by_identifier={},
    )
    assert projection.pending_percentage_count == 1
    assert projection.proposed_casilla_43 == Decimal("0.00")
    assert diagnostic is not None
    assert "pendiente" in diagnostic.message


def test_no_advisory_when_no_in_window_goods() -> None:
    """A register with no in-window goods produces no diagnostic (no noise)."""
    projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        _register(),
        regularizacion_year=2030,  # outside the 2023-2026 mueble window
        prorrata_definitiva_by_identifier={},
    )
    assert projection.rows == ()
    assert diagnostic is None
