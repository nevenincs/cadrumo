"""Backend integration for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.outbound.aeat.sede import parse_iva_compensation_wallet_html
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from aeat.application.calculations import (
    CalculationObservationRepository,
    reconcile_modelo_303_iva_compensation,
)
from aeat.application.modelo import (
    ModeloIvaWalletReconciliationBlocked,
    calculate_modelo_revision,
    create_work_unit,
)
from aeat.core.config import override_settings
from aeat.core.resources import resources
from aeat.domain.buckets import BucketEventHistoryRepository
from aeat.domain.calculations.registry import CasillaObservation, RegistryFilingObservation
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository

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


def _wallet_observation(*, pending: Decimal):
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
                  <td>2026</td><td>1T</td><td>{pending_text}</td><td>0,00</td><td>{pending_text}</td>
                </tr>
              </tbody>
            </table>
          </body>
        </html>
        """,
        taxpayer_nif=_TAXPAYER_NIF,
        authenticated_identity=_TAXPAYER_NIF,
        target_year=_TARGET_YEAR,
        target_period=_TARGET_PERIOD,
        source_url="https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas",
        captured_at=_DECIDED_AT,
    )


def _spanish_amount(value: Decimal) -> str:
    whole, cents = f"{value:.2f}".split(".")
    chunks: list[str] = []
    while whole:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    return f"{'.'.join(reversed(chunks))},{cents}"


def _store_prior_303_compensation(repo: CalculationObservationRepository, *, amount: Decimal) -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period="1T")
    casilla = next(
        item for item in snapshot.revision.casillas if item.id == "iva.compensacion-disponible-fin-periodo"
    )
    formula = next(
        item for item in snapshot.revision.formulas if item.target == "iva.compensacion-disponible-fin-periodo"
    )
    repo.save(
        RegistryFilingObservation(
            modelo="303",
            filing_year=_TARGET_YEAR,
            period="1T",
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

        loaded_decision = observation_repo.load_iva_wallet_decision(_TAXPAYER_NIF, _TARGET_YEAR, _TARGET_PERIOD)
        assert loaded_decision == report.decision
        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.local_recurrence_amount == Decimal("1200.00")

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


def test_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
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
