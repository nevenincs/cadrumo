"""Modelo 303 refunded-period carry-forward: a refund generates zero carry.

A Modelo 303 period whose negative result is REFUNDED (devolución, fichero
"Tipo de declaración" ``D``) returns the credit to the taxpayer rather than
carrying it forward. The end-of-period available compensación
(:func:`derive_303_compensation_available`) must therefore drop the GENERATED
component for a refunded period — ``available = posterior`` only — so the
refunded period carries nothing into the next period's casilla 110. The default
(``refunded=False``) is the standard compensación (``C``) behaviour and is
unchanged.

Legal basis: RD 1624/1992 (RIVA) art. 30 (Registro de devolución mensual);
Ley 37/1992 (LIVA) art. 116 (the monthly-refund right) — a refunded credit is
returned, not carried.

Non-tautological: the assertions are the structural carry invariants (a refund
zeroes the generated component; the carried disposition keeps it). The control
asserts the carried value equals the SAME function's non-refunded output, never
a hand-summed literal reproduced from the formula under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import ResultDisposition, result_disposition_is_refund
from ..carry_forward import derive_303_compensation_available

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_refunded_negative_period_carries_zero_when_no_posterior_pending() -> None:
    """A full refund of a negative-result period carries nothing forward.

    REDEME monthly-refund company: the whole credit is requested back, there is
    no pending posterior balance, so the refunded period's available carry-forward
    is zero — it does not double-claim the refunded credit into the next period.
    """
    available = derive_303_compensation_available(
        posterior=Decimal("0"),
        resultado=Decimal("-500.00"),
        refunded=True,
    )

    assert available == Decimal("0")


def test_carried_negative_period_generates_the_credit_control() -> None:
    """CONTROL (non-regressive): the same negative result, compensar-disposed, carries the credit.

    The refunded flag is the ONLY difference from the test above. With the default
    carried disposition the generated component is preserved, so the available
    carry is the magnitude of the negative result — the standard compensación
    behaviour every existing carry chain depends on.
    """
    resultado = Decimal("-500.00")

    carried = derive_303_compensation_available(posterior=Decimal("0"), resultado=resultado)

    assert carried == -resultado
    assert carried > Decimal("0")


def test_refunded_period_keeps_only_the_posterior_pending() -> None:
    """A refunded period still carries a genuine prior posterior balance, never the generated credit.

    The refund returns only the credit GENERATED this period; a distinct pending
    posterior balance (box 87, already carried from earlier periods) is untouched.
    The available carry equals exactly that posterior — the generated component is
    dropped.
    """
    posterior = Decimal("120.00")

    available = derive_303_compensation_available(
        posterior=posterior,
        resultado=Decimal("-500.00"),
        refunded=True,
    )

    assert available == posterior


def test_default_disposition_is_behaviour_identical_to_explicit_carried() -> None:
    """The default and the explicit ``refunded=False`` produce the same value.

    Guards the behaviour-preserving default: every existing caller that omits the
    new ``refunded`` argument must get the unchanged compensación carry.
    """
    posterior = Decimal("80.00")
    resultado = Decimal("-300.00")

    default_value = derive_303_compensation_available(posterior=posterior, resultado=resultado)
    explicit_carried = derive_303_compensation_available(
        posterior=posterior,
        resultado=resultado,
        refunded=False,
    )

    assert default_value == explicit_carried


def test_positive_result_generates_no_carry_regardless_of_disposition() -> None:
    """A positive result never generates carry, refunded or not — the max(0, -resultado) floor holds."""
    posterior = Decimal("0")
    resultado = Decimal("250.00")

    assert derive_303_compensation_available(posterior=posterior, resultado=resultado) == posterior
    assert derive_303_compensation_available(posterior=posterior, resultado=resultado, refunded=True) == posterior


def test_refund_dispositions_are_classified_as_refund() -> None:
    """The determined-fact predicate recognises every devolución settlement channel.

    ``D`` (ordinary refund), ``V`` (cuenta corriente devolución), and ``X``
    (devolución por transferencia al extranjero) all return the credit, so all
    three drive a refunded carry. The carried code ``C`` and the ingreso/negativa
    codes do not.
    """
    assert result_disposition_is_refund(ResultDisposition.DEVOLUCION)
    assert result_disposition_is_refund(ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION)
    assert result_disposition_is_refund(ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO)


def test_non_refund_dispositions_are_not_refund() -> None:
    """Compensación and the ingreso/negativa codes are NOT refunds (they carry or pay)."""
    assert not result_disposition_is_refund(ResultDisposition.COMPENSACION)
    assert not result_disposition_is_refund(ResultDisposition.INGRESO)
    assert not result_disposition_is_refund(ResultDisposition.NEGATIVA)
