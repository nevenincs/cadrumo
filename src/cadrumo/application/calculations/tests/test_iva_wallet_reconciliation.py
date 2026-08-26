"""Behavioral tests for IVA compensation wallet reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ....core import BindingSourceKind, IvaCompensationStateProvenance, Period
from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.iva_compensation import (
    IvaCompensationAuthoritySource,
    IvaCompensationDecisionReason,
    IvaCompensationOverride,
    IvaCompensationPeriodState,
    IvaCompensationReconciliationInputError,
    IvaCompensationWalletObservationProtocol,
    IvaWalletReconciliationError,
)
from ....tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from ...aggregation import CalculationSourceContext
from .._iva_compensation_history import IvaCompensationHistoryRepository
from .._iva_wallet_reconciliation import (
    IvaWalletDecisionSourceResolver,
    reconcile_iva_compensation_wallet,
    reconcile_modelo_303_iva_compensation,
)
from .._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
_BUCKET_ID = "35353535-3535-4353-8353-353535353535"
#: Checksum-valid synthetic NIFs. ``IvaCompensationPeriodState.taxpayer_nif``
#: is a ``SubjectTaxId``, so a placeholder label is refused at the boundary
#: and these fixtures must carry real identifier shapes.
_TAXPAYER_REF = "12345678Z"
_OTHER_TAXPAYER_REF = "87654321X"


def test_sede_observation_satisfies_the_domain_wallet_protocol() -> None:
    """The Sede adapter observation structurally satisfies the domain wallet port the
    reconciliation logic consumes, so the domain never imports the adapter."""
    wallet = _wallet(Decimal("100.00"))
    assert isinstance(wallet, IvaCompensationWalletObservationProtocol)


def _wallet(amount: Decimal, *, captured_at: datetime = _NOW) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        authenticated_identity=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=2026,
                generation_period=Period.from_year_and_code(2026, "1T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("1200"),
        decided_at=_NOW,
    )
    snapshot = bundled_authority().snapshot("303", filing_year=2026, period="2T")

    resolution = IvaWalletDecisionSourceResolver(decision).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200")}
    assert resolution.owned_sources == (BindingSourceKind.IVA_WALLET_DECISION,)
    assert {item.contributor_source_kind for item in resolution.provenance} == {
        "iva_wallet_decision",
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
        target_period=Period.from_year_and_code(2026, "2T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
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
        target_period=Period.from_year_and_code(2026, "2T"),
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


def test_missing_wallet_with_zero_aeat_filed_history_is_non_blocking_zero_authority() -> None:
    filed_history_source = IvaCompensationAuthoritySource(
        source_kind="filed_history_observation",
        amount=Decimal("0"),
        source_locator="303:2026:2T",
        captured_at=_NOW,
        source_modelo="303",
        source_filing_year=2026,
        source_periods=(Period.from_year_and_code(2026, "2T"),),
    )

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "3T"),
        wallet=None,
        local_recurrence_amount=Decimal("0"),
        local_recurrence_source=filed_history_source,
        decided_at=_NOW,
    )

    assert decision.selected_authority == "filed_history"
    assert decision.selected_amount == Decimal("0")
    assert decision.divergence == "filed_history_zero"
    assert decision.blocked is False
    assert {source.source_kind for source in decision.authority_sources} == {
        "local_recurrence",
        "filed_history_observation",
    }
    assert filed_history_source in decision.authority_sources


def test_modelo_303_reconciliation_auto_zeroes_from_positive_prior_local_filing(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        IvaCompensationHistoryRepository().save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.APP_FILING,
                taxpayer_nif=_TAXPAYER_REF,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "2T"),
                presented_at=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
                prior_pending_amount=Decimal("0"),
                applied_amount=Decimal("0"),
                pending_for_later_amount=Decimal("0"),
                period_result_amount=Decimal("399"),
                final_result_amount=Decimal("399"),
                generated_amount=Decimal("0"),
                available_end_amount=Decimal("0"),
                source_observation_key="303:2026:2T:positive-local-filing",
            ),
        )
        snapshot = bundled_authority().snapshot("303", filing_year=2026, period="3T")

        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_REF,
            wallet=None,
            repository=CalculationObservationRepository(),
            decided_at=_NOW,
        )

    assert report.decision.selected_authority == "filed_history"
    assert report.decision.selected_amount == Decimal("0")
    assert report.decision.local_recurrence_amount == Decimal("0")
    assert report.decision.divergence == "filed_history_zero"
    assert report.decision.blocked is False
    assert report.prefill_report.binding_values["modelo-303-compensacion-pendiente-anteriores"] == Decimal("0")
    assert {source.source_kind for source in report.decision.authority_sources} == {
        "local_recurrence",
        "filed_history_observation",
    }


def test_disabled_generic_recurrence_producer_contributes_nothing_to_the_returned_report(
    tmp_path: Path,
) -> None:
    """A producer the caller switched off must not shape the artefact it receives.

    The seeded history below is exactly what the sibling test above proves the
    generic reconstruction DOES find and DOES publish on the returned
    ``prefill_report``. A caller that disables it — because it supplies a
    stricter recurrence the generic path would undercut — must therefore get an
    empty report, not the same one with only the amount ignored.

    The two producers are not substitutable, so the selection must happen before
    the work rather than after it. Running the generic reconstruction regardless
    and discarding only its recurrence left its report reaching the caller, and
    spent a repository read plus a full history reconstruction on the one path
    that had just declared the producer must have no authority.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        IvaCompensationHistoryRepository().save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.APP_FILING,
                taxpayer_nif=_TAXPAYER_REF,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "2T"),
                presented_at=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
                prior_pending_amount=Decimal("0"),
                applied_amount=Decimal("0"),
                pending_for_later_amount=Decimal("0"),
                period_result_amount=Decimal("399"),
                final_result_amount=Decimal("399"),
                generated_amount=Decimal("0"),
                available_end_amount=Decimal("0"),
                source_observation_key="303:2026:2T:positive-local-filing",
            ),
        )
        snapshot = bundled_authority().snapshot("303", filing_year=2026, period="3T")

        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_REF,
            wallet=None,
            repository=CalculationObservationRepository(),
            decided_at=_NOW,
            use_repository_local_recurrence=False,
        )

    assert dict(report.prefill_report.binding_values) == {}, (
        "the generic recurrence producer was switched off and still published binding values on the "
        "returned report, so the caller receives an artefact shaped by a producer it disabled"
    )
    assert report.prefill_report.prefilled == ()
    assert report.prefill_report.unsatisfied == ()


