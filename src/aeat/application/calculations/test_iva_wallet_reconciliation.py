"""Behavioral tests for IVA compensation wallet reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl

from ...adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ...core.resources import resources
from ..aggregation import CalculationSourceContext
from . import _iva_wallet_reconciliation as wallet_reconciliation
from ._iva_wallet_reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationOverride,
    IvaCompensationReconciliationInputError,
    IvaWalletDecisionSourceResolver,
    reconcile_iva_compensation_wallet,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)


def test_wallet_reconciliation_uses_public_sede_observation_export() -> None:
    assert wallet_reconciliation.IvaCompensationWalletObservation is IvaCompensationWalletObservation


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
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
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
    assert {source.source_kind for source in decision.authority_sources} == {
        "aeat_wallet",
        "local_recurrence",
    }
    assert decision.divergence == "match"
    assert decision.blocked is False


def test_iva_wallet_decision_source_resolver_emits_modelo_303_binding_and_provenance() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("1200"),
        decided_at=_NOW,
    )
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")

    resolution = IvaWalletDecisionSourceResolver(decision).resolve(
        CalculationSourceContext(
            bucket_id="operator",
            modelo="303",
            filing_year=2026,
            period="2T",
            revision=snapshot.revision,
        )
    )

    assert resolution.binding_values == {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("1200")
    }
    assert resolution.owned_sources == ("iva_wallet_decision",)
    assert {item.source_kind for item in resolution.provenance} == {
        "aeat_wallet",
        "local_recurrence",
    }
    assert {item.source_ref for item in resolution.provenance} >= {
        str(IVA_COMPENSATION_WALLET_URL),
        "local-recurrence:modelo-303-compensacion-pendiente-anteriores",
    }


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


def test_missing_wallet_with_aeat_filed_history_is_explicit_filed_history_only_authority() -> None:
    filed_history_source = IvaCompensationAuthoritySource(
        source_kind="filed_history_observation",
        amount=Decimal("800"),
        source_locator="303:2025:4T",
        captured_at=_NOW,
        source_modelo="303",
        source_filing_year=2025,
        source_periods=("4T",),
    )

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        wallet=None,
        local_recurrence_amount=Decimal("800"),
        local_recurrence_source=filed_history_source,
        decided_at=_NOW,
    )

    assert decision.selected_authority == "filed_history"
    assert decision.selected_amount == Decimal("800")
    assert decision.divergence == "filed_history_only"
    assert decision.blocked is False
    assert decision.authority_sources == (filed_history_source,)


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
    assert {source.source_kind for source in decision.authority_sources} == {
        "aeat_wallet",
        "local_recurrence",
        "taxpayer_override",
    }
    assert decision.divergence == "override"
    assert decision.blocked is False


def test_public_wallet_reconciliation_refuses_mismatched_wallet_target() -> None:
    wallet = _wallet(Decimal("1200")).model_copy(update={"target_period": "1T"})

    with pytest.raises(IvaCompensationReconciliationInputError, match="target"):
        reconcile_iva_compensation_wallet(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period="2T",
            wallet=wallet,
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
        )


def test_public_wallet_reconciliation_refuses_mismatched_wallet_taxpayer() -> None:
    wallet = _wallet(Decimal("1200")).model_copy(update={"taxpayer_nif": "99999999R"})

    with pytest.raises(IvaCompensationReconciliationInputError, match="taxpayer"):
        reconcile_iva_compensation_wallet(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period="2T",
            wallet=wallet,
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
        )
