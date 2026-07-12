"""Administrador retención statutory-rate advisory: fires only on a non-101.2 rate.

Modelo 111 aggregates operator-supplied per-perceptor retención rows, so the
fixed LIRPF art. 101.2 rate for administradores y consejeros (35 % general, or
19 % when the paying entity's net turnover is below 100.000 euros; Ley 35/2006
BOE-A-2006-20764, RIRPF art. 80.1.3.º RD 439/2007) could otherwise fold into the
trabajo block unverified. These gates assert the advisory:

* fires exactly one ``administrador_retencion_rate_mismatch`` diagnostic on an
  administrador row whose withholding matches neither statutory figure;
* does NOT fire on an administrador row at the general 35 % rate, nor at the
  reduced 19 % rate (the engine cannot always know the entity's INCN, so either
  statutory rate is conforming);
* does NOT fire on a non-positive-base administrador row, nor on any other
  scheme (empleados follow the progressive art. 101.1 procedure; actividades,
  premios, and capital are not art. 101 trabajo).

The expected rates (35 % / 19 %) are read from the statutory art. 101.2 text, not
derived from any registry formula under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import BindingSourceKind
from .._retencion_rate_advisory import (
    ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND,
    administrador_retencion_rate_advisory_observations,
)
from .._retenciones import RetencionObservation, RetencionScheme

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _administrador(base: str, withheld: str, *, nif: str = "87654321X") -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"administrador-{nif}-{withheld}",
        perceptor_nif=nif,
        perceptor_name="Administrador Ejemplo",
        scheme=RetencionScheme.WORK_INCOME_DIRECTOR,
        taxable_base=Decimal(base),
        retencion_amount=Decimal(withheld),
        accrued_on="2026-03-15",
    )


def _empleado(base: str, withheld: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="empleado-001",
        perceptor_nif="12345678Z",
        perceptor_name="Empleado Ejemplo",
        scheme=RetencionScheme.WORK_INCOME,
        taxable_base=Decimal(base),
        retencion_amount=Decimal(withheld),
        accrued_on="2026-03-15",
    )


def test_advisory_fires_on_administrador_rate_matching_neither_statutory_figure() -> None:
    """A €2.000 base withheld at 25 % (€500) matches neither 35 % nor 19 % → advisory."""
    diagnostics = administrador_retencion_rate_advisory_observations([_administrador("2000.00", "500.00")])
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == "administrador_retencion_rate_mismatch"
    assert diagnostic.source_kind == ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND
    assert "87654321X" in diagnostic.message


def test_advisory_silent_on_administrador_general_35_percent_rate() -> None:
    """€2.000 * 0,35 = €700,00 is the art. 101.2 general rate → no advisory."""
    assert administrador_retencion_rate_advisory_observations([_administrador("2000.00", "700.00")]) == ()


def test_advisory_silent_on_administrador_reduced_19_percent_rate() -> None:
    """€2.000 * 0,19 = €380,00 is the art. 101.2 reduced (INCN < 100.000 €) rate → no advisory."""
    assert administrador_retencion_rate_advisory_observations([_administrador("2000.00", "380.00")]) == ()


def test_advisory_tolerates_one_cent_rounding_on_the_fixed_rate() -> None:
    """A row rounded to cents (1.234,56 * 0,35 = 432,096 → 432,10) stays within tolerance."""
    assert administrador_retencion_rate_advisory_observations([_administrador("1234.56", "432.10")]) == ()


def test_advisory_silent_on_administrador_zero_base() -> None:
    """A non-positive base carries no verifiable rate → advisory out of scope."""
    assert administrador_retencion_rate_advisory_observations([_administrador("0", "0")]) == ()


def test_advisory_silent_on_empleado_progressive_scheme() -> None:
    """Ordinary empleados follow the personalised art. 101.1 escala; no fixed rate applies."""
    assert administrador_retencion_rate_advisory_observations([_empleado("2000.00", "300.00")]) == ()


def test_advisory_fires_once_per_divergent_administrador_row() -> None:
    """Two divergent administrador rows each raise one advisory; a conforming row stays silent."""
    diagnostics = administrador_retencion_rate_advisory_observations(
        [
            _administrador("1000.00", "150.00", nif="11111111H"),
            _administrador("1000.00", "350.00", nif="22222222J"),
            _administrador("1000.00", "220.00", nif="33333333P"),
        ],
    )
    assert len(diagnostics) == 2
    flagged = {d.message.split("perceptor ")[1].split(" ")[0].strip("'") for d in diagnostics}
    assert flagged == {"11111111H", "33333333P"}
