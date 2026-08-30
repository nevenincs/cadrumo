"""What the wallet decision SAYS when no authority is available.

Two situations reach the same no-authority outcome and they are not the same
thing: nothing was stored for the source period, or a prior record was stored
and could not be read as prior-compensation evidence. Only the caller can tell
them apart, so it asserts the difference and the decision states it.

WHAT THIS PROVES AND WHAT IT DOES NOT. It proves the reconciler emits a true
and distinguishing sentence for both populations. It does NOT prove the sentence
reaches an operator: the live ``iva-wallet`` surface projects a different type --
``IvaWalletAuthorityDecisionRow``, not the reconciliation decision -- so carriage
cannot be asserted from here without replicating a fifteen-field construction of
an object this module does not produce. That carriage is a separate check and it
is rowed, not silently assumed.

Two earlier versions of this file DID replicate that construction. Both failed,
and the failures looked like typos -- one wrong field, then one missing field --
while the mistake was structural: the payload was being built from the wrong
CLASS. A hand-replication can be field-perfect, type-wrong, and reveal its error
one field per execution, which reads as a series of small mistakes rather than
the single wrong assumption underneath.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ....domain.iva_compensation.reconciliation import IvaCompensationDecisionReason, reconcile_iva_compensation_wallet
from .._app_live import _iva_wallet_decision_reason_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TAXPAYER_REF = "12345678Z"
_DECIDED_AT = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)


def _reason(*, found_but_unusable: bool) -> IvaCompensationDecisionReason:
    """Return the locale-neutral identity for one no-authority situation."""
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        wallet=None,
        local_recurrence_amount=None,
        decided_at=_DECIDED_AT,
        local_evidence_found_but_unusable=found_but_unusable,
    )
    assert decision.blocked is True, "both situations must still block; only the sentence differs"
    return decision.reason_identity


def test_an_unreadable_prior_record_is_not_described_as_nothing_existing() -> None:
    """The defect this closes: the sentence said nothing exists while the record did.

    A taxpayer sent looking for evidence they already hold is worse served than
    one told plainly that the record could not be read, and the first is what
    the reconciler used to say.
    """
    reason = _reason(found_but_unusable=True)

    assert reason is IvaCompensationDecisionReason.LOCAL_EVIDENCE_UNREADABLE


def test_a_genuinely_absent_prior_record_still_reads_as_nothing_available() -> None:
    """The population the change must leave untouched.

    Without this the first test passes for the wrong reason: a sentence saying
    "could not be read" unconditionally would satisfy it while making the
    genuinely-absent case false in the other direction.
    """
    reason = _reason(found_but_unusable=False)

    assert reason is IvaCompensationDecisionReason.NO_USABLE_AUTHORITY


def test_the_two_situations_do_not_carry_the_same_sentence() -> None:
    """The point of the row is that the two can be told apart at all."""
    assert _reason(found_but_unusable=True) != _reason(found_but_unusable=False)


@pytest.mark.parametrize("reason", tuple(IvaCompensationDecisionReason))
def test_every_wallet_decision_reason_has_a_live_localized_text(reason: IvaCompensationDecisionReason) -> None:
    """Every closed reason reaches the live surface's locale boundary."""
    assert _iva_wallet_decision_reason_text(reason)
