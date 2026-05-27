"""Backend wallet capture persistence and reconciliation tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    FiledDeclaracionObservationStore,
    parse_iva_compensation_wallet_html,
)
from aeat.application.calculations import (
    CalculationObservationRepository,
    IvaCompensationAuthoritySource,
    IvaCompensationHistoryRepository,
    IvaCompensationPeriodState,
    IvaCompensationReconciliationDecision,
    IvaWalletDecisionRepository,
    iva_wallet_decision_key,
)
from aeat.core.resources import resources
from aeat.domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from aeat.tests.secure_sql import dev_test_database_password, isolated_runtime_profile

from . import list_iva_compensation_history, persist_and_reconcile_iva_compensation_wallet

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_TAXPAYER_NIF = "12345678Z"
_CAPTURED_AT = datetime(2026, 5, 20, 10, 30, 0, tzinfo=UTC)
_BUCKET_ID = "operator"
_SESSION_BUCKET_ID = "ephemeral"


@contextmanager
def _secure_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        yield profile.paths.db_dir / "aeat.db"


def test_wallet_capture_backend_persists_reloads_reconciles_and_hides_storage_identity(tmp_path: Path) -> None:
    with _secure_backend(tmp_path) as db_path:
        observation_repo = CalculationObservationRepository()
        _store_prior_compensation(observation_repo, amount=Decimal("1200.00"))
        observation = parse_iva_compensation_wallet_html(
            """
            <html><body>
              <table>
                <tr>
                  <th>Ejercicio</th><th>Periodo</th><th>Generado</th>
                  <th>Aplicado</th><th>Pendiente</th>
                </tr>
                <tr>
                  <td>2026</td><td>1T</td><td>1.200,00</td><td>0,00</td><td>1.200,00</td>
                </tr>
              </table>
            </body></html>
            """,
            taxpayer_nif=_TAXPAYER_NIF,
            authenticated_identity=_TAXPAYER_NIF,
            target_year=2026,
            target_period="2T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=_CAPTURED_AT,
        )

        report = persist_and_reconcile_iva_compensation_wallet(
            observation,
            output_root=tmp_path / "wallet-evidence",
            repository=observation_repo,
            decided_at=_CAPTURED_AT,
        )

        reloaded_wallet = FiledDeclaracionObservationStore(tmp_path / "wallet-evidence").load_iva_wallet_observation(
            Path(report.observation_path)
        )
        reloaded_decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, 2026, "2T")

        assert reloaded_wallet == observation
        assert reloaded_decision is not None
        assert not hasattr(report, "taxpayer_nif")
        assert report.taxpayer_ref.startswith("sha256:")
        assert report.total_pending == "1200.00"
        assert report.selected_authority == "aeat_wallet"
        assert report.local_recurrence_amount == "1200.00"
        assert report.divergence == "match"
        assert report.blocked is False
        assert report.decision_key == iva_wallet_decision_key(_TAXPAYER_NIF, 2026, "2T")
        database_bytes = db_path.read_bytes()
        assert _TAXPAYER_NIF.encode("ascii") not in database_bytes
        assert f"{_TAXPAYER_NIF}:2026:2T".encode("ascii") not in database_bytes


def test_iva_wallet_history_report_surfaces_lots_and_authority_decisions(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        history_repo = IvaCompensationHistoryRepository()
        history_repo.save_period(
            IvaCompensationPeriodState(
                taxpayer_nif=_TAXPAYER_NIF,
                filing_year=2022,
                period="4T",
                expediente_id="EXP-2022-4T",
                status="ALTA",
                presented_at=_CAPTURED_AT,
                generated_amount=Decimal("100.00"),
                applied_amount=Decimal("0.00"),
                available_end_amount=Decimal("100.00"),
                source_observation_key="303:2022:4T:EXP-2022-4T",
            )
        )
        history_repo.save_period(
            IvaCompensationPeriodState(
                taxpayer_nif=_TAXPAYER_NIF,
                filing_year=2024,
                period="1T",
                expediente_id="EXP-2024-1T",
                status="ALTA",
                presented_at=_CAPTURED_AT,
                generated_amount=Decimal("30.00"),
                applied_amount=Decimal("40.00"),
                available_end_amount=Decimal("90.00"),
                source_observation_key="303:2024:1T:EXP-2024-1T",
            )
        )
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif=_TAXPAYER_NIF,
                target_year=2026,
                target_period="2T",
                selected_authority="aeat_wallet",
                selected_amount=Decimal("90.00"),
                wallet_amount=Decimal("90.00"),
                local_recurrence_amount=Decimal("90.00"),
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason="AEAT wallet matches local recurrence.",
                wallet_captured_at=_CAPTURED_AT,
                decided_at=_CAPTURED_AT,
                authority_sources=(
                    IvaCompensationAuthoritySource(
                        source_kind="aeat_wallet",
                        source_locator="wallet:2026:2T",
                        amount=Decimal("90.00"),
                    ),
                    IvaCompensationAuthoritySource(
                        source_kind="filed_history_observation",
                        source_locator="303:2024:1T:EXP-2024-1T",
                        source_modelo="303",
                        source_filing_year=2024,
                        source_periods=("1T",),
                        amount=Decimal("90.00"),
                    ),
                ),
            )
        )

        report = list_iva_compensation_history(as_of_year=2026)

    assert report.row_count == 2
    assert report.carry_forward_lot_count == 2
    assert [(lot.source_filing_year, lot.source_period) for lot in report.carry_forward_lots] == [
        (2022, "4T"),
        (2024, "1T"),
    ]
    assert report.carry_forward_lots[0].applied_amount == "40.00"
    assert report.carry_forward_lots[0].remaining_amount == "60.00"
    assert report.carry_forward_lots[0].age_years == 4
    assert report.carry_forward_lots[0].expiry_review_state == "expiry_review_due"
    assert report.authority_decision_count == 1
    decision = report.authority_decisions[0]
    assert decision.selected_authority == "aeat_wallet"
    assert decision.selected_amount == "90.00"
    assert any(
        "source_kind" not in source and source.startswith("aeat_wallet") for source in decision.authority_sources
    )
    assert _TAXPAYER_NIF not in report.model_dump_json()


def test_remote_iva_evidence_roundtrips_through_profile_secure_sql(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        assert dev_test_database_password(profile.settings)

        history_repo = IvaCompensationHistoryRepository()
        history_repo.save_period(
            IvaCompensationPeriodState(
                taxpayer_nif=_TAXPAYER_NIF,
                filing_year=2025,
                period="4T",
                expediente_id="EXP-2025-4T",
                status="ALTA",
                presented_at=_CAPTURED_AT,
                prior_pending_amount=Decimal("25.00"),
                applied_amount=Decimal("5.00"),
                pending_for_later_amount=Decimal("80.00"),
                period_result_amount=Decimal("-20.00"),
                final_result_amount=Decimal("-20.00"),
                generated_amount=Decimal("20.00"),
                available_end_amount=Decimal("100.00"),
                source_observation_key="303:2025:4T:EXP-2025-4T",
            )
        )

        wallet = parse_iva_compensation_wallet_html(
            """
            <html><body>
              <table>
                <tr>
                  <th>Ejercicio</th><th>Periodo</th><th>Generado</th>
                  <th>Aplicado</th><th>Pendiente</th>
                </tr>
                <tr>
                  <td>2025</td><td>4T</td><td>100,00</td><td>0,00</td><td>100,00</td>
                </tr>
              </table>
            </body></html>
            """,
            taxpayer_nif=_TAXPAYER_NIF,
            authenticated_identity=_TAXPAYER_NIF,
            target_year=2026,
            target_period="1T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=_CAPTURED_AT,
        )
        wallet_ref = FiledDeclaracionObservationStore(tmp_path / "remote-iva-evidence").persist_iva_wallet_observation(
            wallet
        )

        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif=_TAXPAYER_NIF,
                target_year=2026,
                target_period="1T",
                selected_authority="aeat_wallet",
                selected_amount=Decimal("100.00"),
                wallet_amount=Decimal("100.00"),
                local_recurrence_amount=Decimal("100.00"),
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason="AEAT wallet matches filed-history recurrence.",
                wallet_captured_at=_CAPTURED_AT,
                decided_at=_CAPTURED_AT,
                authority_sources=(
                    IvaCompensationAuthoritySource(
                        source_kind="aeat_wallet",
                        source_locator=str(wallet_ref),
                        amount=Decimal("100.00"),
                        captured_at=_CAPTURED_AT,
                    ),
                    IvaCompensationAuthoritySource(
                        source_kind="filed_history_observation",
                        source_locator="303:2025:4T:EXP-2025-4T",
                        source_modelo="303",
                        source_filing_year=2025,
                        source_periods=("4T",),
                        amount=Decimal("100.00"),
                        captured_at=_CAPTURED_AT,
                    ),
                ),
            )
        )

        reloaded_wallet = FiledDeclaracionObservationStore(
            tmp_path / "remote-iva-evidence"
        ).load_iva_wallet_observation(wallet_ref)
        reloaded_history = IvaCompensationHistoryRepository().load_period(2025, "4T")
        reloaded_decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, 2026, "1T")
        report = list_iva_compensation_history(as_of_year=2026)

        # available_end is the structural sum pending_for_later +
        # generated; deriving the expected from the same observation
        # avoids the hand-summed-literal tautology pattern.
        expected_available_end = (
            reloaded_history.pending_for_later_amount
            + reloaded_history.generated_amount
        )
        assert reloaded_wallet == wallet
        assert reloaded_history is not None
        assert reloaded_history.available_end_amount == expected_available_end
        assert reloaded_decision is not None
        assert reloaded_decision.selected_amount == reloaded_history.available_end_amount
        assert report.row_count == 1
        assert report.authority_decision_count == 1
        assert report.authority_decisions[0].taxpayer_ref.startswith("sha256:")
        assert _TAXPAYER_NIF not in report.model_dump_json()

        database_bytes = (profile.paths.db_dir / "aeat.db").read_bytes()
        assert _TAXPAYER_NIF.encode("ascii") not in database_bytes
        assert b"EXP-2025-4T" not in database_bytes


def _store_prior_compensation(repository: CalculationObservationRepository, *, amount: Decimal) -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
    casilla = next(item for item in snapshot.revision.casillas if item.id == "iva.compensacion-disponible-fin-periodo")
    formula = next(item for item in snapshot.revision.formulas if item.target == casilla.id)
    repository.save_observation(
        RegistryModeloObservation(
            modelo="303",
            filing_year=2026,
            period="1T",
            observations=(
                CasillaObservation(
                    casilla_id=casilla.id,
                    value=amount,
                    formula_id=formula.id,
                    legal_refs=tuple(casilla.legal_refs),
                    source_refs=tuple(casilla.source_refs),
                ),
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CAPTURED_AT,
    )
