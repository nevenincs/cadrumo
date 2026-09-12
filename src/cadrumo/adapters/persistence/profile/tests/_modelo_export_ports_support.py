"""Concrete Modelo-export port composition for persistence adapter tests.

The application export service receives a complete, application-owned port
bundle.  These tests exercise encrypted profile persistence, so their outer
fixture composes the real repositories against the isolated bucket storage.
Application-layer tests should provide inward fakes instead of importing this
adapter-owned support module.
"""

from __future__ import annotations

from dataclasses import replace

from cadrumo.adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository, IvaWalletDecisionRepository
from cadrumo.application.modelo.export_ports import ModeloExportPorts
from cadrumo.application.workflow.persistence import workflow_state_repository


class _UnavailableExportAuthority:
    """Inert inward fake for tests whose assertion stops before any repository read."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"export authority {name!r} must not be read in this test")


def empty_modelo_export_ports_for_test() -> ModeloExportPorts:
    """Return an inert bundle for an export gate tested before authority access."""
    authority = _UnavailableExportAuthority()
    return ModeloExportPorts(
        calculation=authority,
        work_unit=authority,
        filing=authority,
        verification=authority,
        bucket_event=authority,
        observation=authority,
        iva_compensation_decision=authority,
        justificante=authority,
        prorrata_register=authority,
        bienes_inversion=authority,
        transaction=authority,
    )


def modelo_export_ports_for_test(
    *,
    bucket_id: str | None = None,
    taxpayer_tax_id: str = "12345678Z",
    secure_objects: object | None = None,
    calculation: object | None = None,
    work_unit: object | None = None,
    filing: object | None = None,
    verification: object | None = None,
    bucket_event: object | None = None,
    observation: object | None = None,
    iva_compensation_decision: object | None = None,
    justificante: object | None = None,
    prorrata_register: object | None = None,
    bienes_inversion: object | None = None,
    transaction: object | None = None,
) -> ModeloExportPorts:
    """Compose real bucket-bound repositories, allowing focused authority overrides."""
    target_bucket_id = bucket_id or workflow_state_repository().load().active_profile_bucket_id()
    if target_bucket_id is None:
        raise RuntimeError("an active or explicit bucket is required for concrete export ports")
    objects = secure_objects or secure_object_repository_for_bucket(target_bucket_id)
    composed = ModeloExportPorts(
        calculation=CalculationRevisionCatalogueRepository(
            bucket_id=target_bucket_id,
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
        ),
        work_unit=WorkUnitCatalogueRepository(bucket_id=target_bucket_id, objects=objects),
        filing=ModeloRecordCatalogueRepository(bucket_id=target_bucket_id, objects=objects),
        verification=VerificationReportCatalogueRepository(bucket_id=target_bucket_id, objects=objects),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
        prorrata_register=ProrrataRegisterRepository(bucket_id=target_bucket_id, objects=objects),
        bienes_inversion=BienesInversionIvaRegisterRepository(bucket_id=target_bucket_id, objects=objects),
        transaction=TransactionCatalogueRepository(bucket_id=target_bucket_id, objects=objects),
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
            iva_compensation_decision
            if iva_compensation_decision is not None
            else composed.iva_compensation_decision
        ),
        justificante=justificante if justificante is not None else composed.justificante,
        prorrata_register=prorrata_register if prorrata_register is not None else composed.prorrata_register,
        bienes_inversion=bienes_inversion if bienes_inversion is not None else composed.bienes_inversion,
        transaction=transaction if transaction is not None else composed.transaction,
    )


__all__ = ["empty_modelo_export_ports_for_test", "modelo_export_ports_for_test"]
