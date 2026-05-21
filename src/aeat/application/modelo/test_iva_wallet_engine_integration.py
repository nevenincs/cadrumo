"""Backend integration for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.outbound.aeat.sede import IVA_COMPENSATION_WALLET_URL, parse_iva_compensation_wallet_html
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from aeat.application.calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    reconcile_modelo_303_iva_compensation,
)
from aeat.application.modelo import (
    ModeloIvaWalletReconciliationBlocked,
    calculate_modelo_revision,
    create_work_unit,
)
from aeat.application.user_profile import UserProfileLifecycleRepository
from aeat.core.config import override_settings
from aeat.core.resources import resources
from aeat.domain.buckets import BucketEventHistoryRepository
from aeat.domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.user_profile import UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_TAXPAYER_NIF = "12345678Z"
_TARGET_YEAR = 2026
_TARGET_PERIOD = "2T"
_DECIDED_AT = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    with provider, override_settings(
        aeat_database_url=f"sqlite:///{(tmp_path / 'iva-wallet-engine.db').as_posix()}",
        aeat_active_profile="operator",
    ) as settings:
        engine = get_engine(settings)
        SecureObjectRepository(engine=engine)
        try:
            yield
        finally:
            dispose_engine(settings)


def _wallet_observation(
    *,
    pending: Decimal,
    target_year: int = _TARGET_YEAR,
    target_period: str = _TARGET_PERIOD,
    generation_year: int = 2026,
    generation_period: str = "1T",
):
    pending_text = _spanish_amount(pending)
    return parse_iva_compensation_wallet_html(
        f"""
        <html>
          <body>
            <table>
              <thead>
                <tr>
                  <th>Ejercicio</th><th>Periodo</th><th>Generado</th>
                  <th>Aplicado</th><th>Pendiente</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{generation_year}</td><td>{generation_period}</td>
                  <td>{pending_text}</td><td>0,00</td><td>{pending_text}</td>
                </tr>
              </tbody>
            </table>
          </body>
        </html>
        """,
        taxpayer_nif=_TAXPAYER_NIF,
        authenticated_identity=_TAXPAYER_NIF,
        target_year=target_year,
        target_period=target_period,
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=_DECIDED_AT,
    )


def _spanish_amount(value: Decimal) -> str:
    whole, cents = f"{value:.2f}".split(".")
    chunks: list[str] = []
    while whole:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    return f"{'.'.join(reversed(chunks))},{cents}"


def _store_prior_303_compensation(
    repo: CalculationObservationRepository,
    *,
    amount: Decimal,
    filing_year: int = _TARGET_YEAR,
    period: str = "1T",
) -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
    casilla = next(
        item for item in snapshot.revision.casillas if item.id == "iva.compensacion-disponible-fin-periodo"
    )
    formula = next(
        item for item in snapshot.revision.formulas if item.target == "iva.compensacion-disponible-fin-periodo"
    )
    repo.save(
        RegistryModeloObservation(
            modelo="303",
            filing_year=filing_year,
            period=period,
            observations=(
                CasillaObservation(
                    casilla_id="iva.compensacion-disponible-fin-periodo",
                    value=amount,
                    formula_id=formula.id,
                    legal_refs=tuple(casilla.legal_refs),
                    source_refs=tuple(casilla.source_refs),
                ),
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_DECIDED_AT,
    )


def _work_unit_repositories():
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _store_operator_profile() -> None:
    UserProfileLifecycleRepository(bucket_id="operator").save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(UserProfileFact(path="identity.tax_id", value=_TAXPAYER_NIF),),
            created_at=_DECIDED_AT,
            updated_at=_DECIDED_AT,
        )
    )


def _modelo_303_engine_inputs() -> dict[str, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
    }


def test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_filing_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        loaded_decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, _TARGET_YEAR, _TARGET_PERIOD)
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
        assert filed_history_source.source_periods == ("1T",)

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
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
        )

        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("1200.00")
        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("1200.00")
        assert revision.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("1000.00")
        assert revision.casilla_values["iva.compensacion-pendiente-periodos-posteriores"] == Decimal("200.00")
        assert revision.casilla_values["iva.resultado"] == Decimal("0.00")
        assert revision.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("200.00")
        assert any(
            obs.casilla_id == "iva.compensacion-aplicada-periodo" and obs.legal_refs and obs.source_refs
            for obs in revision.observations
        )


def test_unpersisted_wallet_decision_cannot_feed_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
            persist=False,
        )
        assert IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, _TARGET_YEAR, _TARGET_PERIOD) is None

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="must be persisted"):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        assert len(calc_repo.load()) == 0


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
        snapshot = resources().modelos.authority.snapshot("303", filing_year=target_year, period=target_period)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(
                pending=Decimal("450.00"),
                target_year=target_year,
                target_period=target_period,
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

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=target_year,
            period=target_period,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("450.00")
        assert revision.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("450.00")
        assert revision.casilla_values["iva.resultado"] == Decimal("550.00")
        assert revision.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("0.00")


def test_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("800.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )
        assert report.decision.blocked is True
        assert report.decision.divergence == "wallet_higher"

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        assert len(calc_repo.load()) == 0


def test_persisted_blocked_wallet_decision_is_replayed_by_modelo_303_calculation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("800.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )
        assert report.decision.blocked is True

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        assert len(calc_repo.load()) == 0
