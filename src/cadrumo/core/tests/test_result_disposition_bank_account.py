"""The bank-account axis is separate from the refund axis, and diverges at ``U``.

Two questions about a result disposition look like one and are not. "Does this
period carry compensación forward" is refund-ness. "Does AEAT need an account
number on the fichero" is this. They agree for the three refund codes and part
company at ``U``, domiciliación del ingreso, which is an INGRESO settled by
direct debit -- AEAT needs an account to CHARGE.

Conflating them would not be a tidy simplification, it would be a defect in a
specific direction: the refund set drives the compensación carry decision, so
adding ``U`` there would change what a domiciliación period carries forward as a
side effect of a question about bank details.

Grounded in the bundled Diseño de Registro for Modelo 303, which names the field
``Domiciliación/Devolución - IBAN`` -- one field serving both directions -- and
lists ``U`` among the payment forms.
"""

from __future__ import annotations

import pytest

from ..result_disposition import (
    ResultDisposition,
    result_disposition_is_refund,
    result_disposition_requires_bank_account,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "disposition",
    [
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    ],
)
def test_every_refund_disposition_needs_an_account(disposition: ResultDisposition) -> None:
    """AEAT cannot pay a refund without one, so refund-ness implies the account."""
    assert result_disposition_requires_bank_account(disposition)
    assert result_disposition_is_refund(disposition)


def test_domiciliacion_needs_an_account_while_not_being_a_refund() -> None:
    """The divergence, asserted on BOTH axes at once.

    Asserting only that ``U`` needs an account would pass equally well if
    someone "simplified" this by folding ``U`` into the refund set -- which is
    the change this test exists to catch, because it would silently move the
    compensación carry decision.
    """
    assert result_disposition_requires_bank_account(ResultDisposition.DOMICILIACION)
    assert not result_disposition_is_refund(ResultDisposition.DOMICILIACION), (
        "U was folded into the refund set, which changes what a domiciliacion period carries forward"
    )


@pytest.mark.parametrize(
    "disposition",
    [
        ResultDisposition.COMPENSACION,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
    ],
)
def test_a_plain_credit_payment_or_nil_return_needs_no_account(disposition: ResultDisposition) -> None:
    """The negative side, so the predicate is not trivially true."""
    assert not result_disposition_requires_bank_account(disposition)


def test_cuenta_corriente_ingreso_is_excluded_and_that_is_an_open_question() -> None:
    """``G`` is excluded, and this pins the exclusion as a decision rather than an oversight.

    Settlement through the cuenta corriente tributaria may legitimately need no
    debit account, and no bundled AEAT text has been read that settles it. The
    exclusion is therefore recorded rather than asserted as correct: if someone
    later establishes that ``G`` does need an account, this test is the place
    that says the current answer was never grounded.
    """
    assert not result_disposition_requires_bank_account(ResultDisposition.CUENTA_CORRIENTE_INGRESO)


def test_the_account_set_is_a_superset_of_the_refund_set() -> None:
    """Every refund code needs an account, over the whole enum rather than a list.

    Enumerated from ``ResultDisposition`` itself so a new member cannot slip in
    on one axis and be missed on the other -- the property, not a tally.
    """
    violations = [
        disposition.value
        for disposition in ResultDisposition
        if result_disposition_is_refund(disposition) and not result_disposition_requires_bank_account(disposition)
    ]
    assert not violations, f"refund disposition(s) that claim to need no account: {violations}"