def test_modelo_303_reconciliation_refuses_explicit_decision_repository_from_foreign_encrypted_bucket(
    tmp_path: Path,
) -> None:
    """A wallet decision cannot leave the observation repository's encrypted bucket."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        snapshot = bundled_authority().snapshot("303", filing_year=2026, period="2T")
        observation_repository = CalculationObservationRepository(objects=runtime.primary.repository)
        foreign_decision_repository = IvaWalletDecisionRepository(objects=runtime.secondary.repository)

        with pytest.raises(IvaCompensationReconciliationInputError) as excinfo:
            reconcile_modelo_303_iva_compensation(
                snapshot,
                taxpayer_nif=_TAXPAYER_REF,
                wallet=_wallet(Decimal("1200")),
                repository=observation_repository,
                decision_repository=foreign_decision_repository,
                decided_at=_NOW,
            )

        assert str(excinfo.value) == "application.calculations.iva_wallet.errors.decision_repository_backend_split"

        assert (
            IvaWalletDecisionRepository(objects=runtime.primary.repository).load_decision(
                _TAXPAYER_REF,
                Period.from_year_and_code(2026, "2T"),
            )
            is None
        )
        with runtime.switch_to_secondary():
            assert (
                foreign_decision_repository.load_decision(
                    _TAXPAYER_REF,
                    Period.from_year_and_code(2026, "2T"),
                )
                is None
            )


def test_modelo_303_reconciliation_persists_explicit_same_bucket_decision_repository_round_trip(
    tmp_path: Path,
) -> None:
    """An explicit repository sharing the active encrypted bucket keeps the decision readable."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        decision_repository = IvaWalletDecisionRepository(objects=profile.repository)
        snapshot = bundled_authority().snapshot("303", filing_year=2026, period="2T")

        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_REF,
            wallet=_wallet(Decimal("1200")),
            repository=observation_repository,
            decision_repository=decision_repository,
            decided_at=_NOW,
        )

        assert (
            decision_repository.load_decision(
                _TAXPAYER_REF,
                Period.from_year_and_code(2026, "2T"),
            )
            == report.decision
        )


