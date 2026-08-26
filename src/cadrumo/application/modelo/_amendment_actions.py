"""Amendment actions for externally filed modelo baselines.

:func:`~cadrumo.application.modelo.amend_modelo_revision` starts from a current, externally evidenced
:class:`ModeloRecord`, builds a corrected
:class:`CalculationRevision` with an explicit
:class:`CalculationRevisionAmendmentKind`, supersedes the
baseline filing, and stores the new amendment record as current.

The side effects update the work-unit pointers and emit ``modelo.amended``
through :class:`BucketEventHistoryRepository`, matching the
event-history path used by imported and locally filed returns.

Only filing records carrying
:class:`ExternalEvidence` can enter this path. The standard
local ``calculate -> verify -> file`` chain remains separate:
locally filed records have no external evidence and must be corrected through
their own re-file workflow. Amendment overrides are resolved against the target
registry snapshot, rejected when they use printed or undeclared casilla tokens,
and projected back onto the
:class:`CasillaObservation` contract so the
new revision keeps legal/source provenance for both overridden and inherited
casillas.

See Also:
    :func:`~cadrumo.application.modelo.import_external_filing_evidence`:
        Creates the AEAT-attested baseline that this module amends.
    :func:`~cadrumo.application.modelo._calculation_helpers.amendment_observations`:
        Carries or rebuilds observation provenance for the corrected casilla map.
    :class:`ExternalEvidence`:
        Filing-record evidence marker required before this amendment path can run.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_unknown_override_casillas`:
        Canonicalizes amendment override casilla ids against the registry.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_incomplete_amendment_casillas`:
        Reuses the registry completeness gate before the amendment is filed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import CasillaId, Modelo
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
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.justificante import JustificanteRepositoryProtocol
from ...domain.modelos import (
    CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY,
    CalculationRevision,
    CalculationRevisionAggregateContext,
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    FilingInstanceEvidence,
    M303RectificativaMotive,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    WorkUnit,
    WorkUnitCatalogue,
    derive_calculation_revision_id,
    derive_filing_record_id,
    m303_rectificativa_motive_is_applicable,
    upsert_calculation_revision,
    upsert_filing_record,
    upsert_work_unit,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ._action_errors import (
    AmendmentEvidenceMissingError,
    AmendmentM303RectificativaMotiveError,
    AmendmentTargetStateError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    WorkUnitNotFoundError,
)
from ._amendment_kind_resolution import assert_amendment_kind_permitted as _assert_amendment_kind_permitted
from ._amendment_kind_resolution import (
    assert_complementaria_liability_direction_permitted as _assert_complementaria_liability_direction_permitted,
)
from ._calculation_helpers import amendment_observations as _amendment_observations
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from ._m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision
from ._profile_export_binding import resolve_export_identity
from ._registry_helpers import reject_incomplete_amendment_casillas as _reject_incomplete_amendment_casillas
from ._registry_helpers import reject_unknown_override_casillas as _reject_unknown_override_casillas
from ._revision_persistence import build_modelo_bucket_event as _build_bucket_event


def _load_amendment_baseline[CasillaKey](
    *,
    from_filing_record_id: str,
    overrides: Mapping[CasillaKey, Decimal],
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
):
    """Load and validate the current externally evidenced baseline filing."""
    filing_catalogue = filing_repository.load()
    baseline = filing_catalogue.get(from_filing_record_id)
    if baseline is None:
        raise ModeloRecordNotFoundError(
            translated_message="application.modelo.errors.filing_record_not_found",
            context={"filing_record_id": from_filing_record_id},
        )
    if baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            translated_message="errors.error.error_modelo_amendment_evidence_missing",
            context={
                "filing_record_id": from_filing_record_id,
                "external_evidence_present": False,
            },
        )
    if baseline.status is not ModeloRecordStatus.VIGENTE:
        raise AmendmentTargetStateError(
            translated_message="errors.error.error_modelo_amendment_target_state",
            context={
                "filing_record_id": from_filing_record_id,
                "record_status": baseline.status.value,
            },
        )

    work_units = work_unit_repository.load()
    work_unit = work_units.get(baseline.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={
                "filing_record_id": from_filing_record_id,
                "work_unit_id": baseline.work_unit_id,
            },
        )

    export_identity = resolve_export_identity(bucket_id=str(work_unit.bucket_id))
    taxpayer_tax_id = export_identity[0].tax_id if export_identity is not None else None
    resolved_calculation_repository = calculation_repository or CalculationRevisionCatalogueRepository(
        bucket_id=str(work_unit.bucket_id),
        m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
    )
    revisions = resolved_calculation_repository.load()
    baseline_revision = revisions.get(baseline.calculation_revision_id)
    if baseline_revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": baseline.calculation_revision_id},
        )
    if work_unit.modelo == Modelo.M303.value and baseline_revision.filing_instance_evidence is None:
        raise AmendmentEvidenceMissingError(
            translated_message="errors.error.error_modelo_amendment_evidence_missing",
            context={
                "filing_record_id": from_filing_record_id,
                "filing_instance_evidence_present": False,
            },
        )

    canonical_overrides = _reject_unknown_override_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        overrides=overrides,
    )
    return (
        filing_catalogue,
        baseline,
        work_units,
        work_unit,
        revisions,
        baseline_revision,
        canonical_overrides,
        resolved_calculation_repository,
        taxpayer_tax_id,
    )


def _resolve_m303_rectificativa_motive_before_identity(
    *,
    work_unit: WorkUnit,
    baseline_revision: CalculationRevision,
    amendment_kind: CalculationRevisionAmendmentKind,
    supplied: M303RectificativaMotive | None,
) -> M303RectificativaMotive | None:
    """Resolve the closed motive against exact retained authority before hashing."""
    applicable = _m303_rectificativa_motive_is_applicable(
        work_unit=work_unit,
        baseline_revision=baseline_revision,
    )
    requires_motive = (
        work_unit.modelo == Modelo.M303.value and amendment_kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
    )
    if (requires_motive and applicable and supplied is not None) or (not requires_motive and supplied is None):
        return supplied
    raise AmendmentM303RectificativaMotiveError(
        translated_message="errors.refused.refused_modelo_m303_rectificativa_motive",
        context={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "revision_id": work_unit.revision_id,
            "amendment_kind": amendment_kind.value,
            "motive_present": supplied is not None,
            "motive_applicable": applicable,
        },
    )


def _m303_rectificativa_motive_is_applicable(
    *,
    work_unit: WorkUnit,
    baseline_revision: CalculationRevision,
) -> bool:
    if work_unit.modelo != Modelo.M303.value:
        return False
    filing_evidence = baseline_revision.filing_instance_evidence
    if filing_evidence is None:
        raise AmendmentEvidenceMissingError(
            translated_message="errors.error.error_modelo_amendment_evidence_missing",
            context={"work_unit_id": work_unit.work_unit_id, "filing_instance_evidence_present": False},
        )
    regimen_snapshot = filing_evidence.m303.regimen_simplificado.regimen_snapshot
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    record_design = regimen_snapshot.record_design
    if not _m303_rectificativa_evidence_matches_coordinate(
        filing_evidence=filing_evidence,
        snapshot=snapshot,
        work_unit=work_unit,
    ):
        return False
    return m303_rectificativa_motive_is_applicable(
        registry_revision_id=work_unit.revision_id,
        record_design=record_design,
    )


def _m303_rectificativa_evidence_matches_coordinate(
    *,
    filing_evidence: FilingInstanceEvidence,
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
) -> bool:
    regimen_snapshot = filing_evidence.m303.regimen_simplificado.regimen_snapshot
    record_design = regimen_snapshot.record_design
    inspected_source = snapshot.sources.get(record_design.id)
    return all(
        (
            filing_evidence.m303.period == work_unit.period,
            regimen_snapshot.filing_year == work_unit.filing_year,
            regimen_snapshot.registry_revision_id == work_unit.revision_id == snapshot.revision.id,
            inspected_source == record_design,
            record_design.id in snapshot.revision.source_refs,
        )
    )


def amend_modelo_revision[CasillaKey](
    *,
    from_filing_record_id: str,
    overrides: Mapping[CasillaKey, Decimal],
    amendment_kind: CalculationRevisionAmendmentKind,
    m303_rectificativa_motive: M303RectificativaMotive | None = None,
    reason: str,
    actor: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    justificante_repository: JustificanteRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Build and file an amendment over an externally filed return.

    ``from_filing_record_id`` must identify the current
    :class:`ModeloRecord` for an imported AEAT-attested
    baseline. The baseline's
    :class:`CalculationRevision` supplies the full casilla
    map; ``overrides`` replace only corrected casillas after registry validation,
    while unchanged casillas are inherited. The resulting revision records the
    requested :class:`CalculationRevisionAmendmentKind`,
    stores the stripped ``reason``, receives registry-grounded observations,
    transitions through ``VERIFICADO_COMPLETO`` to ``PRESENTADO``, and becomes
    the current filed revision for the :class:`WorkUnit`.

    The baseline filing is marked ``SUPERSEDIDO`` and linked to the new current
    amendment record. The new filing record is an internal filing envelope:
    ``aeat_accepted`` remains false, ``external_evidence`` is cleared, and
    ``amends_filing_record_id`` points back to the imported baseline. A
    ``modelo.amended`` bucket event records the amendment kind, override count,
    work-unit id, and amended baseline id.

    Returns:
        The new current :class:`ModeloRecord` for the
        amended return.

    See Also:
        ``aeat app modelo work amend``:
            CLI command that validates ``--from-filing-record``, ``--kind``,
            ``--reason``, and ``--set`` before calling this service.
        :func:`~cadrumo.application.modelo.import_external_filing_evidence`:
            Production import path that creates accepted external-evidence
            baselines.
        :func:`~cadrumo.application.modelo._calculation_helpers.amendment_observations`:
            Builds the :class:`CasillaObservation`
            rows persisted on the amendment revision.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    justificante_repo = justificante_repository
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    (
        filing_catalogue,
        baseline,
        work_units,
        work_unit,
        revisions,
        baseline_revision,
        canonical_overrides,
        cr_repo,
        taxpayer_tax_id,
    ) = _load_amendment_baseline(
        from_filing_record_id=from_filing_record_id,
        overrides=overrides,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        filing_repository=fr_repo,
    )

    now = clock or _utc_now()
    corrected_values: dict[CasillaId, Decimal] = dict(baseline_revision.casilla_values)
    corrected_values.update(canonical_overrides)

    # Period-aware amendment-kind routing: refuse a requested kind the
    # resolved (modelo, period) does not legally permit (e.g. rectificativa
    # requested for a pre-adoption period, or complementaria requested where
    # rectificativa has replaced it), and — for a pre-rectificativa period —
    # refuse a complementaria that would decrease the taxpayer's declared
    # liability (that correction is a solicitud de rectificación, LGT
    # art. 120.3, not a complementaria, LGT art. 122.2). Both guards run
    # before any amendment state is persisted.
    _assert_amendment_kind_permitted(
        modelo=str(baseline.modelo),
        period=baseline.period,
        amendment_kind=amendment_kind,
    )
    _assert_complementaria_liability_direction_permitted(
        modelo=str(baseline.modelo),
        period=baseline.period,
        amendment_kind=amendment_kind,
        baseline_casilla_values=baseline_revision.casilla_values,
        corrected_casilla_values=corrected_values,
    )

    m303_rectificativa_motive = _resolve_m303_rectificativa_motive_before_identity(
        work_unit=work_unit,
        baseline_revision=baseline_revision,
        amendment_kind=amendment_kind,
        supplied=m303_rectificativa_motive,
    )

    amendment_identity = CalculationRevisionAmendmentIdentity(
        kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        m303_rectificativa_motive=m303_rectificativa_motive,
    )
    new_revision_id = derive_calculation_revision_id(
        work_unit_id=baseline.work_unit_id,
        input_values_by_casilla_id=baseline_revision.input_values_by_casilla_id,
        binding_overrides=baseline_revision.binding_overrides,
        relation_overrides=baseline_revision.relation_overrides,
        casilla_values=corrected_values,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
        source_provenance=baseline_revision.source_provenance,
        filing_instance_evidence=baseline_revision.filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=None,
        amendment_identity=amendment_identity,
    )
    if new_revision_id in revisions:
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={"calculation_revision_id": new_revision_id, "state": "duplicate_amendment_revision"},
        )

    # Carry regulatory grounding onto the amendment: build typed
    # CasillaObservation rows for the corrected casilla map so the
    # persisted amendment revision and its CLI emit preserve
    # legal_refs / source_refs (and baseline formula provenance for
    # non-overridden casillas) instead of an empty observations tuple.
    registry_snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    amendment_observations = _amendment_observations(
        corrected_values=corrected_values,
        overrides=canonical_overrides,
        baseline_revision=baseline_revision,
        snapshot=registry_snapshot,
    )
    filing_instance_evidence = validate_m303_filing_instance_evidence_for_revision(
        work_unit=work_unit,
        registry_snapshot=registry_snapshot,
        evidence=baseline_revision.filing_instance_evidence,
        casilla_values=corrected_values,
        observations=amendment_observations,
    )
    justificantes = tuple(justificante_repo.iter_justificantes()) if justificante_repo is not None else ()
    aggregate_context = CalculationRevisionAggregateContext(
        work_units=work_units,
        filing_records=filing_catalogue,
        justificantes=justificantes,
        registry_snapshots={
            work_unit.work_unit_id: bundled_authority().snapshot(
                Modelo.M303.value,
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            )
        }
        if work_unit.modelo == Modelo.M303.value
        else {},
        expected_taxpayer_tax_id=taxpayer_tax_id,
    )

    amendment_draft = _build_amendment_draft_revision(
        new_revision_id=new_revision_id,
        baseline=baseline,
        baseline_revision=baseline_revision,
        corrected_values=corrected_values,
        amendment_observations=amendment_observations,
        amendment_identity=amendment_identity,
        reason=reason,
        now=now,
        filing_instance_evidence=filing_instance_evidence,
        aggregate_context=aggregate_context,
    )
    revisions = upsert_calculation_revision(revisions, amendment_draft, aggregate_context=aggregate_context)

    # Verify the corrected casilla map against the registry's
    # required-manual-input contract before transitioning. The amend
    # path mirrors the standard verify gate so a complementaria
    # cannot be filed with a missing required casilla.
    _reject_incomplete_amendment_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        casilla_values=corrected_values,
    )

    # Transition draft → verified-complete (operator opts in by calling amend).
    verified_amendment = _verified_amendment_revision(amendment_draft, actor=actor, now=now)
    revisions = upsert_calculation_revision(revisions, verified_amendment, aggregate_context=aggregate_context)

    new_filing_id, new_filing, updated_filing_catalogue = _build_amendment_filing_updates(
        baseline=baseline,
        filing_catalogue=filing_catalogue,
        new_revision_id=new_revision_id,
        actor=actor,
        now=now,
    )

    filed_amendment = _filed_amendment_revision(verified_amendment, actor=actor, now=now)
    revisions = upsert_calculation_revision(revisions, filed_amendment, aggregate_context=aggregate_context)

    _persist_amendment_side_effects(
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        work_unit_repository=wu_repo,
        bucket_event_repository=bv_repo,
        revisions=revisions,
        filing_catalogue=updated_filing_catalogue,
        work_units=work_units,
        work_unit=work_unit,
        baseline=baseline,
        new_revision_id=new_revision_id,
        new_filing_id=new_filing_id,
        amendment_kind=amendment_kind,
        override_count=len(canonical_overrides),
        actor=actor,
        now=now,
    )

    return new_filing


def _build_amendment_draft_revision(
    *,
    new_revision_id: CalculationRevisionId,
    baseline: ModeloRecord,
    baseline_revision: CalculationRevision,
    corrected_values: dict[CasillaId, Decimal],
    amendment_observations: tuple[CasillaObservation, ...],
    amendment_identity: CalculationRevisionAmendmentIdentity,
    reason: str,
    now: datetime,
    filing_instance_evidence: FilingInstanceEvidence | None,
    aggregate_context: CalculationRevisionAggregateContext,
) -> CalculationRevision:
    return CalculationRevision.model_validate(
        {
            "calculation_revision_id": new_revision_id,
            "work_unit_id": baseline.work_unit_id,
            "state": CalculationRevisionState.BORRADOR,
            "input_values_by_casilla_id": baseline_revision.input_values_by_casilla_id,
            "binding_overrides": baseline_revision.binding_overrides,
            "relation_overrides": baseline_revision.relation_overrides,
            "source_transaction_ids": baseline_revision.source_transaction_ids,
            "borrador_snapshot_id": baseline_revision.borrador_snapshot_id,
            "bindings_sourced_from_borrador": baseline_revision.bindings_sourced_from_borrador,
            "source_provenance": baseline_revision.source_provenance,
            "casilla_values": corrected_values,
            "observations": amendment_observations,
            "created_at": now,
            "updated_at": now,
            "amendment_identity": amendment_identity,
            "amendment_reason": reason.strip(),
            "filing_instance_evidence": filing_instance_evidence,
            "m303_regimen_simplificado_annual_summary_handoff": None,
        },
        context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: aggregate_context},
    )


def _build_amendment_filing_updates(
    *,
    baseline: ModeloRecord,
    filing_catalogue: ModeloRecordCatalogue,
    new_revision_id: CalculationRevisionId,
    actor: str,
    now: datetime,
) -> tuple[str, ModeloRecord, ModeloRecordCatalogue]:
    new_filing_id = derive_filing_record_id(
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        filed_by=actor.strip(),
        member_nif=baseline.member_nif,
    )
    new_filing = _build_amendment_filing_record(
        filing_record_id=new_filing_id,
        baseline=baseline,
        calculation_revision_id=new_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )
    superseded_baseline = baseline.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": now,
            "superseded_by_filing_record_id": new_filing_id,
        },
    )
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_baseline)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    return new_filing_id, new_filing, updated_filing_catalogue


def _verified_amendment_revision(
    amendment_draft: CalculationRevision,
    *,
    actor: str,
    now: datetime,
) -> CalculationRevision:
    return amendment_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        },
    )


def _filed_amendment_revision(
    verified_amendment: CalculationRevision,
    *,
    actor: str,
    now: datetime,
) -> CalculationRevision:
    return verified_amendment.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        },
    )


def _build_amendment_filing_record(
    *,
    filing_record_id: str,
    baseline: ModeloRecord,
    calculation_revision_id: CalculationRevisionId,
    filed_at: datetime,
    filed_by: str,
) -> ModeloRecord:
    """Create the current filing record that points back to ``baseline``."""
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=baseline.bucket_id,
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        member_nif=baseline.member_nif,
        filed_at=filed_at,
        filed_by=filed_by,
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=None,
        amends_filing_record_id=baseline.filing_record_id,
    )


def _persist_amendment_side_effects(
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    revisions: CalculationRevisionCatalogue,
    filing_catalogue: ModeloRecordCatalogue,
    work_units: WorkUnitCatalogue,
    work_unit: WorkUnit,
    baseline: ModeloRecord,
    new_revision_id: CalculationRevisionId,
    new_filing_id: str,
    amendment_kind: CalculationRevisionAmendmentKind,
    override_count: int,
    actor: str,
    now: datetime,
) -> None:
    """Persist amendment catalogues, work-unit pointers, and the bucket event.

    All four commit in ONE unit of work. Saved separately with the event emitted
    last, an event-storage failure left the amended filing durable and the
    work-unit pointers advanced to it while the history carried no
    ``modelo.amended`` entry and no retryable marker named the gap -- an
    amendment that, by construction, no audit reader could reconstruct.
    """
    advanced_work_units = upsert_work_unit(
        work_units,
        work_unit.model_copy(
            update={
                "current_calculation_revision_id": new_revision_id,
                "filed_calculation_revision_id": new_revision_id,
                "current_filing_record_id": new_filing_id,
                "updated_at": now,
            },
        ),
    )
    amended_event = _build_bucket_event(
        bucket_id=baseline.bucket_id,
        event_type=BucketEventType.MODELO_AMENDED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "amends_filing_record_id": baseline.filing_record_id,
            "calculation_revision_id": new_revision_id,
            "work_unit_id": baseline.work_unit_id,
            "modelo": str(baseline.modelo),
            "filing_year": str(baseline.filing_year),
            "period": baseline.period.registry_token,
            "amendment_kind": amendment_kind.value,
            "override_count": str(override_count),
        },
    )
    filing_repository.save_with_secure_object_writes(
        filing_catalogue,
        (
            calculation_repository.to_secure_object_write(revisions),
            work_unit_repository.to_secure_object_write(advanced_work_units),
            _bucket_event_write(bucket_event_repository, (amended_event,)),
        ),
    )
