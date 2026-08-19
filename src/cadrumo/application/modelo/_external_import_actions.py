"""External filing import actions for modelo baselines.

:func:`~cadrumo.application.modelo.import_external_filing_evidence` turns
AEAT-attested external evidence into a presented
:class:`CalculationRevision` plus current
:class:`ModeloRecord`. Evidence-bearing imports validate the
referenced :class:`Justificante`, stamp an
:class:`ExternalEvidence` payload on the filing record,
supersede any prior current filing for the same target, and emit
``modelo.filing.imported`` through
:class:`BucketEventHistoryRepository`.

The imported record is the production baseline consumed by the amendment path.
It is intentionally distinct from a locally calculated and filed return:
``external_evidence`` marks that the values came from official AEAT evidence,
while
:func:`~cadrumo.application.modelo._calculation_helpers.external_filing_observations`
keeps the imported casilla values on the same registry-grounded
:class:`CasillaObservation` contract as local
calculation revisions.

See Also:
    :func:`~cadrumo.entrypoints.cli._modelo_records_cli.filing_record_import`:
        CLI surface that parses ``filing-record import`` options and calls this
        service.
    :func:`~cadrumo.application.modelo.amend_modelo_revision`:
        Consumes the imported current :class:`ModeloRecord`
        as an amendment baseline.
    :mod:`~cadrumo.domain.justificante`:
        Receipt metadata store required by justificante-PDF, CSV-register, and
        live-capture evidence kinds.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_unknown_import_casillas`:
        Resolves the registry snapshot and refuses noncanonical or undeclared
        imported casilla ids.
    :class:`ExternalEvidence`:
        Filing-record metadata that records the official evidence source.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import CasillaId, Modelo, Period
from ...core.identity import CalculationRevisionId
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepositoryProtocol, BucketEventObjectType, BucketEventType
from ...domain.calculations.registry import BindingId, RelationId
from ...domain.justificante import Justificante
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    WorkUnit,
    WorkUnitCatalogueRepositoryProtocol,
    derive_calculation_revision_id,
    derive_filing_record_id,
    upsert_calculation_revision,
    upsert_filing_record,
    upsert_work_unit,
)
from ._action_errors import ExternalModeloImportError
from ._calculation_helpers import external_filing_observations as _external_filing_observations
from ._registry_helpers import reject_unknown_import_casillas as _reject_unknown_import_casillas
from ._revision_persistence import build_modelo_bucket_event as _build_bucket_event
from ._revision_persistence import modelo_bucket_event_write as _bucket_event_write
from ._revision_persistence import supersede_prior_current_filing as _supersede_prior_current_filing
from ._work_lifecycle import ActiveWorkUnitUse, require_active_work_unit

_JUSTIFICANTE_BOUND_EVIDENCE_KINDS = frozenset(
    {
        ExternalEvidenceKind.AEAT_CSV_REGISTER,
        ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    },
)


def _load_external_import_target[CasillaKey](
    *,
    work_unit_id: str,
    casilla_values: Mapping[CasillaKey, Decimal],
    evidence_reference_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
):
    cleaned_reference = _validated_external_reference(casilla_values, evidence_reference_id)

    work_units = work_unit_repository.load()
    work_unit = require_active_work_unit(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=work_unit_repository.bucket_id,
        use=ActiveWorkUnitUse.IMPORT,
    )
    snapshot, canonical_values = _reject_unknown_import_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_values=casilla_values,
    )
    return work_units, work_unit, snapshot, canonical_values, cleaned_reference


def import_external_filing_evidence[CasillaKey](
    *,
    work_unit_id: str,
    casilla_values: Mapping[CasillaKey, Decimal],
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
    """Persist an externally-filed return and return its current :class:`ModeloRecord`.

    The target :class:`WorkUnit` supplies the bucket,
    modelo, filing year, period, and registry revision used to validate imported
    casilla ids. Justificante-bound evidence kinds require a stored
    :class:`Justificante` whose modelo, year, period,
    and taxpayer id match the target.

    The service writes a ``PRESENTADO``
    :class:`CalculationRevision` containing the imported
    values and registry-grounded observations, creates a ``VIGENTE`` filing
    record with :class:`ExternalEvidence`, supersedes any
    previous current filing for the same target, advances the work-unit pointers,
    and emits ``modelo.filing.imported``.

    Returns:
        The new current :class:`ModeloRecord` carrying the
        external evidence metadata.

    See Also:
        :func:`~cadrumo.application.modelo._calculation_helpers.external_filing_observations`:
            Builds provenance-bearing observations for imported casilla values.
        :func:`~cadrumo.application.modelo.amend_modelo_revision`:
            Requires this external-evidence baseline before filing amendments.
        :mod:`~cadrumo.domain.justificante`:
            Stores the receipt metadata checked for receipt-bound evidence
            references.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    work_units, work_unit, snapshot, canonical_values, cleaned_reference = _load_external_import_target(
        work_unit_id=work_unit_id,
        casilla_values=casilla_values,
        evidence_reference_id=evidence_reference_id,
        work_unit_repository=wu_repo,
    )
    if work_unit.modelo == Modelo.M303.value:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_m303_filing_evidence_required",
            context={"work_unit_id": work_unit.work_unit_id},
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

    input_values_by_casilla_id: dict[CasillaId, str] = {}
    binding_overrides: dict[BindingId, str] = {}
    relation_overrides: dict[RelationId, str] = {}
    outputs = dict(canonical_values)
    observations = _external_filing_observations(casilla_values=outputs, snapshot=snapshot)

    now = clock or _utc_now()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=outputs,
        filing_instance_evidence=None,
        m303_regimen_simplificado_annual_summary_handoff=None,
    )
    # Revisioned: both catalogues are composed into the co-commit below, so
    # neither can use a self-committing mutation, and an unguarded read would
    # write the whole singleton row back over a concurrent writer's entry.
    revisions, revisions_revision_id = cr_repo.load_revisioned()
    if revision_id in revisions:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_duplicate_revision",
            context={"calculation_revision_id": revision_id},
        )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
        observations=observations,
        filing_instance_evidence=None,
        m303_regimen_simplificado_annual_summary_handoff=None,
    )
    revisions = upsert_calculation_revision(revisions, revision)

    new_filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by=actor.strip(),
    )

    filing_catalogue, filing_revision_id = fr_repo.load_revisioned()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = _build_external_filing_record(
        filing_record_id=new_filing_id,
        work_unit=work_unit,
        calculation_revision_id=revision_id,
        filed_at=now,
        filed_by=actor.strip(),
        evidence_kind=evidence_kind,
        evidence_reference_id=cleaned_reference,
    )

    updated_filing_catalogue, revisions = _supersede_prior_current_external_filing(
        filing_catalogue=filing_catalogue,
        prior_current=prior_current,
        revisions=revisions,
        new_filing_id=new_filing_id,
        now=now,
    )
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    advanced_work_units = upsert_work_unit(
        work_units,
        work_unit.model_copy(
            update={
                "current_calculation_revision_id": revision_id,
                "filed_calculation_revision_id": revision_id,
                "current_filing_record_id": new_filing_id,
                "updated_at": now,
            },
        ),
    )
    imported_event = _build_bucket_event(
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
            "period": work_unit.period.registry_token,
            "evidence_kind": evidence_kind.value,
            "evidence_reference_id": cleaned_reference,
            "supersedes_filing_record_id": (prior_current.filing_record_id if prior_current is not None else ""),
            "casilla_count": str(len(outputs)),
        },
    )

    # One unit of work: the imported revision, the filing catalogue, the advanced
    # work-unit pointers, and the ``modelo.filing.imported`` event commit
    # together. Emitted afterwards through a separate save, an event-storage
    # failure left a durable imported filing and an advanced filed-revision
    # pointer that no history entry accounted for.
    fr_repo.save_with_secure_object_writes(
        updated_filing_catalogue,
        (
            cr_repo.to_secure_object_write(revisions, expected_revision_id=revisions_revision_id),
            wu_repo.to_secure_object_write(advanced_work_units),
            _bucket_event_write(bv_repo, (imported_event,)),
        ),
        expected_revision_id=filing_revision_id,
    )

    return new_filing