def test_stale_wallet_records_local_recurrence_but_blocks_automatic_output() -> None:
    stale = _wallet(Decimal("1200"), captured_at=_NOW - timedelta(days=40))
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
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
        operator_explanation="Operator reviewed AEAT wallet and rectificativa evidence.",
        evidence_locator="operator-note:iva-wallet-review-2026-2T",
        recorded_at=_NOW,
    )

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
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

    with pytest.raises(IvaCompensationReconciliationInputError) as excinfo:
        reconcile_iva_compensation_wallet(
            taxpayer_nif=_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            wallet=wallet,
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
        )

    assert str(excinfo.value) == "errors.refused.reconciliation_evidence_invalid"
    context = excinfo.value.context or {}
    assert context["wallet_target_period"] != context["snapshot_target_period"]


def test_public_wallet_reconciliation_refuses_mismatched_wallet_taxpayer() -> None:
    wallet = _wallet(Decimal("1200")).model_copy(update={"taxpayer_nif": _OTHER_TAXPAYER_REF})

    with pytest.raises(IvaCompensationReconciliationInputError) as excinfo:
        reconcile_iva_compensation_wallet(
            taxpayer_nif=_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            wallet=wallet,
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
        )

    assert str(excinfo.value) == "errors.refused.reconciliation_evidence_invalid"
    assert (excinfo.value.context or {})["taxpayer_matches_request"] is False


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
    assert envelope.action is None


def test_negative_max_wallet_age_days_raises_iva_wallet_reconciliation_error() -> None:
    """Negative max_wallet_age_days violates the staleness-predicate precondition.

    The staleness helper is exercised by supplying a fresh wallet with a
    negative age limit so the guard is reached.  The expected raise is the
    typed CoreError subclass, not a bare ValueError.
    """

    with pytest.raises(IvaWalletReconciliationError) as excinfo:
        reconcile_iva_compensation_wallet(
            taxpayer_nif=_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            wallet=_wallet(Decimal("1200")),
            local_recurrence_amount=Decimal("1200"),
            decided_at=_NOW,
            max_wallet_age_days=-1,
        )

    assert str(excinfo.value) == "errors.refused.refused_iva_wallet_reconciliation_invariant"
    assert (excinfo.value.context or {})["non_negative"] is False


# ---------------------------------------------------------------------------
# first_period_zero divergence — LIVA art. 99.5 grounding
# ---------------------------------------------------------------------------


def _wallet_for_period(
    amount: Decimal,
    period: str,
    *,
    captured_at: datetime = _NOW,
) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        authenticated_identity=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        rows=(
            IvaCompensationWalletRow(
                generation_year=2025,
                generation_period=Period.from_year_and_code(2025, "4T"),
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
        target_period=Period.from_year_and_code(2026, "1T"),
        wallet=_wallet_for_period(Decimal("0"), "1T"),
        local_recurrence_amount=None,
        decided_at=_NOW,
        is_first_iva_period=True,
    )

    assert decision.divergence == "first_period_zero"
    assert decision.selected_authority == "aeat_wallet"
    assert decision.selected_amount == Decimal("0")
    assert decision.blocked is False
    assert decision.reason_identity is IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_AEAT_WALLET


def test_first_period_zero_with_seeded_zero_local_record_is_non_blocking() -> None:
    """A seeded-zero local recurrence for the first IVA period is non-blocking.

    When no AEAT wallet is available but a seeded-zero compensation state exists
    for the first registered period, the decision must be non-blocking with
    first_period_zero divergence under LIVA art. 99.5.
    """

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        wallet=None,
        local_recurrence_amount=Decimal("0"),
        decided_at=_NOW,
        is_first_iva_period=True,
    )

    assert decision.divergence == "first_period_zero"
    assert decision.selected_authority == "local_recurrence"
    assert decision.selected_amount == Decimal("0")
    assert decision.blocked is False
    assert decision.reason_identity is IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_LOCAL_RECURRENCE


def test_first_period_flag_does_not_suppress_non_zero_wallet_divergence() -> None:
    """is_first_iva_period=True must not suppress a non-zero wallet value.

    If the AEAT wallet shows a non-zero balance even though the caller marked
    the period as the first, the standard divergence logic applies — the
    non-zero value must be reconciled through the normal authority path.
    """

    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
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
        target_period=Period.from_year_and_code(2026, "1T"),
        wallet=stale,
        local_recurrence_amount=None,
        decided_at=_NOW,
        max_wallet_age_days=31,
        is_first_iva_period=True,
    )

    assert decision.divergence == "wallet_stale"
    assert decision.blocked is True
