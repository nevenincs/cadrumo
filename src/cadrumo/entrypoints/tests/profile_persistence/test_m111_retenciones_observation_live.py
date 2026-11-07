"""M111 retenciones observations feed the live bucket calculation path."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import WITHHOLDING_PAYER_PERSONA, seed_persona_profile
from ....adapters.persistence.profile.tests.retencion_observation_authoring import replace_retencion_observations
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.aggregation.retenciones import RetencionObservation
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.aggregation import (
    AggregationCaptureKind,
    BindingSourceKind,
    RetencionScheme,
)
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "00000000-0000-4000-8000-000000000111"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)


def _professional_observation() -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="professional-payment-001",
        perceptor_nif="12345678Z",
        perceptor_name="Profesional Ejemplo",
        scheme=RetencionScheme("actividades_profesionales"),
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2026-03-15",
    )


def _administrador_observation() -> RetencionObservation:
    """An administrador/consejero retención at the LIRPF art. 101.2 fixed rate (35 %)."""
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="administrador-payment-001",
        perceptor_nif="X0001502F",
        perceptor_name="Administrador Ejemplo",
        scheme=RetencionScheme("rendimientos_trabajo_administrador"),
        taxable_base=Decimal("2000.00"),
        retencion_amount=Decimal("700.00"),  # 2000.00 * 0.35 (art. 101.2 general rate)
        accrued_on="2026-03-15",
    )


def _administrador_wrong_rate_observation() -> RetencionObservation:
    """An administrador retención withheld at 25 % — neither the 35 % nor the 19 % art. 101.2 rate."""
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="administrador-payment-002",
        perceptor_nif="X0001502F",
        perceptor_name="Administrador Ejemplo",
        scheme=RetencionScheme("rendimientos_trabajo_administrador"),
        taxable_base=Decimal("2000.00"),
        retencion_amount=Decimal("500.00"),  # 25 % — matches no art. 101.2 fixed rate
        accrued_on="2026-03-15",
    )


def _calculate_with_observation(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, observation: RetencionObservation
) -> BucketAggregationCalculationResult:
    """Persist one retención observation for 1T 2026, create the Modelo 111 work unit and calculate it."""
    period = Period.from_year_and_code(2026, "1T")
    replace_retencion_observations(
        RetencionObservationRepositoryAdapter(objects=objects),
        modelo="111",
        filing_year=2026,
        period=period,
        observations=[observation],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    snapshot = published_authority_operation().snapshot("111", filing_year=2026, period="1T")
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="111",
        filing_year=2026,
        period=period,
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        invoice_repository=InvoiceCatalogueRepository(objects=objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        work_unit_repository=wu_repo,
    ) as calculation_ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=calculation_ports,
            clock=_T1,
        )


def test_m111_professional_retencion_observation_calculates_activity_boxes(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A persisted professional retención observation drives 07/08/09 and totals 28/30."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 retenciones") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_persona_profile(WITHHOLDING_PAYER_PERSONA, bucket_id=_BUCKET_ID, at=_T0)
        result = _calculate_with_observation(objects, operation, _professional_observation())

    values = result.revision.casilla_values
    assert values["07"] == Decimal("1")
    assert values["08"] == Decimal("1000.00")
    assert values["09"] == Decimal("150.00")
    assert values["28"] == Decimal("150.00")
    assert values["30"] == Decimal("150.00")
    assert result.source_diagnostics == ()


def test_m111_administrador_retencion_observation_folds_into_trabajo_boxes(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An administrador (clave E, art. 101.2) retención drives the trabajo boxes 01/02/03 and totals 28/30.

    Modelo 111 carries a single rendimientos-del-trabajo block, so the administrador/consejero
    retención reports there alongside ordinary empleados (the clave A/E split is only on Modelo
    190). The 700.00 withheld is the art. 101.2 fixed 35 % of the 2.000,00 base.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 retenciones") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_persona_profile(WITHHOLDING_PAYER_PERSONA, bucket_id=_BUCKET_ID, at=_T0)
        result = _calculate_with_observation(objects, operation, _administrador_observation())

    values = result.revision.casilla_values
    assert values["01"] == Decimal("1")
    assert values["02"] == Decimal("2000.00")
    assert values["03"] == Decimal("700.00")
    assert values["28"] == Decimal("700.00")
    assert values["30"] == Decimal("700.00")
    assert result.source_diagnostics == ()


def test_m111_administrador_wrong_rate_surfaces_calculate_advisory(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An administrador retención at a non-art.-101.2 rate surfaces a non-blocking calculate advisory.

    The withheld 500.00 on a 2.000,00 base is 25 %, which matches neither the fixed 35 %
    general rate nor the 19 % reduced rate of LIRPF art. 101.2. The trabajo boxes still fold
    the operator-supplied amounts (the advisory never overrides values), but the engine surfaces
    an ``administrador_retencion_rate_mismatch`` diagnostic so the operator can confirm the rate
    before filing (``no-silent-under-declaration``).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 retenciones") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_persona_profile(WITHHOLDING_PAYER_PERSONA, bucket_id=_BUCKET_ID, at=_T0)
        result = _calculate_with_observation(objects, operation, _administrador_wrong_rate_observation())

    values = result.revision.casilla_values
    assert values["02"] == Decimal("2000.00")
    assert values["03"] == Decimal("500.00")
    mismatch = [d for d in result.source_diagnostics if d.reason == "administrador_retencion_rate_mismatch"]
    assert len(mismatch) == 1
    assert "X0001502F" in mismatch[0].message
