"""Outer test composition for the modelo verification repository capability.

Application tests exercise the use case through its application-owned bundle
port.  The concrete encrypted repositories are assembled here, alongside the
other storage-runtime test composition helpers, so application test modules do
not add adapter imports merely to satisfy verification's required dependency.
"""

from __future__ import annotations

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import (    secure_object_repository_for_active_bucket,
)
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository, IvaWalletDecisionRepository
from cadrumo.application.modelo.verification_repository_ports import VerificationRepositoryBundle
from cadrumo.application.workflow.persistence import WorkflowRunRepository
from cadrumo.core.bucket_pointer import resolve_active_bucket_id

def build_test_verification_repository_bundle() -> VerificationRepositoryBundle:
    """Compose the real adapter bundle over the active isolated test bucket."""
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise AssertionError("verification tests require an active profile bucket")
    objects = secure_object_repository_for_active_bucket()
    return VerificationRepositoryBundle(
        calculation=CalculationRevisionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        work_unit=WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects),
        filing=ModeloRecordCatalogueRepository(bucket_id=bucket_id, objects=objects),
        transaction=TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        verification=VerificationReportCatalogueRepository(bucket_id=bucket_id, objects=objects),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects),
        participation_index=TransactionParticipationIndexRepository(bucket_id=bucket_id, objects=objects),
        workflow_run=WorkflowRunRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
    )


def build_test_certificate_secret_backend_factory() -> InMemoryCertificateSecretBackendFactory:
    """Compose the application certificate-secret fake for one test call."""
    return InMemoryCertificateSecretBackendFactory()


__all__ = [
    "build_test_certificate_secret_backend_factory",
    "build_test_verification_repository_bundle",
]
