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
        Receipt metadata store required by justificante-PDF and live-capture evidence
        kinds. CSV/XLSX register imports bind the source reference directly to
        the target work-unit coordinates instead of masquerading as a receipt.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_unknown_import_casillas`:
        Resolves the registry snapshot and refuses noncanonical or undeclared
        imported casilla ids.
    :class:`ExternalEvidence`:
        Filing-record metadata that records the official evidence source.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import CasillaId, Modelo, Period, validated_casilla_id
from ...core.decimal import normalize_decimal_separators
from ...core.identity import CalculationRevisionId
from ...core.time import now as _utc_now
from ...domain.buckets import (
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets import (
    bucket_event_history_write as _bucket_event_write,
)
from ...domain.calculations.registry import BindingId, RegistryModeloObservation, RelationId
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
    WorkUnitCatalogue,
    derive_calculation_revision_id,
    derive_filing_record_id,
    is_receipt_bound_external_evidence,
    upsert_calculation_revision,
    upsert_filing_record,
    upsert_work_unit,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations import CalculationObservationRepository, ObservationSourceKind
from ._action_errors import ExternalModeloImportError
from ._calculation_helpers import external_filing_observations as _external_filing_observations
from ._registry_helpers import reject_unknown_import_casillas as _reject_unknown_import_casillas
from ._revision_persistence import build_modelo_bucket_event as _build_bucket_event
from ._revision_persistence import supersede_prior_current_filing as _supersede_prior_current_filing
from ._work_lifecycle import ActiveWorkUnitUse, create_work_unit, require_active_work_unit
from .work_addressing import (
    ModeloWorkResolution,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
    ModeloWorkVisibleTargetAmbiguousError,
    resolve_registry_revision_for_work_target,
    select_modelo_work_resolution,
)


@dataclass(frozen=True, slots=True)
class ExternalFilingBaselineSource:
    """One source-only, casilla-complete external filing observation."""

    modelo: str
    filing_year: int
    period: Period
    evidence_kind: ExternalEvidenceKind
    evidence_reference_id: str
    tax_id: str
    casilla_lexicals: Mapping[CasillaId, str]
    registry_revision_id: str | None = None


def _select_active_external_import_work_unit(
    source: ExternalFilingBaselineSource,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Apply the canonical active-only cardinality policy to one captured catalogue."""
    return select_modelo_work_resolution(
        ModeloWorkSelectorRequest(
            bucket_id=bucket_id,
            modelo=source.modelo,
            filing_year=source.filing_year,
            period=source.period,
            revision_id=source.registry_revision_id,
        ),
        catalogue=catalogue,
        bucket_id=bucket_id,
        mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
    )


def import_external_filing_source(
    source: ExternalFilingBaselineSource,
    *,
    bucket_id: str,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    justificante_repository: JustificanteRepository | None = None,
    observation_repository: CalculationObservationRepository | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Resolve or create the target work unit and persist an amendable baseline.

    Source lexical tokens are retained verbatim on the revision input snapshot;
    their independently parsed Decimal values feed the filing baseline.
    """
    if source.period.filing_year != source.filing_year:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_period_mismatch",
        )
    if not source.casilla_lexicals:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )
    lexical_values: dict[CasillaId, str] = {}
    decimal_values: dict[CasillaId, Decimal] = {}
    for raw_casilla_id, raw_lexical in source.casilla_lexicals.items():
        casilla_id = validated_casilla_id(raw_casilla_id, surface="external filing source")
        lexical = raw_lexical.strip()
        if not lexical:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_blank",
                context={"casilla_id": casilla_id},
            )
        try:
            decimal_value = Decimal(
                normalize_decimal_separators(
                    lexical,
                    strip_thousands="." in lexical and "," in lexical,
                ),
            )
        except (InvalidOperation, ValueError) as exc:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_non_numeric",
                context={"casilla_id": casilla_id},
            ) from exc
        lexical_values[casilla_id] = raw_lexical
        decimal_values[casilla_id] = decimal_value

    snapshot, canonical_values = _reject_unknown_import_casillas(
        modelo=source.modelo,
        filing_year=source.filing_year,
        period=source.period,
        casilla_values=decimal_values,
    )
    _validated_source_lexicals(
        canonical_values=canonical_values,
        source_lexicals=lexical_values,
    )
    required_numeric_ids = {
        casilla.id
        for casilla in snapshot.revision.casillas
        if casilla.required and casilla.data_type in {"decimal", "money", "integer", "ratio", "boolean"}
    }
    missing_required = required_numeric_ids.difference(canonical_values)
    if missing_required:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_incomplete",
            context={"missing_casilla_ids": ",".join(sorted(missing_required))},
        )
    if source.modelo == Modelo.M303.value:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_m303_filing_evidence_required",
        )
    if not actor.strip():
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_actor_blank",
        )
    _require_bound_justificante_artifact(
        evidence_kind=source.evidence_kind,
        evidence_reference_id=source.evidence_reference_id.strip(),
        modelo=source.modelo,
        filing_year=source.filing_year,
        period=source.period,
        expected_tax_id=source.tax_id,
        justificante_repository=justificante_repository or JustificanteRepository(),
    )

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository(bucket_id=bucket_id)
    catalogue = wu_repo.load()
    try:
        resolution = _select_active_external_import_work_unit(
            source,
            catalogue=catalogue,
            bucket_id=bucket_id,
        )
    except ModeloWorkVisibleTargetAmbiguousError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_work_unit_ambiguous",
        ) from exc
    except ModeloWorkRevisionConflictError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_revision_mismatch",
        ) from exc
    if resolution.work_unit is not None:
        work_unit = resolution.work_unit
    else:
        revision_id = resolve_registry_revision_for_work_target(
            modelo=source.modelo,
            filing_year=source.filing_year,
            period=source.period,
            registry_revision_id=source.registry_revision_id,
        )
        work_unit = create_work_unit(
            bucket_id=bucket_id,
            modelo=source.modelo,
            filing_year=source.filing_year,
            period=source.period,
            revision_id=revision_id,
            actor=actor,
            repository=wu_repo,
            bucket_event_repository=bucket_event_repository,
            clock=clock,
        )
    return import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=decimal_values,
        source_lexical_values_by_casilla_id=lexical_values,
        evidence_kind=source.evidence_kind,
        evidence_reference_id=source.evidence_reference_id,
        actor=actor,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        bucket_event_repository=bucket_event_repository,
        justificante_repository=justificante_repository,
        observation_repository=observation_repository,
        expected_tax_id=source.tax_id,
        clock=clock,
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


def _validated_source_lexicals[CasillaKey](
    *,
    canonical_values: Mapping[CasillaId, Decimal],
    source_lexicals: Mapping[CasillaKey, str] | None,
) -> dict[CasillaId, str]:
    if source_lexicals is None:
        return {}
    canonical_lexicals = {
        validated_casilla_id(raw_id, surface="external filing source"): value
        for raw_id, value in source_lexicals.items()
    }
    if canonical_lexicals.keys() != canonical_values.keys():
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_casilla_mismatch",
        )
    validated: dict[CasillaId, str] = {}
    for casilla_id, raw_value in canonical_lexicals.items():
        lexical = raw_value.strip()
        try:
            parsed = Decimal(
                normalize_decimal_separators(
                    lexical,
                    strip_thousands="." in lexical and "," in lexical,
                ),
            )
        except (InvalidOperation, ValueError) as exc:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_non_numeric",
                context={"casilla_id": casilla_id},
            ) from exc
        if not lexical or parsed != canonical_values[casilla_id]:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_value_mismatch",
                context={"casilla_id": casilla_id},
            )
        validated[casilla_id] = raw_value
    return validated


def import_external_filing_evidence[CasillaKey](
    *,
    work_unit_id: str,
    casilla_values: Mapping[CasillaKey, Decimal],
    source_lexical_values_by_casilla_id: Mapping[CasillaKey, str] | None = None,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    justificante_repository: JustificanteRepository | None = None,
    observation_repository: CalculationObservationRepository | None = None,
    expected_tax_id: str | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Persist an externally-filed return and return its current :class:`ModeloRecord`.

    The target :class:`WorkUnit` supplies the bucket,
    modelo, filing year, period, and registry revision used to validate imported
    casilla ids. Justificante-bound evidence kinds require a stored
    :class:`Justificante` whose modelo, year, period,
    and taxpayer id match the target. CSV-register evidence is the imported
    file itself: its reference is bound to the validated target coordinates in
    the atomically committed filing record and does not require fabricated
    Justificante metadata.

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
    observation_repo = observation_repository or CalculationObservationRepository()

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

    input_values_by_casilla_id = _validated_source_lexicals(
        canonical_values=canonical_values,
        source_lexicals=source_lexical_values_by_casilla_id,
    )
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
        source_provenance=(),
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
        source_provenance=(),
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
    observation_payload = (
        observation_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
                observations=revision.observations,
            ),
            source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
            captured_at=now,
            stamped_revision_id=work_unit.revision_id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": cleaned_reference,
                "authenticated_identity": (expected_tax_id or "").strip(),
                "external_evidence_reference_id": cleaned_reference,
                "filing_record_id": new_filing_id,
            },
        )
        if evidence_kind is ExternalEvidenceKind.AEAT_CSV_REGISTER
        else None
    )

    # One unit of work: the imported revision, the filing catalogue, the advanced
    # work-unit pointers, and the ``modelo.filing.imported`` event commit
    # together. Emitted afterwards through a separate save, an event-storage
    # failure left a durable imported filing and an advanced filed-revision
    # pointer that no history entry accounted for.
    fr_repo.save_with_secure_object_writes(
        updated_filing_catalogue,
        tuple(
            write
            for write in (
                cr_repo.to_secure_object_write(revisions, expected_revision_id=revisions_revision_id),
                wu_repo.to_secure_object_write(advanced_work_units),
                _bucket_event_write(bv_repo, (imported_event,)),
                observation_repo.to_secure_object_write(observation_payload)
                if observation_payload is not None
                else None,
            )
            if write is not None
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

    Justificante-PDF and live-capture imports are treated as receipt-bound
    baselines: the evidence reference must resolve to stored
    justificante metadata for the same taxpayer, modelo, filing year, and
    period. The taxpayer comparison is case-insensitive after stripping.
    """
    if not is_receipt_bound_external_evidence(evidence_kind):
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
