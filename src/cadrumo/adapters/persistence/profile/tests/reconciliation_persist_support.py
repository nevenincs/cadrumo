"""Shared support: run a modelo reconciliation through prepare and persist in one call."""

from __future__ import annotations

from .....application.modelo.reconciliation import (
    ModeloReconciliationCommand,
    ModeloReconciliationReport,
    prepare_modelo_reconcile,
    prepare_parsed_declaracion,
    prepare_parsed_justificante,
)
from .....application.modelo.reconciliation_parsing import ReconciliationDeclaracionObservation
from .....application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.justificante.schema import Justificante
from .....domain.modelos.work_unit import WorkUnit

__all__ = [
    "modelo_reconcile",
    "reconcile_parsed_declaracion",
    "reconcile_parsed_justificante",
]


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
