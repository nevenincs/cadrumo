"""What the iva-wallet surface tells an operator when no authority is available.

The live ``iva-wallet`` surface renders the wallet decision's own ``reason``
verbatim, both as a payload field and as a text line. Two situations arrive at
the same no-authority outcome and they are not the same thing: nothing was
stored for the source period, or a prior record was stored and could not be read
as prior-compensation evidence. Only the caller can tell them apart, so it
asserts the difference and the decision states it.

These tests execute that projection rather than inspecting it, because the claim
being checked is that the sentence REACHES the operator, and a read of the
rendering site is not that claim.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.iva_compensation import reconcile_iva_compensation_wallet
from .._app_live_payloads import IvaWalletAuthorityDecisionPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TAXPAYER_REF = "12345678Z"
_DECIDED_AT = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
_NOTHING_IS_AVAILABLE = "No AEAT wallet observation or local recurrence is available"


def _surfaced_reason(*, found_but_unusable: bool) -> str:
    """Return the reason an operator reads, through the projection the CLI builds."""
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

    payload = IvaWalletAuthorityDecisionPayload(
        taxpayer_ref=decision.taxpayer_ref,
        target_year=decision.target_year,
        target_period=decision.target_period,
        selected_authority=decision.selected_authority,
        selected_amount=decision.selected_amount,
        wallet_amount=decision.wallet_amount,
        local_recurrence_amount=decision.local_recurrence_amount,
        override_amount=decision.override_amount,
        divergence=decision.divergence,
        blocked=decision.blocked,
        stale_wallet=decision.stale_wallet,
        reason=decision.reason,
        wallet_captured_at=None,
        decided_at=decision.decided_at,
    )
    return payload.reason


def test_an_unreadable_prior_record_is_not_reported_to_the_operator_as_nothing_existing() -> None:
    """The defect this closes: the operator was told nothing exists while their record did.

    A taxpayer sent looking for evidence they already hold is worse served than
    one told plainly that the record could not be read, and the second is what
    actually happened.
    """
    surfaced = _surfaced_reason(found_but_unusable=True)

    assert _NOTHING_IS_AVAILABLE not in surfaced, (
        "the operator is still told no observation or recurrence is available while a prior "
        f"record exists and could not be read. Surfaced: {surfaced!r}"
    )
    assert "could not be read" in surfaced, f"the surfaced reason does not say what happened: {surfaced!r}"


def test_a_genuinely_absent_prior_record_still_reads_as_nothing_available() -> None:
    """The population the change must leave untouched.

    Without this the first test passes for the wrong reason -- a sentence that
    said "could not be read" unconditionally would satisfy it while making the
    genuinely-absent case false in the other direction.
    """
    surfaced = _surfaced_reason(found_but_unusable=False)

    assert _NOTHING_IS_AVAILABLE in surfaced, (
        f"the genuinely-absent case no longer states that nothing is available: {surfaced!r}"
    )
    assert "could not be read" not in surfaced, (
        f"the genuinely-absent case now claims a record was found and unread: {surfaced!r}"
    )


def test_the_two_situations_do_not_surface_the_same_sentence() -> None:
    """The whole point is that an operator can tell them apart."""
    assert _surfaced_reason(found_but_unusable=True) != _surfaced_reason(found_but_unusable=False)
