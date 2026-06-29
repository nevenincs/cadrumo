"""Amendment actions for externally filed modelo baselines.

``amend_modelo_revision`` starts from a current, externally evidenced
:class:`ModeloRecord`, builds a corrected :class:`CalculationRevision` with an
explicit :class:`CalculationRevisionAmendmentKind`, supersedes the baseline
filing, and stores the new amendment record as current.

The side effects update the work-unit pointers and emit ``modelo.amended``
through :class:`BucketEventHistoryRepository`, matching the event-history path
used by imported and locally filed returns.

Only filing records carrying
:class:`~aeat.domain.modelos._filing_record.ExternalEvidence` can enter this
path. The standard local ``calculate -> verify -> file`` chain remains separate:
locally filed records have no external evidence and must be corrected through
their own re-file workflow. Amendment overrides are resolved against the target
registry snapshot, rejected when they use printed or undeclared casilla tokens,
and projected back onto the
:class:`~aeat.domain.calculations.registry.CasillaObservation` contract so the
new revision keeps legal/source provenance for both overridden and inherited
casillas.

See Also:
    :func:`aeat.application.modelo._external_import_actions.import_external_filing_evidence`:
        Creates the AEAT-attested baseline that this module amends.
    :func:`aeat.application.modelo._calculation_helpers.amendment_observations`:
        Carries or rebuilds observation provenance for the corrected casilla map.
    :func:`aeat.application.modelo._registry_helpers.reject_unknown_override_casillas`:
        Canonicalizes amendment override casilla ids against the registry.
    :func:`aeat.application.modelo._registry_helpers.reject_incomplete_amendment_casillas`:
        Reuses the registry completeness gate before the amendment is filed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepository, BucketEventObjectType, BucketEventType
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import CasillaId
from ...domain.modelos import (
    CalculationRevisionCatalogue,
    ModeloRecordCatalogue,
    WorkUnit,
    WorkUnitCatalogue,
)
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._filing_record import ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository, upsert_filing_record
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ._action_errors import (
    AmendmentEvidenceMissingError,
    AmendmentTargetStateError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    WorkUnitNotFoundError,
)
from ._calculation_helpers import amendment_observations as _amendment_observations
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from ._registry_helpers import reject_incomplete_amendment_casillas as _reject_incomplete_amendment_casillas
from ._registry_helpers import reject_unknown_override_casillas as _reject_unknown_override_casillas
from ._revision_persistence import emit_bucket_event as _emit_bucket_event


def _load_amendment_baseline[CasillaKey](
    *,
    from_filing_record_id: str,
    overrides: Mapping[CasillaKey, Decimal],
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
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
            f"filing record {from_filing_record_id!r} has no external_evidence; the "
            f"modelo amend path requires an imported AEAT-attested baseline. Use the "
            f"standard re-file path (calculate → verify → file) for locally-filed returns.",
        )
    if baseline.status is not ModeloRecordStatus.VIGENTE:
        raise AmendmentTargetStateError(
            f"filing record {from_filing_record_id!r} is in status {baseline.status.value!r}; "
            f"only CURRENT filings can be amended",
        )

    work_units = work_unit_repository.load()
    work_unit = work_units.get(baseline.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"filing record {from_filing_record_id!r} references missing work_unit_id={baseline.work_unit_id!r}",
        )

    revisions = calculation_repository.load()
    baseline_revision = revisions.get(baseline.calculation_revision_id)
    if baseline_revision is None:
        raise CalculationRevisionNotFoundError(
            f"baseline calculation revision {baseline.calculation_revision_id!r} is missing from the catalogue",
        )

    canonical_overrides = _reject_unknown_override_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        overrides=overrides,
    )
    return filing_catalogue, baseline, work_units, work_unit, revisions, baseline_revision, canonical_overrides


def amend_modelo_revision[CasillaKey](
    *,
    from_filing_record_id: str,
    overrides: Mapping[CasillaKey, Decimal],
    amendment_kind: CalculationRevisionAmendmentKind,
    reason: str,
    actor: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Build and file an amendment over an externally filed return.

    ``from_filing_record_id`` must identify the current
    :class:`ModeloRecord` for an imported AEAT-attested baseline. The baseline's
    :class:`CalculationRevision` supplies the full casilla map; ``overrides``
    replace only corrected casillas after registry validation, while unchanged
    casillas are inherited. The resulting revision records the requested
    :class:`CalculationRevisionAmendmentKind`, stores the stripped ``reason``,
    receives registry-grounded observations, transitions through
    ``VERIFICADO_COMPLETO`` to ``PRESENTADO``, and becomes the current filed
    revision for the :class:`WorkUnit`.

    The baseline filing is marked ``SUPERSEDIDO`` and linked to the new current
    amendment record. The new filing record is an internal filing envelope:
    ``aeat_accepted`` remains false, ``external_evidence`` is cleared, and
    ``amends_filing_record_id`` points back to the imported baseline. A
    ``modelo.amended`` bucket event records the amendment kind, override count,
    work-unit id, and amended baseline id.

    Returns:
        The new current :class:`ModeloRecord` for the amended return.

    See Also:
        ``aeat app modelo work amend``:
            CLI command that validates ``--from-filing-record``, ``--kind``,
            ``--reason``, and ``--set`` before calling this service.
        :func:`aeat.application.modelo._external_import_actions.import_external_filing_evidence`:
            Production import path that creates accepted external-evidence
            baselines.
        :func:`aeat.application.modelo._calculation_helpers.amendment_observations`:
            Builds the :class:`~aeat.domain.calculations.registry.CasillaObservation`
            rows persisted on the amendment revision.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    filing_catalogue, baseline, work_units, work_unit, revisions, baseline_revision, canonical_overrides = (
        _load_amendment_baseline(
            from_filing_record_id=from_filing_record_id,
            overrides=overrides,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
        )
    )

    now = clock or _utc_now()
    corrected_values: dict[CasillaId, Decimal] = dict(baseline_revision.casilla_values)
    corrected_values.update(canonical_overrides)

    new_revision_id = derive_calculation_revision_id(
        work_unit_id=baseline.work_unit_id,
        input_values_by_casilla_id=baseline_revision.input_values_by_casilla_id,
        binding_overrides=baseline_revision.binding_overrides,
        relation_overrides=baseline_revision.relation_overrides,
        casilla_values=corrected_values,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
    )
    if new_revision_id in revisions:
        raise CalculationRevisionStateError(
            f"amendment overrides produce calculation_revision_id {new_revision_id!r} "
            f"that already exists in the catalogue; no-op overrides cannot be filed as amendments",
        )

    # Carry regulatory grounding onto the amendment: build typed
    # CasillaObservation rows for the corrected casilla map so the
    # persisted amendment revision and its CLI emit preserve
    # legal_refs / source_refs (and baseline formula provenance for
    # non-overridden casillas) instead of an empty observations tuple.
    amendment_observations = _amendment_observations(
        corrected_values=corrected_values,
        overrides=canonical_overrides,
        baseline_revision=baseline_revision,
        snapshot=_resolve_registry_snapshot_for_work_unit(work_unit),
    )

    amendment_draft = CalculationRevision(
        calculation_revision_id=new_revision_id,
        work_unit_id=baseline.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=baseline_revision.input_values_by_casilla_id,
        binding_overrides=baseline_revision.binding_overrides,
        relation_overrides=baseline_revision.relation_overrides,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
        casilla_values=corrected_values,
        observations=amendment_observations,
        created_at=now,
        updated_at=now,
        amendment_kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        amendment_reason=reason.strip(),
    )
    revisions = upsert_calculation_revision(revisions, amendment_draft)

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
    revisions = upsert_calculation_revision(revisions, verified_amendment)

    new_filing_id = derive_filing_record_id(
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
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

    filed_amendment = _filed_amendment_revision(verified_amendment, actor=actor, now=now)
    revisions = upsert_calculation_revision(revisions, filed_amendment)

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
    calculation_revision_id: str,
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
    new_revision_id: str,
    new_filing_id: str,
    amendment_kind: CalculationRevisionAmendmentKind,
    override_count: int,
    actor: str,
    now: datetime,
) -> None:
    """Persist amendment catalogues, work-unit pointers, and the bucket event."""
    calculation_repository.save(revisions)
    filing_repository.save(filing_catalogue)
    work_unit_repository.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": new_revision_id,
                    "filed_calculation_revision_id": new_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                },
            ),
        ),
    )
    _emit_bucket_event(
        repository=bucket_event_repository,
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
