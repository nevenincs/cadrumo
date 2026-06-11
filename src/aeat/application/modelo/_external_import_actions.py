"""External filing import actions for modelo baselines.

Use of :class:`BucketEventHistoryRepository`, :class:`CalculationRevision`, :class:`ModeloRecord` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepository, BucketEventObjectType, BucketEventType
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.justificante import JustificanteRepository
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository, upsert_filing_record
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ...domain.modelos._work_unit import WorkUnitState
from ._action_errors import ExternalModeloImportError, WorkUnitMutationRefusedError, WorkUnitNotFoundError
from ._calculation_helpers import external_filing_observations as _external_filing_observations
from ._registry_helpers import reject_unknown_import_casillas as _reject_unknown_import_casillas
from ._revision_persistence import emit_bucket_event as _emit_bucket_event

_JUSTIFICANTE_BOUND_EVIDENCE_KINDS = frozenset(
    {
        ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    },
)


def _load_external_import_target(
    *,
    work_unit_id: str,
    casilla_values: Mapping[str, Decimal],
    evidence_reference_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
):
    cleaned_reference = _validated_external_reference(casilla_values, evidence_reference_id)

    work_units = work_unit_repository.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_discarded_cannot_import",
            context={"work_unit_id": work_unit_id},
        )
    snapshot = _reject_unknown_import_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_values=casilla_values,
    )
    return work_units, work_unit, snapshot, cleaned_reference


def import_external_filing_evidence(
    *,
    work_unit_id: str,
    casilla_values: Mapping[str, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    justificante_repository: JustificanteRepository | None = None,
    expected_tax_id: str | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Persist an externally-filed return and return a :class:`ModeloRecord`."""
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    work_units, work_unit, snapshot, cleaned_reference = _load_external_import_target(
        work_unit_id=work_unit_id,
        casilla_values=casilla_values,
        evidence_reference_id=evidence_reference_id,
        work_unit_repository=wu_repo,
    )
    _require_bound_justificante_artifact(
        evidence_kind=evidence_kind,
        evidence_reference_id=cleaned_reference,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        expected_tax_id=expected_tax_id,
        justificante_repository=justificante_repository or JustificanteRepository(),
    )

    inputs_snapshot: dict[str, str] = {}
    binding_overrides: dict[str, str] = {}
    outputs = dict(casilla_values)
    observations = _external_filing_observations(casilla_values=outputs, snapshot=snapshot)

    now = clock or _utc_now()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
    )
    revisions = cr_repo.load()
    if revision_id in revisions:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_duplicate_revision",
            context={"calculation_revision_id": revision_id},
        )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
        observations=observations,
    )
    revisions = upsert_calculation_revision(revisions, revision)

    new_filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=cleaned_reference,
            imported_at=now,
        ),
    )

    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            },
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                    "superseded_at": now,
                    "updated_at": now,
                },
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "filed_calculation_revision_id": revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                },
            ),
        ),
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_FILING_IMPORTED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "work_unit_id": work_unit_id,
            "calculation_revision_id": revision_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "evidence_kind": evidence_kind.value,
            "evidence_reference_id": cleaned_reference,
            "supersedes_filing_record_id": (prior_current.filing_record_id if prior_current is not None else ""),
            "casilla_count": str(len(outputs)),
        },
    )

    return new_filing


def _validated_external_reference(
    casilla_values: Mapping[str, Decimal],
    evidence_reference_id: str,
) -> str:
    if not casilla_values:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )
    cleaned_reference = evidence_reference_id.strip()
    if not cleaned_reference:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_evidence_reference_blank",
        )
    return cleaned_reference


def _require_bound_justificante_artifact(
    *,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    expected_tax_id: str | None,
    justificante_repository: JustificanteRepository,
) -> None:
    if evidence_kind not in _JUSTIFICANTE_BOUND_EVIDENCE_KINDS:
        return
    cleaned_expected_tax_id = (expected_tax_id or "").strip()
    if not cleaned_expected_tax_id:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_tax_id_missing",
            context={
                "evidence_reference_id": evidence_reference_id,
                "evidence_kind": evidence_kind.value,
            },
        )
    justificante = justificante_repository.load(evidence_reference_id)
    if justificante is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_justificante_missing",
            context={
                "evidence_reference_id": evidence_reference_id,
                "evidence_kind": evidence_kind.value,
            },
        )
    if not _justificante_matches_import_target(
        justificante,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        expected_tax_id=cleaned_expected_tax_id,
    ):
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_justificante_mismatch",
            context={
                "evidence_reference_id": evidence_reference_id,
                "modelo": modelo,
                "filing_year": str(filing_year),
                "period": period,
            },
        )


def _justificante_matches_import_target(
    justificante: object,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    expected_tax_id: str,
) -> bool:
    return (
        str(getattr(justificante, "modelo", "")).strip() == modelo
        and str(getattr(justificante, "ejercicio", "") or "").strip() == str(filing_year)
        and str(getattr(justificante, "period", "")).strip().upper() == period.strip().upper()
        and str(getattr(justificante, "tax_id", "") or "").strip() == expected_tax_id
    )
