"""Backend integration for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import ObservedHeaderFact, Period, ResultDisposition
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.iva_compensation import IvaCompensationOverride, IvaCompensationReconciliationDecision
from ....tests import general_m303_filing_evidence
from ...calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    ObservationSourceKind,
    ResultDispositionProjection,
    reconcile_modelo_303_iva_compensation,
)
from .._calculation_actions import calculate_modelo_revision
from .._filed_revision_observation import persist_filed_revision_observation
from .._iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from .._iva_wallet_gate import (
    lazily_reconcile_local_iva_compensation_for_work_unit,
    resolve_iva_compensation_decision_for_calculation,
)
from ._iva_wallet_engine_support import (
    _DECIDED_AT,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _M303_DISPONIBLE_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _M303_RESULTADO_CASILLA,
    _TARGET_PERIOD,
    _TARGET_YEAR,
    _TAXPAYER_NIF,
    _create_modelo_303_work_unit,
    _modelo_303_engine_inputs,
    _negative_modelo_303_engine_inputs,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_operator_profile_with_tax_id,
    _store_prior_303_compensation,
    _wallet_observation,
    _work_unit_repositories,
    _work_unit_repositories_with_modelo_303_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_filing_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        loaded_decision = IvaWalletDecisionRepository().load_decision(
            _TAXPAYER_NIF,
            _period(_TARGET_YEAR, _TARGET_PERIOD),
        )
        assert loaded_decision == report.decision
        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.local_recurrence_amount == Decimal("1200.00")
        assert {source.source_kind for source in report.decision.authority_sources} == {
            "aeat_wallet",
            "local_recurrence",
            "filed_history_observation",
        }
        filed_history_source = next(
            source for source in report.decision.authority_sources if source.source_kind == "filed_history_observation"
        )
        assert filed_history_source.source_modelo == "303"
        assert filed_history_source.source_filing_year == _TARGET_YEAR
        assert filed_history_source.source_periods == (Period.from_year_and_code(_TARGET_YEAR, "1T"),)

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=loaded_decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-integration"
            ),
        )

        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("1200.00")
        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("1200.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("1000.00")
        assert revision.casilla_values[_M303_POSTERIOR_CASILLA] == Decimal("200.00")
        assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("0.00")
        assert revision.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("200.00")
        assert any(
            obs.casilla_id == _M303_COMPENSACION_APLICADA_CASILLA and obs.legal_refs and obs.source_refs
            for obs in revision.observations
        )


def test_no_seed_303_calculate_with_prior_filed_history_stays_safely_blocked(
    tmp_path: Path,
) -> None:
    """#50 guardrail 3 + safety: a real prior filed-history balance is NOT auto-carried.

    With a prior 303 filing leaving a 1200.00 carry-forward in the local history
    (and no caller override, no live wallet), the lazy reconcile must NOT silently
    auto-carry that filed-history-derived balance into casilla 110 — the domain
    deliberately blocks filed-history-only evidence pending explicit operator
    confirmation (it may diverge from AEAT's authoritative cartera). Calculate
    therefore refuses, NON-circularly: the operator is directed to confirm/override
    the carried amount, never auto-zeroed and never silently carried. (The genuine
    first-period-zero path above is the case that lazy-reconcile unblocks; this is
    the case it must keep gated.)
    """
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-integration"
                ),
            )

    # Blocked on the filed-history-only divergence — never silently carried.
    assert "missing" in str(exc_info.value) or exc_info.value.translated_message is not None
    # The blocked error MUST carry the divergence/reason context so the localized
    # `iva_wallet_blocked` template renders them instead of leaking `%{divergence}`/`%{reason}`.
    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_blocked"
    assert exc_info.value.context is not None
    assert exc_info.value.context["divergence"] == "missing"
    assert exc_info.value.context.get("reason")


def test_missing_wallet_filed_history_decision_blocks_real_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=None,
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        assert report.decision.selected_authority == "filed_history"
        assert report.decision.divergence == "filed_history_only"
        assert report.decision.blocked is True
        assert {source.source_kind for source in report.decision.authority_sources} == {
            "local_recurrence",
            "filed_history_observation",
        }

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="filed_history_only") as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-integration"
                ),
            )
        assert not hasattr(exc_info.value, "suggestion")
        assert (
            exc_info.value.precondition_failure.scenario_id
            == "modelo.work.calculate.iva_wallet.filed_history_requires_override"
        )
        assert len(calc_repo.load()) == 0


def test_prior_calculated_303_cannot_unblock_next_period_without_validated_filed_envelope(tmp_path: Path) -> None:
    taxpayer_nif = "X1234567L"
    decided_1t_at = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        work_repo, calc_repo, event_repo = _work_unit_repositories()
        snapshot_1t = _snapshot_303(period="1T")
        work_unit_1t = _create_modelo_303_work_unit(
            snapshot_1t,
            work_unit_repository=work_repo,
            clock=decided_1t_at,
        )
        revision_1t = calculate_modelo_revision(
            work_unit_1t.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values={
                **_modelo_303_engine_inputs(),
                "modelo-303-iva-repercutido-general-cuota": Decimal("84.00"),
            },
            iva_compensation_decision=None,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=decided_1t_at,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit_1t.period, reference="test:iva-wallet-engine-integration"
            ),
        )
        assert revision_1t.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("84.00")
        assert revision_1t.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("0.00")

        snapshot_2t = _snapshot_303(period="2T")
        work_unit_2t = _create_modelo_303_work_unit(snapshot_2t, work_unit_repository=work_repo)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="missing"):
            calculate_modelo_revision(
                work_unit_2t.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit_2t.period, reference="test:iva-wallet-engine-integration"
                ),
            )

        observation_repository = CalculationObservationRepository()
        persist_filed_revision_observation(
            revision=revision_1t,
            work_unit=work_unit_1t,
            repository=observation_repository,
            captured_at=decided_1t_at,
            result_disposition=ResultDisposition.INGRESO,
            taxpayer_nif=taxpayer_nif,
        )
        revision_2t = calculate_modelo_revision(
            work_unit_2t.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=None,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit_2t.period, reference="test:iva-wallet-engine-integration"
            ),
        )

        assert revision_2t.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
        decision = IvaWalletDecisionRepository().load_decision(
            taxpayer_nif,
            _period(_TARGET_YEAR, "2T"),
        )
        assert decision is not None
        assert decision.divergence == "local_recurrence_zero"
        assert decision.selected_amount == Decimal("0")
        assert decision.local_recurrence_amount == Decimal("0")
        assert any(
            source.source_locator == "observation-envelope:303:2026:1T"
            and source.source_periods == (_period(_TARGET_YEAR, "1T"),)
            for source in decision.authority_sources
        )


def test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_year_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(
            observation_repo,
            amount=Decimal("450.00"),
            filing_year=2025,
            period="4T",
        )
        target_year = 2026
        target_period = "1T"
        snapshot = _snapshot_303(filing_year=target_year, period=target_period)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(
                pending=Decimal("450.00"),
                target_year=target_year,
                target_period=_period(target_year, target_period),
                generation_year=2025,
                generation_period="4T",
            ),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.local_recurrence_amount == Decimal("450.00")
        assert report.prefill_report.prefilled[0].source_filing_year == 2025
        assert report.prefill_report.prefilled[0].source_periods == ("4T",)

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-integration"
            ),
        )

        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("450.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("450.00")
        assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("550.00")
        assert revision.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("0.00")


def _calculate_credit_1t(
    *,
    taxpayer_nif: str,
):
    """Produce a real negative 1T calculation whose filing disposition decides carry."""
    _store_operator_profile_with_tax_id(taxpayer_nif)
    work_repo, calc_repo, event_repo = _work_unit_repositories()
    snapshot = _snapshot_303(period="1T")
    work_unit = _create_modelo_303_work_unit(snapshot, work_unit_repository=work_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator",
        casilla_inputs={},
        binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
        backend_binding_values=_negative_modelo_303_engine_inputs(),
        iva_compensation_decision=None,
        filing_period_date=date(2026, 3, 31),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=_DECIDED_AT,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period, reference="test:iva-wallet-engine-integration"
        ),
    )
    assert revision.casilla_values[_M303_DISPONIBLE_CASILLA] > Decimal("0")
    return work_unit, revision, work_repo, calc_repo, event_repo


def _official_303_envelope(
    repository: CalculationObservationRepository,
    *,
    revision,
    work_unit,
    declaration_type: ResultDisposition,
    stamped_revision_id: str | None = None,
    result_disposition: ResultDisposition | None = None,
) -> None:
    """Persist an official-source envelope through the production encrypted repository."""
    source_headers = (
        ObservedHeaderFact(
            header_key="declaration_type",
            value=declaration_type.value,
            source_artefact_kind="submitted_file",
            source_locator=(f"modelo-303-fichero-boe:modelo-303-page-01:declaration-type:{declaration_type.value}"),
        ),
    )
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="303",
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
                observations=revision.observations,
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_DECIDED_AT,
            stamped_revision_id=stamped_revision_id or work_unit.revision_id,
            source_headers=source_headers,
            result_disposition=(
                ResultDispositionProjection(
                    disposition=result_disposition,
                    provenance_kind="source_header",
                    provenance_locator="test:conflicting-official-disposition",
                )
                if result_disposition is not None
                else None
            ),
            normalize_m303_carry=result_disposition is None,
        )
    )


def test_refunded_filed_envelope_feeds_zero_to_wallet_and_never_reappears(tmp_path: Path) -> None:
    """A filed D credit reaches later wallet decisions only as zero recurrence."""
    taxpayer_nif = _TAXPAYER_NIF
    with _secure_backend(tmp_path):
        work_unit_1t, revision_1t, work_repo, calc_repo, event_repo = _calculate_credit_1t(taxpayer_nif=taxpayer_nif)
        observations = CalculationObservationRepository()
        persist_filed_revision_observation(
            revision=revision_1t,
            work_unit=work_unit_1t,
            repository=observations,
            captured_at=_DECIDED_AT,
            result_disposition=ResultDisposition.DEVOLUCION,
            taxpayer_nif=taxpayer_nif,
        )

        work_unit_2t = _create_modelo_303_work_unit(
            _snapshot_303(period="2T"),
            work_unit_repository=work_repo,
        )
        revision_2t = calculate_modelo_revision(
            work_unit_2t.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=None,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit_2t.period, reference="test:iva-wallet-engine-integration"
            ),
        )
        persist_filed_revision_observation(
            revision=revision_2t,
            work_unit=work_unit_2t,
            repository=observations,
            captured_at=_DECIDED_AT,
            result_disposition=ResultDisposition.INGRESO,
            taxpayer_nif=taxpayer_nif,
        )

        work_unit_3t = _create_modelo_303_work_unit(
            _snapshot_303(period="3T"),
            work_unit_repository=work_repo,
        )
        revision_3t = calculate_modelo_revision(
            work_unit_3t.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=None,
            filing_period_date=date(2026, 9, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit_3t.period, reference="test:iva-wallet-engine-integration"
            ),
        )

        decisions = IvaWalletDecisionRepository()
        decision_2t = decisions.load_decision(taxpayer_nif, _period(2026, "2T"))
        decision_3t = decisions.load_decision(taxpayer_nif, _period(2026, "3T"))

    assert revision_2t.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
    assert revision_3t.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
    assert decision_2t is not None and decision_3t is not None
    assert decision_2t.selected_amount == decision_2t.local_recurrence_amount == Decimal("0")
    assert decision_3t.selected_amount == decision_3t.local_recurrence_amount == Decimal("0")


def test_compensated_filed_envelope_reports_its_validated_credit_to_wallet(tmp_path: Path) -> None:
    """The same real credit is non-zero only when its filed envelope elects C."""
    taxpayer_nif = _TAXPAYER_NIF
    with _secure_backend(tmp_path):
        work_unit, revision, work_repo, _, _ = _calculate_credit_1t(taxpayer_nif=taxpayer_nif)
        persisted_credit = revision.casilla_values[_M303_DISPONIBLE_CASILLA]
        persist_filed_revision_observation(
            revision=revision,
            work_unit=work_unit,
            repository=CalculationObservationRepository(),
            captured_at=_DECIDED_AT,
            result_disposition=ResultDisposition.COMPENSACION,
            taxpayer_nif=taxpayer_nif,
        )
        target = _create_modelo_303_work_unit(_snapshot_303(period="2T"), work_unit_repository=work_repo)
        decision = lazily_reconcile_local_iva_compensation_for_work_unit(
            target,
            snapshot=_snapshot_303(period="2T"),
        )

    assert decision is not None
    assert decision.selected_amount == decision.local_recurrence_amount == persisted_credit
    assert decision.blocked is True
    assert decision.divergence == "wallet_missing"
    assert any(
        source.source_locator == "observation-envelope:303:2026:1T" and source.amount == persisted_credit
        for source in decision.authority_sources
    )


def test_official_and_local_refund_envelopes_feed_the_same_wallet_recurrence(tmp_path: Path) -> None:
    """Official-pull and local-filing provenance share the exact D wallet result."""
    decisions = []
    for source_kind, taxpayer_nif in (("official", _TAXPAYER_NIF), ("local", _TAXPAYER_NIF)):
        with _secure_backend(tmp_path / source_kind):
            work_unit, revision, work_repo, _, _ = _calculate_credit_1t(taxpayer_nif=taxpayer_nif)
            observations = CalculationObservationRepository()
            if source_kind == "official":
                _official_303_envelope(
                    observations,
                    revision=revision,
                    work_unit=work_unit,
                    declaration_type=ResultDisposition.DEVOLUCION,
                )
            else:
                persist_filed_revision_observation(
                    revision=revision,
                    work_unit=work_unit,
                    repository=observations,
                    captured_at=_DECIDED_AT,
                    result_disposition=ResultDisposition.DEVOLUCION,
                    taxpayer_nif=taxpayer_nif,
                )
            target = _create_modelo_303_work_unit(_snapshot_303(period="2T"), work_unit_repository=work_repo)
            decision = lazily_reconcile_local_iva_compensation_for_work_unit(
                target,
                snapshot=_snapshot_303(period="2T"),
            )
            assert decision is not None
            decisions.append((decision.selected_amount, decision.local_recurrence_amount, decision.blocked))

    assert decisions == [(Decimal("0"), Decimal("0"), False), (Decimal("0"), Decimal("0"), False)]


@pytest.mark.parametrize(
    ("stamped_revision_id", "result_disposition"),
    [
        ("unrelated-stale-revision", None),
        (None, ResultDisposition.COMPENSACION),
    ],
)
def test_wallet_refuses_revision_mismatched_or_header_conflicting_official_envelope(
    tmp_path: Path,
    stamped_revision_id: str | None,
    result_disposition: ResultDisposition | None,
) -> None:
    """A stale calculation cannot rescue official D evidence that the envelope rejects."""
    taxpayer_nif = _TAXPAYER_NIF
    with _secure_backend(tmp_path):
        work_unit, revision, work_repo, _, _ = _calculate_credit_1t(taxpayer_nif=taxpayer_nif)
        _official_303_envelope(
            CalculationObservationRepository(),
            revision=revision,
            work_unit=work_unit,
            declaration_type=ResultDisposition.DEVOLUCION,
            stamped_revision_id=stamped_revision_id,
            result_disposition=result_disposition,
        )
        target = _create_modelo_303_work_unit(_snapshot_303(period="2T"), work_unit_repository=work_repo)
        decision = lazily_reconcile_local_iva_compensation_for_work_unit(
            target,
            snapshot=_snapshot_303(period="2T"),
        )

    assert decision is not None
    assert decision.selected_amount is None
    assert decision.local_recurrence_amount is None
    assert decision.divergence == "missing"
    assert decision.blocked is True


@pytest.mark.parametrize(
    "prior_disposition",
    [ResultDisposition.DEVOLUCION, ResultDisposition.COMPENSACION],
)
@pytest.mark.parametrize("mutation", ["stale_stamp", "header_conflict"])
def test_normal_wallet_replay_revalidates_prior_envelope_recurrence(
    tmp_path: Path,
    prior_disposition: ResultDisposition,
    mutation: str,
) -> None:
    """Neither a zero D decision nor a non-zero C decision outlives bad source evidence."""
    taxpayer_nif = _TAXPAYER_NIF
    with _secure_backend(tmp_path):
        work_unit, revision, work_repo, _, _ = _calculate_credit_1t(taxpayer_nif=taxpayer_nif)
        observations = CalculationObservationRepository()
        persist_filed_revision_observation(
            revision=revision,
            work_unit=work_unit,
            repository=observations,
            captured_at=_DECIDED_AT,
            result_disposition=prior_disposition,
            taxpayer_nif=taxpayer_nif,
        )
        target = _create_modelo_303_work_unit(_snapshot_303(period="2T"), work_unit_repository=work_repo)
        initial = lazily_reconcile_local_iva_compensation_for_work_unit(
            target,
            snapshot=_snapshot_303(period="2T"),
        )
        assert initial is not None
        assert any(source.source_locator == "observation-envelope:303:2026:1T" for source in initial.authority_sources)

        if mutation == "stale_stamp":
            _official_303_envelope(
                observations,
                revision=revision,
                work_unit=work_unit,
                declaration_type=ResultDisposition.DEVOLUCION,
                stamped_revision_id="unrelated-stale-revision",
            )
        else:
            _official_303_envelope(
                observations,
                revision=revision,
                work_unit=work_unit,
                declaration_type=ResultDisposition.DEVOLUCION,
                result_disposition=ResultDisposition.COMPENSACION,
            )

        replayed = resolve_iva_compensation_decision_for_calculation(
            target,
            snapshot=_snapshot_303(period="2T"),
            supplied_decision=None,
            repository=IvaWalletDecisionRepository(),
            binding_values=None,
            backend_binding_values=None,
            casilla_inputs=None,
            backend_casilla_inputs=None,
        )

    assert replayed is not None
    assert isinstance(replayed, IvaCompensationReconciliationDecision)
    assert replayed.selected_amount is None
    assert replayed.local_recurrence_amount is None
    assert replayed.divergence == "missing"
    assert replayed.blocked is True


def test_normal_wallet_replay_preserves_override_with_envelope_like_locator(tmp_path: Path) -> None:
    """A taxpayer override never becomes envelope recurrence from its free-form locator."""
    taxpayer_nif = _TAXPAYER_NIF
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        work_repo, _, _ = _work_unit_repositories()
        snapshot = _snapshot_303(period="2T")
        target = _create_modelo_303_work_unit(snapshot, work_unit_repository=work_repo)
        decision = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=taxpayer_nif,
            wallet=None,
            repository=CalculationObservationRepository(),
            override=IvaCompensationOverride(
                amount=Decimal("42"),
                operator_explanation="Taxpayer reviewed the prior IVA compensation evidence.",
                evidence_locator="observation-envelope:taxpayer-attestation",
                recorded_at=_DECIDED_AT,
            ),
            decided_at=_DECIDED_AT,
        ).decision

        replayed = resolve_iva_compensation_decision_for_calculation(
            target,
            snapshot=snapshot,
            supplied_decision=None,
            repository=IvaWalletDecisionRepository(),
            binding_values=None,
            backend_binding_values=None,
            casilla_inputs=None,
            backend_casilla_inputs=None,
        )

    assert decision.selected_authority == "taxpayer_override"
    assert replayed == decision
