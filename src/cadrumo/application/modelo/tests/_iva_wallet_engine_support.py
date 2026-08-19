"""Shared setup for Modelo 303 IVA wallet engine integration tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

from ....adapters.outbound.aeat.sede import IVA_COMPENSATION_WALLET_URL, parse_iva_compensation_wallet_html
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    RegistryModeloObservation,
    RegistrySnapshot,
)
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    FilingInstanceEvidence,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, IvaWalletDecisionRepository
from .. import create_work_unit

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_TAXPAYER_NIF = "12345678Z"
_TARGET_YEAR = 2026
_TARGET_PERIOD = "2T"
_DECIDED_AT = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")


def _period(filing_year: int, period: str) -> Period:
    return Period.from_year_and_code(filing_year, period)


_TARGET_PERIOD_VALUE = _period(_TARGET_YEAR, _TARGET_PERIOD)


def _filing_instance_evidence(period: Period) -> FilingInstanceEvidence:
    """Delegate to the one shared typed-evidence fixture builder."""
    return general_m303_filing_evidence(period, reference="test:iva-wallet:exonerado-390")


@cache
def _snapshot_303(*, filing_year: int = _TARGET_YEAR, period: str = _TARGET_PERIOD) -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)


@contextmanager
def _secure_backend(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


@cache
def _wallet_observation(
    *,
    pending: Decimal,
    taxpayer_nif: str = _TAXPAYER_NIF,
    target_year: int = _TARGET_YEAR,
    target_period: Period = _TARGET_PERIOD_VALUE,
    generation_year: int = 2026,
    generation_period: str = "1T",
    captured_at: datetime = _DECIDED_AT,
):
    pending_text = _spanish_amount(pending)
    return parse_iva_compensation_wallet_html(
        f"""
        <html><head><title>Cartera de cuotas de IVA a compensar</title></head>
          <body>
            <h1>Cartera de cuotas de IVA a compensar</h1>
            <li><strong>Cuotas a compensar pendientes de períodos anteriores:</strong>
              <span>{pending_text}</span></li>
            <table id="tablaResultados">
              <thead>
                <tr><th>Ejercicio</th><th>Período</th><th>Cuota Disponible</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td>{generation_year}</td><td>{generation_period}</td><td>{pending_text}</td>
                </tr>
              </tbody>
            </table>
          </body>
        </html>
        """,
        taxpayer_nif=taxpayer_nif,
        authenticated_identity=taxpayer_nif,
        target_year=target_year,
        target_period=target_period,
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=captured_at,
    )


def _spanish_amount(value: Decimal) -> str:
    whole, cents = f"{value:.2f}".split(".")
    chunks: list[str] = []
    while whole:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    return f"{'.'.join(reversed(chunks))},{cents}"


@cache
def _prior_303_compensation_observation(
    *,
    amount: Decimal,
    filing_year: int,
    period: str,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period=period,
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=filing_year,
            period=period,
            casilla_values={_M303_DISPONIBLE_CASILLA: amount},
        ),
    )


def _store_prior_303_compensation(
    repo: CalculationObservationRepository,
    *,
    amount: Decimal,
    filing_year: int = _TARGET_YEAR,
    period: str = "1T",
) -> None:
    repo.save(
        repo.prepare_observation_envelope(
            _prior_303_compensation_observation(
                amount=amount,
                filing_year=filing_year,
                period=period,
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_DECIDED_AT,
        )
    )


def _work_unit_repositories() -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]:
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _create_modelo_303_work_unit(
    snapshot: RegistrySnapshot,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    clock: datetime = _DECIDED_AT,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=snapshot.filing_year,
        period=_period(snapshot.filing_year, snapshot.period),
        revision_id=snapshot.revision.id,
        repository=work_unit_repository,
        clock=clock,
    )


def _work_unit_repositories_with_modelo_303_work_unit(
    snapshot: RegistrySnapshot,
    *,
    clock: datetime = _DECIDED_AT,
) -> tuple[
    WorkUnit,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]:
    work_repo, calc_repo, event_repo = _work_unit_repositories()
    work_unit = _create_modelo_303_work_unit(snapshot, work_unit_repository=work_repo, clock=clock)
    return work_unit, work_repo, calc_repo, event_repo


def _store_operator_profile() -> None:
    _store_operator_profile_with_tax_id(_TAXPAYER_NIF)


def _store_operator_profile_with_tax_id(tax_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=tax_id),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="censo.activity_start_date", value="2026-01-01"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="iva.regime", value=IVARegime.GENERAL),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="provenance.source", value=PROVENANCE_SOURCE_MANUAL_CLI),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
            created_at=_DECIDED_AT,
            updated_at=_DECIDED_AT,
        ),
    )


@cache
def _workflow_profile(tax_id: str = _TAXPAYER_NIF) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=tax_id,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _modelo_303_engine_inputs() -> dict[BindingId, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }


def _negative_modelo_303_engine_inputs() -> dict[BindingId, Decimal]:
    values = _modelo_303_engine_inputs()
    values["modelo-303-iva-repercutido-general-cuota"] = Decimal("0.00")
    values["modelo-303-iva-soportado-interiores-cuota"] = Decimal("1000.00")
    return values


def _work_unit_and_revision_for_wallet_gate(
    *,
    compensation_amount: Decimal,
    state: CalculationRevisionState = CalculationRevisionState.BORRADOR,
) -> tuple[WorkUnit, CalculationRevision]:
    target_period = _period(_TARGET_YEAR, _TARGET_PERIOD)
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_TARGET_YEAR,
        period=target_period,
        revision_id="m303-wallet-gate-test",
    )
    casilla_values: dict[CasillaId, Decimal] = {
        _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: compensation_amount,
    }
    filing_instance_evidence = general_m303_filing_evidence(target_period, reference="test:iva-wallet-engine")
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=_TARGET_YEAR,
        period=target_period,
        revision_id="m303-wallet-gate-test",
        name="303 wallet gate test",
        created_at=_DECIDED_AT,
        updated_at=_DECIDED_AT,
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD,
            casilla_values=casilla_values,
        ),
        created_at=_DECIDED_AT,
        updated_at=_DECIDED_AT,
        filing_instance_evidence=filing_instance_evidence,
    )
    return work_unit, revision


def _save_wallet_gate_decision(*, amount: Decimal, blocked: bool = False) -> None:
    IvaWalletDecisionRepository().save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif=_TAXPAYER_NIF,
            target_year=_TARGET_YEAR,
            target_period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            selected_authority="aeat_wallet" if not blocked else "missing",
            selected_amount=amount if not blocked else None,
            wallet_amount=amount,
            local_recurrence_amount=amount,
            override_amount=None,
            divergence="match" if not blocked else "filed_history_only",
            blocked=blocked,
            stale_wallet=False,
            reason_identity="aeat_wallet_validated",
            wallet_captured_at=_DECIDED_AT,
            decided_at=_DECIDED_AT,
        ),
    )
