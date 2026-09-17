"""Concrete Modelo-export port composition for persistence adapter tests.

The application export service receives a complete, application-owned port
bundle.  These tests exercise encrypted profile persistence, so their outer
fixture composes the real repositories against the isolated bucket storage.
Application-layer tests should provide inward fakes instead of importing this
adapter-owned support module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from cadrumo.adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_bucket,
    secure_object_repository_for_cold_bootstrap_state,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from cadrumo.application.calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from cadrumo.application.filing.draft_review_ports import DraftReviewPorts
from cadrumo.application.modelo.export_ports import ModeloExportPorts
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from cadrumo.domain.justificante.protocols import JustificanteRepositoryProtocol
from cadrumo.domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from cadrumo.domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from cadrumo.domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from cadrumo.domain.transactions.protocols import TransactionCatalogueRepositoryProtocol

_EMPTY_EXPORT_BUCKET_ID = "ephemeral"


class _ProfileActivityReader:
    """Read the active profile projection through the encrypted workflow state."""

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        """Return path values only when workflow state names the requested bucket."""
        record = workflow_state_repository().load().active_profile_record()
        if record is None or str(record.profile_id) != bucket_id:
            return None
        return record_to_path_values(record)


def _draft_review_ports_for_test(*, bucket_id: str, objects: SecureObjectRepository) -> DraftReviewPorts:
    """Compose the concrete draft-review authorities over one secure store."""
    return DraftReviewPorts(
        transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=bucket_id, objects=objects),
        observation_repository=CalculationObservationRepository(objects=objects),
        profile_repository=_ProfileActivityReader(),
        draft_repository=ModeloDraftRepository(bucket_id=bucket_id, objects=objects),
    )


def _compose_modelo_export_ports(
    *,
    bucket_id: str,
    taxpayer_tax_id: str,
    objects: SecureObjectRepository,
) -> ModeloExportPorts:
    """Compose every concrete export and draft-review authority over one store."""
    return ModeloExportPorts(
        calculation=CalculationRevisionCatalogueRepository(
            bucket_id=bucket_id,
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
        ),
        work_unit=WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects),
        filing=ModeloRecordCatalogueRepository(bucket_id=bucket_id, objects=objects),
        verification=VerificationReportCatalogueRepository(
            bucket_id=bucket_id,
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
        ),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
        prorrata_register=ProrrataRegisterRepository(bucket_id=bucket_id, objects=objects),
        bienes_inversion=BienesInversionIvaRegisterRepository(bucket_id=bucket_id, objects=objects),
        transaction=TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        draft_review_ports=_draft_review_ports_for_test(bucket_id=bucket_id, objects=objects),
    )


def empty_modelo_export_ports_for_test() -> ModeloExportPorts:
    """Return a complete encrypted bundle for a gate tested before any read."""
    return _compose_modelo_export_ports(
        bucket_id=_EMPTY_EXPORT_BUCKET_ID,
        taxpayer_tax_id="12345678Z",
        objects=secure_object_repository_for_cold_bootstrap_state(),
    )


def modelo_export_ports_for_test(
    *,
    bucket_id: str | None = None,
    taxpayer_tax_id: str = "12345678Z",
    secure_objects: SecureObjectRepository | None = None,
    calculation: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    work_unit: WorkUnitCatalogueRepositoryProtocol | None = None,
    filing: ModeloRecordCatalogueRepositoryProtocol | None = None,
    verification: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event: BucketEventHistoryRepositoryProtocol | None = None,
    observation: CalculationObservationRepositoryProtocol | None = None,
    iva_compensation_decision: IvaWalletDecisionRepositoryProtocol | None = None,
    justificante: JustificanteRepositoryProtocol | None = None,
    prorrata_register: ProrrataRegisterRepositoryProtocol | None = None,
    bienes_inversion: BienesInversionIvaRegisterRepositoryProtocol | None = None,
    transaction: TransactionCatalogueRepositoryProtocol | None = None,
) -> ModeloExportPorts:
    """Compose real bucket-bound repositories, allowing focused authority overrides."""
    if bucket_id is None:
        target_bucket_id = workflow_state_repository().load().active_profile_bucket_id()
        if target_bucket_id is None:
            raise RuntimeError("an active or explicit bucket is required for concrete export ports")
    else:
        target_bucket_id = bucket_id
    objects = secure_object_repository_for_bucket(target_bucket_id) if secure_objects is None else secure_objects
    composed = _compose_modelo_export_ports(
        bucket_id=target_bucket_id,
        taxpayer_tax_id=taxpayer_tax_id,
        objects=objects,
    )
    return replace(
        composed,
        calculation=calculation if calculation is not None else composed.calculation,
        work_unit=work_unit if work_unit is not None else composed.work_unit,
        filing=filing if filing is not None else composed.filing,
        verification=verification if verification is not None else composed.verification,
        bucket_event=bucket_event if bucket_event is not None else composed.bucket_event,
        observation=observation if observation is not None else composed.observation,
        iva_compensation_decision=(
            iva_compensation_decision if iva_compensation_decision is not None else composed.iva_compensation_decision
        ),
        justificante=justificante if justificante is not None else composed.justificante,
        prorrata_register=prorrata_register if prorrata_register is not None else composed.prorrata_register,
        bienes_inversion=bienes_inversion if bienes_inversion is not None else composed.bienes_inversion,
        transaction=transaction if transaction is not None else composed.transaction,
    )


__all__ = ["empty_modelo_export_ports_for_test", "modelo_export_ports_for_test"]
