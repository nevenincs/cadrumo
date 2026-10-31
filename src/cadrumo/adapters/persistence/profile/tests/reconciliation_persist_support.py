"""Shared support: run a modelo reconciliation through prepare and persist in one call."""

from __future__ import annotations

from datetime import datetime

from .....application.modelo.reconciliation import (
    ModeloReconciliationCommand,
    ModeloReconciliationReport,
    prepare_modelo_reconcile,
    prepare_parsed_declaracion,
    prepare_parsed_justificante,
)
from .....application.modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from .....application.modelo.reconciliation_parsing import ReconciliationDeclaracionObservation
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.justificante.schema import Justificante
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.repository import upsert_work_unit
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..modelos_work_units import WorkUnitCatalogueRepository

__all__ = [
    "modelo_reconcile",
    "persist_work_unit",
    "reconcile_parsed_declaracion",
    "reconcile_parsed_justificante",
]


def persist_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    timestamp: datetime,
) -> str:
    """Save a work unit for the exact coordinates in the active profile and return its id."""
    typed_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=timestamp,
        updated_at=timestamp,
    )
    repository = WorkUnitCatalogueRepository()
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit_id


def modelo_reconcile(
    command: ModeloReconciliationCommand,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloReconciliationReport:
    """Reconcile a local evidence file and persist the outcome."""
    return prepare_modelo_reconcile(command, operation=operation).persist()


def reconcile_parsed_justificante(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    justificante: Justificante,
    operation: PinnedAuthorityOperation,
) -> ModeloReconciliationReport:
    """Reconcile parsed justificante evidence with the work unit and persist the outcome."""
    return prepare_parsed_justificante(
        work_unit=work_unit,
        source_kind=source_kind,
        source_ref=source_ref,
        actor=actor,
        justificante=justificante,
        operation=operation,
    ).persist()


def reconcile_parsed_declaracion(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    declaracion: ReconciliationDeclaracionObservation,
    operation: PinnedAuthorityOperation,
) -> ModeloReconciliationReport:
    """Reconcile parsed declaration evidence with the work unit and persist the outcome."""
    return prepare_parsed_declaracion(
        work_unit=work_unit,
        source_kind=source_kind,
        source_ref=source_ref,
        actor=actor,
        declaracion=declaracion,
        operation=operation,
    ).persist()
