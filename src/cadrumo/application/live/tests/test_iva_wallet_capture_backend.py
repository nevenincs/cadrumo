"""Backend wallet capture persistence and reconciliation tests."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede.iva_compensation_wallet import IVA_COMPENSATION_WALLET_URL, parse_iva_compensation_wallet_html
from ....adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ....adapters.persistence.storage import has_active_bucket_session
from ....core import IvaCompensationStateProvenance, Period
from ....domain.iva_compensation import (
    IvaCompensationAuthoritySource,
    IvaCompensationDecisionReason,
    IvaCompensationPeriodState,
    IvaCompensationReconciliationDecision,
)
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import (
    dev_test_database_password,
    isolated_profile_storage_root,
    isolated_runtime_profile,
    read_db_at_rest_bytes,
)
from ....tests.user_profile import register_minimal_profile
from ...calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    IvaWalletDecisionRepository,
    iva_wallet_decision_key,
)
from ..iva_remote_state import (
    load_iva_remote_state,
    persist_and_reconcile_iva_compensation_wallet,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A checksum-valid synthetic NIF. This value reaches
#: ``IvaCompensationPeriodState.taxpayer_nif``, which is a ``SubjectTaxId``,
#: so a placeholder label is refused at the boundary.
_TAXPAYER_REF = "12345678Z"
_CAPTURED_AT = datetime(2026, 5, 20, 10, 30, 0, tzinfo=UTC)
_SESSION_BUCKET_ID = "38383838-3838-4383-8383-383838383838"
_OTHER_SESSION_BUCKET_ID = "39393939-3939-4393-8393-393939393939"


def _wallet_html(*, total: str, rows: str, target_year: int, target_period: str) -> str:
    return f"""
    <html><body>
      <h1>Cartera de cuotas de IVA a compensar</h1>
      <ul>
        <li><strong>Ejercicio:</strong><span>{target_year}</span></li>
        <li><strong>Período:</strong><span>{target_period}</span></li>
      </ul>
      <ul>
        <li><strong>Cuotas a compensar pendientes de períodos anteriores:</strong>
          <span>{total}</span></li>
      </ul>
      <table id="tablaResultados">
        <thead>
          <tr>
            <th>Ejercicio</th><th>Período</th><th>Cuota Disponible</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </body></html>
    """


@contextmanager
def _secure_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        yield profile.paths.database_file


def test_wallet_capture_backend_persists_reloads_reconciles_and_hides_storage_identity(tmp_path: Path) -> None:
    with _secure_backend(tmp_path) as db_path:
        observation_repo = CalculationObservationRepository()
        _store_prior_compensation(amount=Decimal("1200.00"))
        observation = parse_iva_compensation_wallet_html(
            _wallet_html(
                total="1.200,00",
                rows="<tr><td>2026</td><td>1T</td><td>1.200,00</td></tr>",
                target_year=2026,
                target_period="2T",
            ),
            taxpayer_nif=_TAXPAYER_REF,
            authenticated_identity=_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
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
            Path(report.observation_path),
        )
        reloaded_decision = IvaWalletDecisionRepository().load_decision(
            _TAXPAYER_REF,
            Period.from_year_and_code(2026, "2T"),
        )

        assert reloaded_wallet == observation
        assert reloaded_decision is not None
        assert not hasattr(report, "taxpayer_nif")
        assert report.taxpayer_ref.startswith("sha256:")
        assert report.total_pending == "1200.00"
        assert report.selected_authority == "aeat_wallet"
        assert report.local_recurrence_amount == "1200.00"
        assert report.divergence == "match"
        assert report.blocked is False
        assert report.decision_key == iva_wallet_decision_key(_TAXPAYER_REF, Period.from_year_and_code(2026, "2T"))
        database_bytes = read_db_at_rest_bytes(db_path)
        assert _TAXPAYER_REF.encode("ascii") not in database_bytes
        assert f"{_TAXPAYER_REF}:2026:2T".encode("ascii") not in database_bytes


def test_wallet_reconciliation_uses_runtime_bound_repository_for_decision_persistence(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path / "wallet-profile", bucket_id=_SESSION_BUCKET_ID) as profile:
        observation_repo = CalculationObservationRepository(objects=profile.repository)
        decision_repo = IvaWalletDecisionRepository(objects=profile.repository)
        _store_prior_compensation(amount=Decimal("1200.00"))
        observation = parse_iva_compensation_wallet_html(
            _wallet_html(
                total="1.200,00",
                rows="<tr><td>2026</td><td>1T</td><td>1.200,00</td></tr>",
                target_year=2026,
                target_period="2T",
            ),
            taxpayer_nif=_TAXPAYER_REF,
            authenticated_identity=_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=_CAPTURED_AT,
        )

        report = persist_and_reconcile_iva_compensation_wallet(
            observation,
            output_root=tmp_path / "wallet-evidence-bound",
            repository=observation_repo,
            decision_repository=decision_repo,
            decided_at=_CAPTURED_AT,
        )

        assert report.divergence == "match"
        assert decision_repo.load_decision(_TAXPAYER_REF, Period.from_year_and_code(2026, "2T")) is not None

    with isolated_runtime_profile(tmp_path=tmp_path / "other-profile", bucket_id=_OTHER_SESSION_BUCKET_ID):
        assert IvaWalletDecisionRepository().load_decision(_TAXPAYER_REF, Period.from_year_and_code(2026, "2T")) is None


def test_iva_wallet_history_report_surfaces_lots_and_authority_decisions(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        history_repo = IvaCompensationHistoryRepository()
        history_repo.save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                taxpayer_nif=_TAXPAYER_REF,
                filing_year=2022,
                period=Period.from_year_and_code(2022, "4T"),
                expediente_id="202230300000004Z",
                status="ALTA",
                presented_at=_CAPTURED_AT,
                generated_amount=Decimal("100.00"),
                applied_amount=Decimal("0.00"),
                available_end_amount=Decimal("100.00"),
                source_observation_key="303:2022:4T:EXP-2022-4T",
            ),
        )
        history_repo.save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                taxpayer_nif=_TAXPAYER_REF,
                filing_year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                expediente_id="202430300000001Z",
                status="ALTA",
                presented_at=_CAPTURED_AT,
                generated_amount=Decimal("30.00"),
                applied_amount=Decimal("40.00"),
                available_end_amount=Decimal("90.00"),
                source_observation_key="303:2024:1T:EXP-2024-1T",
            ),
        )
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif=_TAXPAYER_REF,
                target_year=2026,
                target_period=Period.from_year_and_code(2026, "2T"),
                selected_authority="aeat_wallet",
                selected_amount=Decimal("90.00"),
                wallet_amount=Decimal("90.00"),
                local_recurrence_amount=Decimal("90.00"),
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason_identity=IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED,
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
                        source_periods=(Period.from_year_and_code(2024, "1T"),),
                        amount=Decimal("90.00"),
                    ),
                ),
            ),
        )

        remote_state = load_iva_remote_state(as_of_year=2026)
        report = remote_state.history

    assert report.row_count == 2
    assert report.carry_forward_lot_count == 2
    assert [(lot.source_filing_year, lot.source_period) for lot in report.carry_forward_lots] == [
        (2022, Period.from_year_and_code(2022, "4T")),
        (2024, Period.from_year_and_code(2024, "1T")),
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
    assert "wallet:2026:2T" not in report.model_dump_json()
    assert "202230300000004Z" not in report.model_dump_json()
    assert "202430300000001Z" not in report.model_dump_json()
    assert _TAXPAYER_REF not in report.model_dump_json()


def test_remote_iva_evidence_roundtrips_through_profile_secure_sql(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        assert dev_test_database_password(profile.settings)

        history_repo = IvaCompensationHistoryRepository()
        history_repo.save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                taxpayer_nif=_TAXPAYER_REF,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "4T"),
                expediente_id="202530300000004Z",
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
            ),
        )

        wallet = parse_iva_compensation_wallet_html(
            _wallet_html(
                total="100,00",
                rows="<tr><td>2025</td><td>4T</td><td>100,00</td></tr>",
                target_year=2026,
                target_period="1T",
            ),
            taxpayer_nif=_TAXPAYER_REF,
            authenticated_identity=_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "1T"),
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=_CAPTURED_AT,
        )
        wallet_ref = FiledDeclaracionObservationStore(tmp_path / "remote-iva-evidence").persist_iva_wallet_observation(
            wallet,
        )
        assert _secure_object_namespace_count(profile.paths.database_file, wallet_ref.parts[-2]) == 1
        assert not (tmp_path / "remote-iva-evidence").exists()

        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif=_TAXPAYER_REF,
                target_year=2026,
                target_period=Period.from_year_and_code(2026, "1T"),
                selected_authority="aeat_wallet",
                selected_amount=Decimal("100.00"),
                wallet_amount=Decimal("100.00"),
                local_recurrence_amount=Decimal("100.00"),
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason_identity=IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED,
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
                        source_periods=(Period.from_year_and_code(2025, "4T"),),
                        amount=Decimal("100.00"),
                        captured_at=_CAPTURED_AT,
                    ),
                ),
            ),
        )

        reloaded_wallet = FiledDeclaracionObservationStore(
            tmp_path / "remote-iva-evidence",
        ).load_iva_wallet_observation(wallet_ref)
        reloaded_history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2025, "4T"))
        reloaded_decision = IvaWalletDecisionRepository().load_decision(
            _TAXPAYER_REF,
            Period.from_year_and_code(2026, "1T"),
        )
        remote_state = load_iva_remote_state(as_of_year=2026)
        report = remote_state.history

        assert reloaded_wallet == wallet
        assert reloaded_history is not None
        assert reloaded_history.pending_for_later_amount == Decimal("80.00")
        assert reloaded_history.generated_amount == Decimal("20.00")
        assert reloaded_history.available_end_amount == Decimal("100.00")
        assert reloaded_decision is not None
        assert reloaded_decision.selected_amount == reloaded_history.available_end_amount
        assert remote_state.wallet_observation_count == 1
        assert remote_state.wallet_observations[0].taxpayer_ref.startswith("sha256:")
        assert remote_state.wallet_observations[0].total_pending == str(reloaded_wallet.total_pending)
        assert report.row_count == 1
        assert report.authority_decision_count == 1
        assert report.authority_decisions[0].taxpayer_ref.startswith("sha256:")
        assert _TAXPAYER_REF not in remote_state.model_dump_json()
        assert "202530300000004Z" not in remote_state.model_dump_json()
        assert "303:2025:4T" not in remote_state.model_dump_json()
        assert _TAXPAYER_REF not in report.model_dump_json()

        database_bytes = read_db_at_rest_bytes(profile.paths.database_file)
        assert _TAXPAYER_REF.encode("ascii") not in database_bytes
        assert b"202530300000004Z" not in database_bytes


def test_remote_iva_evidence_reload_opens_active_profile_session_without_cli_bootstrap(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        with open_test_profile_session(_SESSION_BUCKET_ID):
            # Seeded through a detached WorkflowState, never a repository
            # read: the capsule publishes by an atomic no-replace rename
            # onto ``buckets/<profile-id>``, which a workflow-state
            # repository construction would otherwise materialise first
            # and collide with.
            register_minimal_profile(profile_id=_SESSION_BUCKET_ID)
            IvaCompensationHistoryRepository().save_period(
                IvaCompensationPeriodState(
                    provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                    taxpayer_nif=_TAXPAYER_REF,
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "4T"),
                    expediente_id="202530300000004Z",
                    status="ALTA",
                    presented_at=_CAPTURED_AT,
                    generated_amount=Decimal("20.00"),
                    available_end_amount=Decimal("20.00"),
                    source_observation_key="303:2025:4T:EXP-2025-4T",
                ),
            )

        assert has_active_bucket_session() is False

        remote_state = load_iva_remote_state(as_of_year=2026)

    assert remote_state.history.row_count == 1
    assert remote_state.history.carry_forward_lot_count == 1
    assert remote_state.history.rows[0].year == 2025
    assert remote_state.history.rows[0].period == Period.from_year_and_code(2025, "4T")
    assert _TAXPAYER_REF not in remote_state.model_dump_json()
    assert "202530300000004Z" not in remote_state.model_dump_json()


def _store_prior_compensation(*, amount: Decimal) -> None:
    IvaCompensationHistoryRepository().save_period(
        IvaCompensationPeriodState(
            provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
            taxpayer_nif=_TAXPAYER_REF,
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            expediente_id="202630300000001Z",
            status="ALTA",
            presented_at=_CAPTURED_AT,
            generated_amount=amount,
            applied_amount=Decimal("0.00"),
            available_end_amount=amount,
            source_observation_key="303:2026:1T:EXP-2026-1T",
        ),
    )


def _secure_object_namespace_count(database_path: Path, namespace: str) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM secure_objects WHERE namespace = ?",
            (namespace,),
        ).fetchone()
    return int(row[0])
