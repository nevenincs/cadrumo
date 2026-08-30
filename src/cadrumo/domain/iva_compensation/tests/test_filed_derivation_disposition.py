"""The filed-casilla carry derivation must be told the refund disposition.

``derive_m303_compensation_available_from_casillas`` produces
``iva.compensacion-disponible-fin-periodo``, which the
``modelo-303-compensacion-pendiente-anteriores`` binding selects from period
``N-1`` to fill casilla 110 of period ``N``. So its answer is a figure-bearing
cross-period carry, and a wrong one surfaces a quarter later as an over-stated
credit rather than as a failure.

Two paths write that casilla. The LOCAL filed path knows the fichero "Tipo de
declaración" and re-stamps the casilla to its posterior-only value for a
refunded period. The AEAT-FETCHED paths read casillas only, and Modelo 303 has
no devolución casilla -- the election lives in the fichero header -- so they
cannot observe it. While ``refunded`` carried a default, those callers silently
assumed compensación, and a taxpayer who had requested a refund carried the
refunded credit forward into the next period's casilla 110.

The argument is now required, so the assumption has to be written at each call
site instead of inherited from a signature. These tests pin the policy on both
derivation bases and pin the requirement itself.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from ....core import CasillaId
from ..carry_forward import derive_303_compensation_available
from ..filed_derivation import (
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
    derive_m303_compensation_available_from_casillas,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_POSTERIOR = Decimal("400.00")
_GENERATED = Decimal("250.00")
_NEGATIVE_RESULTADO = Decimal("-250.00")


def _values(**overrides: Decimal) -> dict[CasillaId, Decimal]:
    base: dict[CasillaId, Decimal] = {M303_COMPENSATION_POSTERIOR_CASILLA: _POSTERIOR}
    base.update(overrides)  # type: ignore[arg-type]
    return base


def test_the_fixture_period_actually_generates_credit_on_both_bases() -> None:
    """Anchor test: without generated credit the refunded case is vacuous.

    If the fixture ever stopped generating a credit, refunded and carried would
    agree trivially and every assertion below would pass while testing nothing.
    """
    assert Decimal("0") < _GENERATED
    assert Decimal("0") > _NEGATIVE_RESULTADO
    assert (
        derive_303_compensation_available(
            posterior=_POSTERIOR,
            resultado=_NEGATIVE_RESULTADO,
        )
        > _POSTERIOR
    )


def test_a_refunded_period_carries_only_the_posterior_on_the_resultado_basis() -> None:
    """The refunded credit was returned to the taxpayer, so it is not carried."""
    derivation = derive_m303_compensation_available_from_casillas(
        _values(**{M303_COMPENSATION_RESULTADO_CASILLA: _NEGATIVE_RESULTADO}),
        refunded=True,
    )

    assert derivation is not None
    assert derivation.available == _POSTERIOR, "a refunded credit was carried into the next period"
    assert derivation.generated == Decimal("0"), "a refunded period reported a generated credit it does not carry"


def test_a_refunded_period_carries_only_the_posterior_on_the_generated_basis() -> None:
    """The directly filed generated casilla is not an operand of a refunded carry.

    The generated basis was the path that could not express a refund at all: it
    added the filed generated credit unconditionally, so a refunded period whose
    filing carried that casilla over-stated the carry by exactly the refunded
    amount.
    """
    derivation = derive_m303_compensation_available_from_casillas(
        _values(**{M303_COMPENSATION_GENERADA_CASILLA: _GENERATED}),
        refunded=True,
    )

    assert derivation is not None
    assert derivation.available == _POSTERIOR
    assert derivation.generated == Decimal("0"), "a refunded period reported a generated credit it does not carry"
    assert derivation.operand_refs == (), "a refunded carry must not project the generated operand"


@pytest.mark.parametrize(
    "extra",
    [
        {M303_COMPENSATION_RESULTADO_CASILLA: _NEGATIVE_RESULTADO},
        {M303_COMPENSATION_GENERADA_CASILLA: _GENERATED},
    ],
)
def test_a_carried_period_still_includes_the_generated_credit(extra: dict[CasillaId, Decimal]) -> None:
    """Positive control: the refund policy is not a blanket drop of the credit.

    Without this, a derivation that always returned the posterior would satisfy
    both refunded cases above while silently under-stating every ordinary
    compensación carry.
    """
    derivation = derive_m303_compensation_available_from_casillas(_values(**extra), refunded=False)

    assert derivation is not None
    assert derivation.available > _POSTERIOR
    assert derivation.generated == _GENERATED


@pytest.mark.parametrize("refunded", [True, False])
def test_the_available_carry_decomposes_into_the_posterior_and_the_generated_credit(
    refunded: bool,
) -> None:
    """The two amounts are one decomposition, so they cannot disagree about a refund.

    ``generated_amount`` and ``available_end_amount`` are written into one
    period state by one constructor. Both depend on the disposition, so a
    consumer reading one from this derivation and computing the other itself
    produces a record that is internally inconsistent rather than uniformly
    wrong -- and nothing downstream can then tell which field to believe.

    Scoped to the GENERADA basis deliberately. On the resultado basis the
    derivation reads ``generated`` back out of the policy's answer as
    ``available - posterior``, so the identity is an algebraic rearrangement of
    that definition and holds whatever either figure is -- it cannot fail, and
    asserting it there reads as coverage while proving nothing. On this basis
    ``generated`` is the filed input and ``available`` is computed from it, so
    the two are independent and the identity discriminates. The resultado basis
    is held to the properties that do discriminate for it, below.
    """
    derivation = derive_m303_compensation_available_from_casillas(
        _values(**{M303_COMPENSATION_GENERADA_CASILLA: _GENERATED}),
        refunded=refunded,
    )

    assert derivation is not None
    assert derivation.available == _POSTERIOR + derivation.generated


@pytest.mark.parametrize(
    ("refunded", "carries_credit"),
    [(True, False), (False, True)],
)
def test_the_resultado_basis_generated_credit_answers_to_the_disposition(
    refunded: bool,
    carries_credit: bool,
) -> None:
    """On the resultado basis the disposition alone decides whether credit is carried.

    This replaces an identity assertion that could not fail here. What
    discriminates on this basis is the SIGN behaviour: a refunded period must
    report exactly zero generated credit, and a carried period with a negative
    resultado must report a strictly positive one. A derivation that zeroed both
    dispositions, or neither, fails one of these.
    """
    derivation = derive_m303_compensation_available_from_casillas(
        _values(**{M303_COMPENSATION_RESULTADO_CASILLA: _NEGATIVE_RESULTADO}),
        refunded=refunded,
    )

    assert derivation is not None
    assert derivation.generated >= Decimal("0"), "a generated credit is never negative"
    if carries_credit:
        assert derivation.generated > Decimal("0")
        assert derivation.available > _POSTERIOR
    else:
        assert derivation.generated == Decimal("0")
        assert derivation.available == _POSTERIOR


def test_the_refund_disposition_is_required_rather_than_defaulted() -> None:
    """A default silently picks compensación for taxpayers who requested a refund.

    The disposition is not recoverable from ``casilla_values`` -- Modelo 303
    declares no devolución casilla -- so a caller that cannot observe it must be
    forced to say so at the call site rather than inherit an answer.
    """
    parameter = inspect.signature(derive_m303_compensation_available_from_casillas).parameters["refunded"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        derive_m303_compensation_available_from_casillas(  # type: ignore[call-arg]  # ty: ignore[missing-argument]  # reason: the omission IS the assertion — the disposition must be impossible to forget at a call site
            _values(**{M303_COMPENSATION_RESULTADO_CASILLA: _NEGATIVE_RESULTADO}),
        )
