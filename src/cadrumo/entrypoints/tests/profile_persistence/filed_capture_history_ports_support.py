"""Filed-observation capability bundle shared by the filed capture history tests."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

from cadrumo.adapters.outbound.aeat.sede.filed_observation_persistence import (
    BucketEventRepositoryAdapter,
    CalculationObservationRepositoryAdapter,
    FiledDeclarationTransformationAdapter,
    FiledObservationParserAdapter,
    FiledObservationStoreAdapter,
    FilingReconciliationAdapter,
    FilingRepositoryAdapter,
    IvaHistoryRepositoryAdapter,
    IvaObservationPersistenceAdapter,
    JustificanteRepositoryAdapter,
)
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.application.live.filed_observation_ports import FiledObservationPersistencePorts
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

SESSION_BUCKET_ID = "45454545-4545-4454-8454-454545454545"
FILED_OPERATION_STACK = ExitStack()


def filed_ports(
    *,
    bucket_id: str,
    root: Path,
    calculation_repository: CalculationObservationRepository | None = None,
) -> FiledObservationPersistencePorts:
    """Compose the canonical filed-observation capability bundle for a test."""
    # The observation envelope and its IVA history co-commit in one backend
    # transaction, so every repository here must share the caller's backend.
    objects = (
        calculation_repository.secure_object_repository
        if calculation_repository is not None
        else secure_object_repository_for_bucket(bucket_id)
    )
    operation = FILED_OPERATION_STACK.enter_context(bundled_indexed_authority().operation())
    work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects)
    filing = ModeloRecordCatalogueRepository(bucket_id=bucket_id, objects=objects)
    justificantes = JustificanteRepository(objects=objects)
    events = BucketEventHistoryRepository(objects=objects)
    observations = calculation_repository or CalculationObservationRepository(bucket_id=bucket_id, objects=objects)
    history = IvaCompensationHistoryRepository(bucket_id=bucket_id, objects=objects)
    return FiledObservationPersistencePorts(
        parser=FiledObservationParserAdapter(),
        transformation=FiledDeclarationTransformationAdapter(operation=operation),
        observation_persistence=FiledObservationStoreAdapter(root=root, objects=objects),
        calculation_repository=CalculationObservationRepositoryAdapter(repository=observations),
        iva_history_repository=IvaHistoryRepositoryAdapter(repository=history),
        iva_observation_persistence=IvaObservationPersistenceAdapter(),
        justificante_repository=JustificanteRepositoryAdapter(repository=justificantes),
        filing_repository=FilingRepositoryAdapter(repository=filing),
        bucket_event_repository=BucketEventRepositoryAdapter(repository=events),
        filing_reconciliation=FilingReconciliationAdapter(
            work_lifecycle_ports=WorkLifecyclePorts(
                work_unit_repository=work_units,
                bucket_event_repository=events,
            ),
            calculation_repository=CalculationRevisionCatalogueRepository(bucket_id=bucket_id, objects=objects),
            filing_repository=filing,
            justificante_repository=justificantes,
            observation_repository=observations,
        ),
    )