def _supersede_prior_current_external_filing(
    *,
    filing_catalogue: ModeloRecordCatalogue,
    prior_current: ModeloRecord | None,
    revisions: CalculationRevisionCatalogue,
    new_filing_id: str,
    now: datetime,
) -> tuple[ModeloRecordCatalogue, CalculationRevisionCatalogue]:
    updated_filing_catalogue = filing_catalogue
    if prior_current is None:
        return updated_filing_catalogue, revisions
    return _supersede_prior_current_filing(
        prior_current,
        filing_catalogue=updated_filing_catalogue,
        revisions=revisions,
        new_filing_id=new_filing_id,
        now=now,
    )


def _build_external_filing_record(
    *,
    filing_record_id: str,
    work_unit: WorkUnit,
    calculation_revision_id: CalculationRevisionId,
    filed_at: datetime,
    filed_by: str,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
) -> ModeloRecord:
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=filed_at,
        filed_by=filed_by,
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=evidence_reference_id,
            imported_at=filed_at,
        ),
    )


def _validated_external_reference[CasillaKey](
    casilla_values: Mapping[CasillaKey, Decimal],
    evidence_reference_id: str,
) -> str:
    """Return a stripped evidence reference after basic import-shape checks."""
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
    period: Period,
    expected_tax_id: str | None,
    justificante_repository: JustificanteRepository,
) -> None:
    """Require matching stored :class:`Justificante` metadata.

    CSV-register, justificante-PDF, and live-capture imports are treated as
    receipt-bound baselines: the evidence reference must resolve to stored
    justificante metadata for the same taxpayer, modelo, filing year, and
    period. The taxpayer comparison is case-insensitive after stripping.
    """
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
                "period": period.registry_token,
            },
        )


def _justificante_matches_import_target(
    justificante: Justificante,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    expected_tax_id: str,
) -> bool:
    """Return whether ``justificante`` matches the external-import target axis."""
    return justificante.matches_filing_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        tax_id=expected_tax_id,
    )
