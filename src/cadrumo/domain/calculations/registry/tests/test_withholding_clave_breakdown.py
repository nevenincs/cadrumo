"""Per-clave retención breakdown projection for the Modelo 190 output surface.

``aggregate_withholding_by_clave`` groups the per-perceptor-clave withholding
detail (the AEAT Diseño de Registros type-2 records) by clave de percepción and
applies the same ``percepcion_count`` / ``percibido_sum`` / ``retencion_sum``
field arithmetic the scalar withholding facts use, so an operator can reconcile
the annual Modelo 190 figures against the individual Modelo 111 quarterly
filings clave by clave. These tests pin the grouping arithmetic against
explicit, hand-supplied observation magnitudes (the test author owns the input
amounts; nothing is derived from a registry formula under test).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import RetencionClave
from ..withholding_bindings import (
    WithholdingClaveBreakdown,
    WithholdingObservation,
    aggregate_withholding_by_clave,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _obs(
    *,
    source_id: str,
    nif: str,
    clave: str,
    subclave: str = "",
    percibido_dinerario: str = "0",
    percibido_especie: str = "0",
    retencion_practicada: str = "0",
    ingreso_a_cuenta: str = "0",
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(2025, 6, 1),
        clave=RetencionClave(clave),
        subclave=subclave,
        percibido_dinerario=Decimal(percibido_dinerario),
        percibido_especie=Decimal(percibido_especie),
        retencion_practicada=Decimal(retencion_practicada),
        ingreso_a_cuenta=Decimal(ingreso_a_cuenta),
    )


def test_breakdown_groups_by_clave_and_sums_magnitudes() -> None:
    """Two claves roll up to distinct per-clave percepción counts and magnitudes."""
    observations = (
        _obs(source_id="a1", nif="11111111H", clave="A", percibido_dinerario="1000.00", retencion_practicada="190.00"),
        _obs(source_id="a2", nif="22222222J", clave="A", percibido_dinerario="500.00", retencion_practicada="95.00"),
        _obs(
            source_id="g1",
            nif="11111111H",
            clave="G",
            percibido_dinerario="2000.00",
            percibido_especie="100.00",
            retencion_practicada="400.00",
            ingreso_a_cuenta="20.00",
        ),
    )

    breakdown = aggregate_withholding_by_clave(observations)

    assert [row.clave for row in breakdown] == [RetencionClave.A, RetencionClave.G]
    rows = {row.clave: row for row in breakdown}
    # Clave A: two distinct perceptores, percibido = 1000 + 500, retención = 190 + 95.
    assert rows[RetencionClave.A].percepcion_count == 2
    assert rows[RetencionClave.A].percibido_total == Decimal("1500.00")
    assert rows[RetencionClave.A].retencion_total == Decimal("285.00")
    # Clave G: one percepción, percibido = dinerario + especie, retención = practicada + ingreso a cuenta.
    assert rows[RetencionClave.G].percepcion_count == 1
    assert rows[RetencionClave.G].percibido_total == Decimal("2100.00")
    assert rows[RetencionClave.G].retencion_total == Decimal("420.00")
    assert all(isinstance(row, WithholdingClaveBreakdown) for row in breakdown)


def test_distinct_percepcion_count_is_per_perceptor_subclave_within_clave() -> None:
    """A perceptor paid twice under one (clave, subclave) is one percepción; a new subclave is another."""
    observations = (
        _obs(source_id="r1", nif="11111111H", clave="A", subclave="01", retencion_practicada="50.00"),
        _obs(source_id="r2", nif="11111111H", clave="A", subclave="01", retencion_practicada="70.00"),
        _obs(source_id="r3", nif="11111111H", clave="A", subclave="02", retencion_practicada="30.00"),
    )

    breakdown = aggregate_withholding_by_clave(observations)

    assert len(breakdown) == 1
    row = breakdown[0]
    assert row.clave == RetencionClave.A
    # (H, 01) collapses to one percepción; (H, 02) is a second.
    assert row.percepcion_count == 2
    assert row.retencion_total == Decimal("150.00")


def test_breakdown_is_order_independent_and_sorted_by_clave() -> None:
    """Identical observations in any order produce the same clave-sorted tuple."""
    a = _obs(source_id="a", nif="11111111H", clave="A", retencion_practicada="10.00")
    g = _obs(source_id="g", nif="22222222J", clave="G", retencion_practicada="20.00")
    e = _obs(source_id="e", nif="33333333P", clave="E", retencion_practicada="30.00")

    forward = aggregate_withholding_by_clave((a, e, g))
    shuffled = aggregate_withholding_by_clave((g, a, e))

    assert forward == shuffled
    assert [row.clave for row in forward] == [RetencionClave.A, RetencionClave.E, RetencionClave.G]


def test_empty_observations_yield_empty_breakdown() -> None:
    """No observations means no per-clave rows (a nil-percepciones M190 filer)."""
    assert aggregate_withholding_by_clave(()) == ()
