"""Shared support: run a modelo reconciliation through prepare and persist in one call."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from .....application.modelo.reconciliation import (
    ModeloReconciliationCommand,
    ModeloReconciliationReport,
    prepare_modelo_reconcile,
    prepare_parsed_declaracion,
    prepare_parsed_justificante,
)
from .....application.modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from .....application.modelo.reconciliation_parsing import ReconciliationDeclaracionObservation
from .....application.workflow.persistence import workflow_state_repository
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import validated_casilla_id
from .....core.period import Period
from .....core.time.clock import now
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from .....domain.justificante.schema import Justificante
from .....domain.modelos.calculation_repository import upsert_calculation_revision
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.repository import upsert_work_unit
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....inbound.declaracion.schema import InboundDeclaracionObservation, TemplateRevision
from ....inbound.pdf.extracted_casilla import ExtractedCasilla
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository

__all__ = [
    "modelo_reconcile",
    "persist_filed_revision",
    "persist_work_unit",
    "reconcile_parsed_declaracion",
    "reconcile_parsed_justificante",
    "seed_active_work_unit",
    "synthetic_declaracion",
]


def _save_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    timestamp: datetime,
) -> WorkUnit:
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
    return work_unit


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
    return _save_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        timestamp=timestamp,
    ).work_unit_id


def seed_active_work_unit(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    operation: PinnedAuthorityOperation,
    snapshot_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> WorkUnit:
    """Save a work unit pinned to the law-determined revision for the active profile.

    The real revision id keeps the snapshot resolver's identity assertion true, so the
    reconcile compare runs instead of diverting into a snapshot-unavailable advisory.
    """
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = operation.snapshot(
        modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period).registry_token,
        grade=snapshot_grade,
    ).revision.id
    return _save_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        timestamp=datetime.now(UTC),
    )


def persist_filed_revision(
    work_unit: WorkUnit,
    *,
    casilla_values: dict[str, Decimal],
    clock: datetime,
) -> None:
    """Persist a PRESENTADO calculation revision carrying ``casilla_values`` for ``work_unit``."""
    validated_values = {validated_casilla_id(k, surface="test"): v for k, v in casilla_values.items()}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=validated_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(
        upsert_calculation_revision(
            repo.load(),
            CalculationRevision(
                calculation_revision_id=revision_id,
                work_unit_id=work_unit.work_unit_id,
                registry_snapshot_ref=RegistrySnapshotRef(
                    modelo=work_unit.modelo,
                    revision_id=work_unit.revision_id,
                    modelo_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                ),
                state=CalculationRevisionState.PRESENTADO,
                casilla_values=validated_values,
                observations=registry_grounded_observations(
                    modelo=str(work_unit.modelo),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    casilla_values=validated_values,
                ),
                created_at=clock,
                updated_at=clock,
                verified_at=clock,
                verified_by="test",
                filed_at=clock,
                filed_by="test",
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        ),
    )


def synthetic_declaracion(
    work_unit: WorkUnit,
    *,
    values: dict[str, Decimal],
    operation: PinnedAuthorityOperation,
    tax_id: str,
    modelo: str | None = None,
    ejercicio: str | None = None,
    period: Period | None = None,
    extraction_profile_provisional: bool = False,
    snapshot_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> InboundDeclaracionObservation:
    """Build an in-memory declaración observation for the work unit's modelo.

    Bypasses PDF extraction (declared ``synthetic_generated`` provenance) and carries a
    registry snapshot ref matching the seeded work unit's law-determined revision.
    """
    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        grade=snapshot_grade,
    )
    return InboundDeclaracionObservation(
        modelo=modelo or str(work_unit.modelo),
        ejercicio=ejercicio or str(work_unit.filing_year),
        period=period or work_unit.period,
        tax_id=tax_id,
        template_revision=TemplateRevision(
            modelo=str(work_unit.modelo),
            año=work_unit.filing_year,
            revision=snapshot.revision.id,
            detected_from="explicit_override",
        ),
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            modelo_year=snapshot.filing_year,
            period=snapshot.period,
        ),
        values=tuple(
            ExtractedCasilla(
                casilla_id=validated_casilla_id(casilla_id, surface="test"),
                printed_value=value,
                source_page=1,
                source_bbox=None,
                extraction_confidence=1.0,
            )
            for casilla_id, value in values.items()
        ),
        warnings=(),
        extraction_profile_id=f"modelo-{modelo or str(work_unit.modelo)}-declaracion-pdf",
        extraction_profile_provisional=extraction_profile_provisional,
        source_pdf_path=Path(f"synthetic/declaracion-{work_unit.modelo}.pdf"),
        source_pdf_sha256="0" * 64,
        parsed_at=now(),
    )


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
