"""Behavioral tests for IVA compensation wallet reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ....core import Period
from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....core.resources import resources
from ....domain.iva_compensation._errors import (
    IvaCompensationReconciliationInputError,
    IvaWalletReconciliationError,
)
from ....domain.iva_compensation._reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationOverride,
    IvaCompensationWalletObservationProtocol,
)
from ...aggregation import CalculationSourceContext
from .._iva_wallet_reconciliation import (
    IvaWalletDecisionSourceResolver,
    reconcile_iva_compensation_wallet,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
_TAXPAYER_REF = "synthetic-taxpayer"
_OTHER_TAXPAYER_REF = "other-synthetic-taxpayer"


def test_sede_observation_satisfies_the_domain_wallet_protocol() -> None:
    """The Sede adapter observation structurally satisfies the domain wallet port the
    reconciliation logic consumes, so the domain never imports the adapter (DB-26 contract)."""
    wallet = _wallet(Decimal("100.00"))
    assert isinstance(wallet, IvaCompensationWalletObservationProtocol)


def _wallet(amount: Decimal, *, captured_at: datetime = _NOW) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        authenticated_identity=_TAXPAYER_REF,
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
        taxpayer_nif=_TAXPAYER_REF,
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
        taxpayer_nif=_TAXPAYER_REF,
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
            period=Period.from_year_and_code(2026, "2T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200")}
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
        taxpayer_nif=_TAXPAYER_REF,
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
        taxpayer_nif=_TAXPAYER_REF,
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
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="2T",
        wallet=_wallet(Decimal("400")),
        local_recurrence_amount=Decimal("800"),
        decided_at=_NOW,
    )

    assert decision.selected_authority == "missing"
    assert decision.divergence == "wallet_lower"
    assert decision.blocked is True


def test_missing_wallet_records_local_recurrence_but_blocks_automatic_output() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="2T",
        wallet=None,
        local_recurrence_amount=Decimal("800"),
        decided_at=_NOW,
    )

    assert decision.selected_authority == "local_recurrence"
    assert decision.selected_amount == Decimal("800")
    assert decision.divergence == "wallet_missing"
    assert decision.blocked is True


def test_missing_wallet_with_aeat_filed_history_is_explicit_filed_history_only_authority() -> None:
    filed_history_source = IvaCompensationAuthoritySource(
        source_kind="filed_history_observation",
        amount=Decimal("800"),
        source_locator="303:2025:4T",
        captured_at=_NOW,
        source_modelo="303",
        source_filing_year=2025,
        source_periods=(Period.from_year_and_code(2025, "4T"),),
    )

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
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
    assert decision.blocked is True
    assert {source.source_kind for source in decision.authority_sources} == {
        "local_recurrence",
        "filed_history_observation",
    }
    assert filed_history_source in decision.authority_sources


def test_stale_wallet_records_local_recurrence_but_blocks_automatic_output() -> None:
    stale = _wallet(Decimal("1200"), captured_at=_NOW - timedelta(days=40))
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
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
    assert decision.blocked is True


def test_taxpayer_override_selects_override_with_wallet_and_local_context() -> None:
    override = IvaCompensationOverride(
        amount=Decimal("1000"),
        reason="Operator reviewed AEAT wallet and rectificativa evidence.",
        evidence_locator="operator-note:iva-wallet-review-2026-2T",
        recorded_at=_NOW,
    )

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
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
            taxpayer_nif=_TAXPAYER_REF,
            target_year=2026,
            target_period="2T",
            wallet=wallet,
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
        )


def test_public_wallet_reconciliation_refuses_mismatched_wallet_taxpayer() -> None:
    wallet = _wallet(Decimal("1200")).model_copy(update={"taxpayer_nif": _OTHER_TAXPAYER_REF})

    with pytest.raises(IvaCompensationReconciliationInputError, match="taxpayer"):
        reconcile_iva_compensation_wallet(
            taxpayer_nif=_TAXPAYER_REF,
            target_year=2026,
            target_period="2T",
            wallet=wallet,
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
        )


# ---------------------------------------------------------------------------
# contract — IvaWalletReconciliationError registry and raise-site coverage
# ---------------------------------------------------------------------------


def test_iva_wallet_reconciliation_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_IVA_WALLET_RECONCILIATION_INVARIANT" in ERROR_REGISTRY


def test_iva_wallet_reconciliation_error_round_trips_through_build_error_envelope() -> None:
    exc = IvaWalletReconciliationError("max_wallet_age_days must be non-negative")
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_IVA_WALLET_RECONCILIATION_INVARIANT"
    assert envelope.retryable is False
    assert envelope.suggestion == "aeat app live iva-wallet pull"


def test_negative_max_wallet_age_days_raises_iva_wallet_reconciliation_error() -> None:
    """Negative max_wallet_age_days violates the staleness-predicate precondition.

    The staleness helper is exercised by supplying a fresh wallet with a
    negative age limit so the guard is reached.  The expected raise is the
    typed CoreError subclass, not a bare ValueError.
    """

    with pytest.raises(IvaWalletReconciliationError, match="non-negative"):
        reconcile_iva_compensation_wallet(
            taxpayer_nif=_TAXPAYER_REF,
            target_year=2026,
            target_period="2T",
            wallet=_wallet(Decimal("1200")),
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
            max_wallet_age_days=-1,
        )


# ---------------------------------------------------------------------------
# first_period_zero divergence — LIVA art. 99.5 grounding
# ---------------------------------------------------------------------------


def _wallet_for_period(
    amount: Decimal, period: str, *, captured_at: datetime = _NOW,
) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        authenticated_identity=_TAXPAYER_REF,
        target_year=2026,
        target_period=period,
        rows=(
            IvaCompensationWalletRow(
                generation_year=2025,
                generation_period="4T",
                generated_amount=amount,
                applied_amount=Decimal("0"),
                pending_amount=amount,
                raw_label="2025 4T",
            ),
        )
        if amount > Decimal("0")
        else (),
        total_pending=amount,
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
        captured_at=captured_at,
        raw_sha256="b" * 64,
    )


def test_first_period_zero_with_aeat_wallet_zero_is_non_blocking() -> None:
    """AEAT wallet showing zero for the first registered IVA period is non-blocking.

    Under LIVA art. 99.5 there is no prior compensation balance for the first
    period; zero is legally certain.  The decision must select aeat_wallet with
    first_period_zero divergence and blocked=False.
    """

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="1T",
        wallet=_wallet_for_period(Decimal("0"), "1T"),
        local_recurrence_amount=None,
        decided_at=_NOW,
        is_first_iva_period=True,
    )

    assert decision.divergence == "first_period_zero"
    assert decision.selected_authority == "aeat_wallet"
    assert decision.selected_amount == Decimal("0")
    assert decision.blocked is False
    assert "art. 99.5" in decision.reason
    assert "LIVA" in decision.reason


def test_first_period_zero_with_seeded_zero_local_record_is_non_blocking() -> None:
    """A seeded-zero local recurrence for the first IVA period is non-blocking.

    When no AEAT wallet is available but a seeded-zero compensation state exists
    for the first registered period, the decision must be non-blocking with
    first_period_zero divergence under LIVA art. 99.5.
    """

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="1T",
        wallet=None,
        local_recurrence_amount=Decimal("0"),
        decided_at=_NOW,
        is_first_iva_period=True,
    )

    assert decision.divergence == "first_period_zero"
    assert decision.selected_authority == "local_recurrence"
    assert decision.selected_amount == Decimal("0")
    assert decision.blocked is False
    assert "art. 99.5" in decision.reason
    assert "LIVA" in decision.reason


def test_first_period_flag_does_not_suppress_non_zero_wallet_divergence() -> None:
    """is_first_iva_period=True must not suppress a non-zero wallet value.

    If the AEAT wallet shows a non-zero balance even though the caller marked
    the period as the first, the standard divergence logic applies — the
    non-zero value must be reconciled through the normal authority path.
    """

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="1T",
        wallet=_wallet_for_period(Decimal("500"), "1T"),
        local_recurrence_amount=None,
        decided_at=_NOW,
        is_first_iva_period=True,
    )

    assert decision.divergence == "wallet_only"
    assert decision.selected_authority == "aeat_wallet"
    assert decision.selected_amount == Decimal("500")
    assert decision.blocked is False


def test_first_period_flag_does_not_suppress_stale_wallet() -> None:
    """A stale wallet is not promoted to non-blocking by is_first_iva_period.

    The first_period_zero path only applies to a fresh wallet showing zero.
    A stale wallet must still route through the staleness branch regardless
    of the first-period flag.
    """

    stale = _wallet_for_period(Decimal("0"), "1T", captured_at=_NOW - timedelta(days=40))

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period="1T",
        wallet=stale,
        local_recurrence_amount=None,
        decided_at=_NOW,
        max_wallet_age_days=31,
        is_first_iva_period=True,
    )

    assert decision.divergence == "wallet_stale"
    assert decision.blocked is True
