"""Behavioral tests for IVA compensation wallet reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl

from ...adapters.outbound.aeat.sede._schema import (
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ._iva_wallet_reconciliation import (
    IvaCompensationOverride,
    reconcile_iva_compensation_wallet,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)


def _wallet(amount: Decimal, *, captured_at: datetime = _NOW) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2026,
        target_period="2T",
        rows=(
            IvaCompensationWalletRow(
                generation_year=2026,
                generation_period="1T",
                generated_amount=amount,
                applied_amount=Decimal("0"),
                pending_amount=amount,
                raw_label="2026 1T",
            ),
        ),
        total_pending=amount,
        source_url=AnyHttpUrl("https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas"),
        captured_at=captured_at,
        raw_sha256="a" * 64,
    )


def test_wallet_match_selects_aeat_wallet_and_keeps_local_as_corroboration() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("1200"),
        decided_at=_NOW,
    )

    assert decision.selected_authority == "aeat_wallet"
    assert decision.selected_amount == Decimal("1200")
    assert decision.wallet_amount == Decimal("1200")
    assert decision.local_recurrence_amount == Decimal("1200")
    assert decision.divergence == "match"
    assert decision.blocked is False


def test_wallet_without_local_history_is_authoritative_but_not_cross_verified() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=None,
        decided_at=_NOW,
    )

    assert decision.selected_authority == "aeat_wallet"
    assert decision.selected_amount == Decimal("1200")
    assert decision.local_recurrence_amount is None
    assert decision.divergence == "wallet_only"
    assert decision.blocked is False


def test_wallet_higher_than_local_blocks_automatic_output() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("800"),
        decided_at=_NOW,
    )

    assert decision.selected_authority == "missing"
    assert decision.selected_amount is None
    assert decision.divergence == "wallet_higher"
    assert decision.blocked is True


def test_wallet_lower_than_local_blocks_automatic_output() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("400")),
        local_recurrence_amount=Decimal("800"),
        decided_at=_NOW,
    )

    assert decision.selected_authority == "missing"
    assert decision.divergence == "wallet_lower"
    assert decision.blocked is True


def test_missing_wallet_uses_local_recurrence_as_lower_confidence_fallback() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=None,
        local_recurrence_amount=Decimal("800"),
        decided_at=_NOW,
    )

    assert decision.selected_authority == "local_recurrence"
    assert decision.selected_amount == Decimal("800")
    assert decision.divergence == "wallet_missing"
    assert decision.blocked is False


def test_stale_wallet_uses_local_recurrence_as_lower_confidence_fallback() -> None:
    stale = _wallet(Decimal("1200"), captured_at=_NOW - timedelta(days=40))
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=stale,
        local_recurrence_amount=Decimal("800"),
        decided_at=_NOW,
        max_wallet_age_days=31,
    )

    assert decision.selected_authority == "local_recurrence"
    assert decision.selected_amount == Decimal("800")
    assert decision.wallet_amount == Decimal("1200")
    assert decision.divergence == "wallet_stale"
    assert decision.stale_wallet is True
    assert decision.blocked is False


def test_taxpayer_override_selects_override_with_wallet_and_local_context() -> None:
    override = IvaCompensationOverride(
        amount=Decimal("1000"),
        reason="Operator reviewed AEAT wallet and rectificativa evidence.",
        evidence_locator="operator-note:iva-wallet-review-2026-2T",
        recorded_at=_NOW,
    )

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("800"),
        override=override,
        decided_at=_NOW,
    )

    assert decision.selected_authority == "taxpayer_override"
    assert decision.selected_amount == Decimal("1000")
    assert decision.wallet_amount == Decimal("1200")
    assert decision.local_recurrence_amount == Decimal("800")
    assert decision.override_amount == Decimal("1000")
    assert decision.divergence == "override"
    assert decision.blocked is False
