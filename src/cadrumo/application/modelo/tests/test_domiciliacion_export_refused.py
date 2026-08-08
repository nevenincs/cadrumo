"""A domiciliación export is refused: there is no charge account to state.

``U``, domiciliación del ingreso, is an INGRESO the taxpayer pays by direct debit,
so the account on the fichero is the one AEAT **charges**. This application has
no such account. The profile records exactly one, documented as the account AEAT
pays a refund INTO, and no charge or cargo account concept exists on the export
path at all.

The refusal is UNCONDITIONAL, and the tests below assert that rather than
asserting "refuses when nothing is on file". That distinction is the whole
decision: reusing the refund account reads as harmless, and AEAT's own record
design even carries a single dual-purpose IBAN field at position 23 labelled
``Domiciliación/Devolución - IBAN``. But one shared FIELD says only that a filing
is a refund or a charge and never both. It says nothing about whether the account
a taxpayer nominated for RECEIVING money is the account they authorise to be
DEBITED, and emitting it would turn an application inference into a debit
instruction nothing downstream contradicts.

Nothing is lost by refusing: this application never files, a human files outside
it, so a blocked export costs a step while a wrong debit instruction reaching
AEAT does not announce itself. And the position being refused from is not a good
one -- before this, a ``U`` election exported with no account whatsoever.
"""

from __future__ import annotations

import pytest

from ....core import ResultDisposition
from ....core.errors import get_error_suggestion
from ....domain.deadlines import RefundAccount
from .._action_errors import ModeloRefundAccountMissingError
from .._export import _refuse_domiciliacion_without_charge_account

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SPANISH_IBAN = "ES9121000418450200051332"


@pytest.mark.parametrize(
    ("label", "account"),
    [
        ("no account at all", None),
        ("a payable SEPA account on file", RefundAccount(iban=_SPANISH_IBAN)),
        ("a SWIFT-only foreign account", RefundAccount(swift_bic="BSCHESMMXXX", bank_country_code="US")),
    ],
)
def test_a_domiciliacion_export_is_refused_whatever_the_refund_account_holds(
    label: str,
    account: RefundAccount | None,
) -> None:
    """Unconditional, including the case that looks fine.

    The middle case is the one that matters. A perfectly payable Spanish IBAN is
    on file and the export still refuses, because a refund account is not an
    authorisation to debit. A conditional refusal would pass a test named for
    this behaviour while silently emitting that IBAN as a charge instruction.
    """
    with pytest.raises(ModeloRefundAccountMissingError) as caught:
        _refuse_domiciliacion_without_charge_account(account)

    message = str(caught.value)
    assert "domiciliación" in message, f"the refusal does not name the election it refuses ({label})"
    assert "charge" in message.lower(), "the refusal does not say what is missing, only that something is"


def test_the_refusal_names_the_election_the_requirement_and_the_gap() -> None:
    """Not "export refused". Three specific facts an operator can act on."""
    with pytest.raises(ModeloRefundAccountMissingError) as caught:
        _refuse_domiciliacion_without_charge_account(RefundAccount(iban=_SPANISH_IBAN))

    message = str(caught.value)
    assert "elects domiciliación" in message, "the message does not state which election triggered it"
    assert "AEAT requires" in message, "the message does not state that AEAT requires the account"
    assert "no charge account is on file" in message, "the message does not state what is absent"
    assert "not an authorisation to debit" in message, (
        "the message does not explain why the refund account on file does not satisfy the requirement"
    )


def test_the_suggestion_is_honestly_unsupported_rather_than_unfollowable() -> None:
    """An instruction the operator cannot carry out is worse than saying so.

    There is no verb that records a charge account, so a suggestion naming one
    would be a dead instruction -- a defect class this codebase's tests have
    repeatedly caught. The suggestion says the capability is missing and offers
    the two routes that do exist.
    """
    with pytest.raises(ModeloRefundAccountMissingError) as caught:
        _refuse_domiciliacion_without_charge_account(None)

    suggestion = get_error_suggestion(caught.value)
    assert suggestion, "an operator-reachable refusal resolved to no next step at all"
    assert "not supported yet" in suggestion, "the suggestion implies a capability that does not exist"
    assert "plain ingreso" in suggestion, "the suggestion offers no route the operator can actually take"


def test_domiciliacion_is_the_only_disposition_this_refusal_governs() -> None:
    """Anchors the blast radius.

    A refusal keyed too broadly would block refund exports, which work and must
    keep working. This asserts the enum member the caller branches on rather than
    re-testing the caller, so the pairing cannot drift silently.
    """
    assert ResultDisposition.DOMICILIACION.value == "U"
    assert ResultDisposition.DOMICILIACION not in {
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    }
