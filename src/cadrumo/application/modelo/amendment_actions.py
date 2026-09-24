"""Amendment actions for externally filed modelo baselines.

:func:`~cadrumo.application.modelo.amendment_actions.amend_modelo_revision` starts from a current, externally evidenced
:class:`ModeloRecord`, builds a corrected
:class:`CalculationRevision` with an explicit
:class:`CalculationRevisionAmendmentKind`, supersedes the
baseline filing, and stores the new amendment record as current.

The side effects update the work-unit pointers and emit ``modelo.amended``
through the application-owned bucket-event capability, matching the
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
    :func:`~cadrumo.application.modelo.external_import_actions.import_external_filing_evidence`:
        Creates the AEAT-attested baseline that this module amends.
    :func:`~cadrumo.application.modelo._calculation_helpers.amendment_observations`:
        Carries or rebuilds observation provenance for the corrected casilla map.
    :class:`ExternalEvidence`:
        Filing-record evidence marker required before this amendment path can run.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_unknown_override_casillas`:
        Canonicalizes amendment override casilla ids against the registry.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_incomplete_amendment_casillas`:
        Reuses the registry completeness gate before the amendment is filed.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.modelo import Modelo
from ...core.result_disposition import ResultDisposition
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now as _utc_now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write as _bucket_event_write
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.calculation_repository import upsert_calculation_revision
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos.calculation_revision_aggregate import (
    CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY,
    CalculationRevisionAggregateContext,
)
from ...domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
    m303_rectificativa_motive_is_applicable,
)
from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos.filing_repository import upsert_filing_record
from ...domain.modelos.ledger_filing_snapshot import LedgerFilingEvidence, LedgerFilingSnapshot
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.ledger_filing_snapshot import (
    assert_evidence_covers_snapshot,
    compute_ledger_filing_snapshot,
)
from ._amendment_kind_resolution import assert_amendment_kind_permitted as _assert_amendment_kind_permitted
from ._amendment_kind_resolution import (
    assert_complementaria_liability_direction_permitted as _assert_complementaria_liability_direction_permitted,
)
from ._calculation_helpers import amendment_observations as _amendment_observations
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from ._calculation_modelo_adjustments import detail_row_declaration_modelos
from ._ledger_anchor_capture import capture_revision_ledger_evidence
from ._registry_helpers import refuse_stored_row_field_scalar_inputs as _refuse_stored_row_field_scalar_inputs
from ._registry_helpers import reject_incomplete_amendment_casillas as _reject_incomplete_amendment_casillas
from ._registry_helpers import reject_unknown_override_casillas as _reject_unknown_override_casillas
from .action_errors import (
    AmendmentDetailRowsRequiredError,
    AmendmentEvidenceMissingError,
    AmendmentM303RectificativaMotiveError,
    AmendmentTargetStateError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    WorkUnitNotFoundError,
)
from .amendment_action_ports import AmendmentActionPorts
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .filed_revision_observation import filed_revision_observation_writes, prepare_filed_revision_observation
from .lifecycle_clock_gate import (
    ModeloLifecycleClockOperation,
    amendment_ordering_instants,
    require_lifecycle_clock_not_before,
)
from .m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision
from .profile_export_binding import resolve_export_identity
from .result_disposition_resolution import base_modelo_result_disposition
from .revision_persistence import build_modelo_bucket_event as _build_bucket_event


def _load_amendment_baseline[CasillaKey](
    *,
    from_filing_record_id: str,
    overrides: Mapping[CasillaKey, Decimal],
    ports: AmendmentActionPorts,
    operation: PinnedAuthorityOperation,
):
    """Load the in-force entry being corrected and the confirmed declaration it amends.

    The in-force entry supplies the content the correction starts from. The
    amendment always references the latest AEAT-confirmed declaration of the
    period, because each correction chains to the immediately preceding
    accepted one; a pending in-force entry was never presented, so it is
    discarded rather than amended.
    """
    filing_catalogue = ports.filing_repository.load()
    in_force = filing_catalogue.get(from_filing_record_id)
    if in_force is None:
        raise ModeloRecordNotFoundError(
            translated_message="application.modelo.errors.filing_record_not_found",
            context={"filing_record_id": from_filing_record_id},
        )
    if in_force.status is not ModeloRecordStatus.VIGENTE:
        raise AmendmentTargetStateError(
            translated_message="errors.error.error_modelo_amendment_target_state",
            context={
                "filing_record_id": from_filing_record_id,
                "record_status": in_force.status.value,
            },
        )
    baseline = filing_catalogue.latest_confirmed_for(
        bucket_id=in_force.bucket_id,
        modelo=in_force.modelo,
        filing_year=in_force.filing_year,
        period=in_force.period,
        member_nif=in_force.member_nif,
    )
    if baseline is None or baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            translated_message="errors.error.error_modelo_amendment_evidence_missing",
            context={
                "filing_record_id": from_filing_record_id,
                "external_evidence_present": False,
            },
        )

    work_units = ports.work_unit_repository.load()
    work_unit = work_units.get(in_force.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={
                "filing_record_id": from_filing_record_id,
                "work_unit_id": in_force.work_unit_id,
            },
        )

    export_identity = resolve_export_identity(
        bucket_id=str(work_unit.bucket_id),
        operation=operation,
    )
    taxpayer_tax_id = export_identity[0].tax_id if export_identity is not None else None
    revisions = ports.calculation_repository.load()
    baseline_revision = _require_revision(revisions, baseline.calculation_revision_id, operation=operation)
    source_revision = _require_revision(revisions, in_force.calculation_revision_id, operation=operation)
    # Both revisions contribute stored inputs to the correction, so neither may
    # carry a scalar a detail-row casilla cannot hold.
    for stored_revision in (source_revision, baseline_revision):
        _refuse_stored_row_field_scalar_inputs(stored_revision, work_unit=work_unit, operation=operation)
    if work_unit.modelo == Modelo("303").value and source_revision.filing_instance_evidence is None:
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
        operation=operation,
    )
    return (
        filing_catalogue,
        in_force,
        baseline,
        work_units,
        work_unit,
        revisions,
        baseline_revision,
        source_revision,
        canonical_overrides,
        taxpayer_tax_id,
    )


def _require_revision(
    revisions: CalculationRevisionCatalogue,
    calculation_revision_id: str,
    *,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    revision = revisions.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    require_calculation_revision_coordinates_current(revision, operation=operation)
    return revision


def _resolve_m303_rectificativa_motive_before_identity(
    *,
    work_unit: WorkUnit,
    baseline_revision: CalculationRevision,
    amendment_kind: CalculationRevisionAmendmentKind,
    supplied: M303RectificativaMotive | None,
    operation: PinnedAuthorityOperation,
) -> M303RectificativaMotive | None:
    """Resolve the closed motive against exact retained authority before hashing."""
    applicable = _m303_rectificativa_motive_is_applicable(
        work_unit=work_unit,
        baseline_revision=baseline_revision,
        operation=operation,
    )
    requires_motive = (
        work_unit.modelo == Modelo("303").value and amendment_kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
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
    operation: PinnedAuthorityOperation,
) -> bool:
    if work_unit.modelo != Modelo("303").value:
        return False
    filing_evidence = baseline_revision.filing_instance_evidence
    if filing_evidence is None:
        raise AmendmentEvidenceMissingError(
            translated_message="errors.error.error_modelo_amendment_evidence_missing",
            context={"work_unit_id": work_unit.work_unit_id, "filing_instance_evidence_present": False},
        )
    regimen_snapshot = filing_evidence.m303.regimen_simplificado.regimen_snapshot
    snapshot = operation.snapshot(
        Modelo("303").value,
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
    detail_rows: Sequence[ModeloDetailRow] | None = None,
    reason: str,
    actor: str,
    ports: AmendmentActionPorts,
    clock: datetime | None = None,
    operation: PinnedAuthorityOperation | None = None,
    result_disposition: ResultDisposition | None = None,
) -> ModeloRecord:
    """Build and file an amendment of the period's latest AEAT-confirmed declaration.

    ``from_filing_record_id`` must identify the in-force
    :class:`ModeloRecord` of the period, confirmed or still pending. Its
    :class:`CalculationRevision` supplies the full casilla map; ``overrides``
    replace only corrected casillas after registry validation, while unchanged
    casillas are inherited. The amendment references the latest confirmed
    declaration; a pending in-force entry is marked ``DESCARTADA``, and with no
    confirmed declaration the amendment is refused. The resulting revision records the
    requested :class:`CalculationRevisionAmendmentKind`,
    stores the stripped ``reason``, receives registry-grounded observations,
    transitions through ``VERIFICADO_COMPLETO`` to ``PRESENTADO``, and becomes
    the current filed revision for the :class:`WorkUnit`.

    The confirmed baseline is linked to the new current amendment record. The
    new filing record is an internal filing envelope: the record stays
    ``PENDIENTE``, ``external_evidence`` is cleared, and
    ``amends_filing_record_id`` points back to the baseline. The amendment's
    observations are written to the pending-local layer, and a
    ``modelo.amended`` bucket event records the amendment kind, override count,
    work-unit id, amended baseline id and any discarded entry, all in one unit
    of work. ``result_disposition`` is the Modelo 303 declaration disposition of
    the correction; when omitted, the period's effective recorded disposition
    is kept.

    Returns:
        The new current :class:`ModeloRecord` for the
        amended return.

    See Also:
        ``aeat app modelo work amend``:
            CLI command that validates ``--from-filing-record``, ``--kind``,
            ``--reason``, and ``--set`` before calling this service.
        :func:`~cadrumo.application.modelo.external_import_actions.import_external_filing_evidence`:
            Production import path that creates accepted external-evidence
            baselines.
        :func:`~cadrumo.application.modelo._calculation_helpers.amendment_observations`:
            Builds the :class:`CasillaObservation`
            rows persisted on the amendment revision.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return amend_modelo_revision(
                from_filing_record_id=from_filing_record_id,
                overrides=overrides,
                amendment_kind=amendment_kind,
                m303_rectificativa_motive=m303_rectificativa_motive,
                detail_rows=detail_rows,
                reason=reason,
                actor=actor,
                ports=ports,
                clock=clock,
                operation=indexed_operation,
                result_disposition=result_disposition,
            )
    (
        filing_catalogue,
        in_force,
        baseline,
        work_units,
        work_unit,
        revisions,
        baseline_revision,
        source_revision,
        canonical_overrides,
        taxpayer_tax_id,
    ) = _load_amendment_baseline(
        from_filing_record_id=from_filing_record_id,
        overrides=overrides,
        ports=ports,
        operation=operation,
    )

    now = clock or _utc_now()
    require_lifecycle_clock_not_before(
        now,
        operation=ModeloLifecycleClockOperation.AMEND,
        instants=amendment_ordering_instants(work_unit=work_unit, baseline=baseline, in_force=in_force),
    )
    corrected_values: dict[CasillaId, Decimal] = dict(source_revision.casilla_values)
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
        operation=operation,
    )

    amendment_identity = CalculationRevisionAmendmentIdentity(
        kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        m303_rectificativa_motive=m303_rectificativa_motive,
    )
    amendment_detail_rows = _require_amendment_detail_rows(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        supplied=detail_rows,
    )
    if (
        corrected_values == dict(source_revision.casilla_values)
        and amendment_detail_rows == source_revision.detail_rows
    ):
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={
                "calculation_revision_id": source_revision.calculation_revision_id,
                "state": "no_op_amendment",
            },
        )
    new_revision_id = derive_calculation_revision_id(
        work_unit_id=in_force.work_unit_id,
        input_values_by_casilla_id=source_revision.input_values_by_casilla_id,
        binding_overrides=source_revision.binding_overrides,
        relation_overrides=source_revision.relation_overrides,
        casilla_values=corrected_values,
        source_transaction_ids=source_revision.source_transaction_ids,
        borrador_snapshot_id=source_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=source_revision.bindings_sourced_from_borrador,
        source_provenance=source_revision.source_provenance,
        filing_instance_evidence=source_revision.filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=None,
        amendment_identity=amendment_identity,
        detail_rows=amendment_detail_rows,
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
    registry_snapshot = _resolve_registry_snapshot_for_work_unit(work_unit, operation=operation)
    amendment_observations = _amendment_observations(
        corrected_values=corrected_values,
        overrides=canonical_overrides,
        baseline_revision=source_revision,
        snapshot=registry_snapshot,
    )
    filing_instance_evidence = validate_m303_filing_instance_evidence_for_revision(
        work_unit=work_unit,
        registry_snapshot=registry_snapshot,
        evidence=source_revision.filing_instance_evidence,
        casilla_values=corrected_values,
        observations=amendment_observations,
        operation=operation,
    )
    justificantes = tuple(ports.justificante_repository.iter_justificantes())
    aggregate_context = CalculationRevisionAggregateContext(
        work_units=work_units,
        filing_records=filing_catalogue,
        justificantes=justificantes,
        # The upsert revalidates every stored rectificativa, not only this
        # period's, so each Modelo 303 work unit needs its own snapshot.
        registry_snapshots={
            unit.work_unit_id: operation.snapshot(
                Modelo("303").value,
                filing_year=unit.filing_year,
                period=unit.period.registry_token,
            )
            for unit in work_units.values()
            if unit.modelo == Modelo("303").value
        },
        expected_taxpayer_tax_id=taxpayer_tax_id,
    )

    amendment_draft = _build_amendment_draft_revision(
        new_revision_id=new_revision_id,
        registry_snapshot_ref=registry_snapshot.snapshot_ref,
        baseline=in_force,
        baseline_revision=source_revision,
        corrected_values=corrected_values,
        amendment_observations=amendment_observations,
        amendment_identity=amendment_identity,
        detail_rows=amendment_detail_rows,
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
    ledger_snapshot, ledger_evidence = _amendment_ledger_anchor(
        amendment_draft=amendment_draft,
        work_unit=work_unit,
        transaction_repository=ports.transaction_repository,
        now=now,
    )
    verified_amendment = _verified_amendment_revision(
        amendment_draft,
        actor=actor,
        now=now,
        ledger_filing_snapshot=ledger_snapshot,
        ledger_filing_evidence=ledger_evidence,
    )
    revisions = upsert_calculation_revision(revisions, verified_amendment, aggregate_context=aggregate_context)

    new_filing_id, new_filing, updated_filing_catalogue = _build_amendment_filing_updates(
        baseline=baseline,
        in_force=in_force,
        filing_catalogue=filing_catalogue,
        new_revision_id=new_revision_id,
        declaration_kind=FilingDeclarationKind(amendment_kind.value),
        actor=actor,
        now=now,
    )

    filed_amendment = _filed_amendment_revision(verified_amendment, actor=actor, now=now)
    revisions = upsert_calculation_revision(revisions, filed_amendment, aggregate_context=aggregate_context)
    prepared_observation = prepare_filed_revision_observation(
        revision=filed_amendment,
        work_unit=work_unit,
        repository=ports.observation_repository,
        captured_at=now,
        result_disposition=_amendment_result_disposition(
            work_unit=work_unit,
            amendment=filed_amendment,
            supplied=result_disposition,
            ports=ports,
            operation=operation,
        ),
        filing_record_id=new_filing_id,
        iva_compensation_history_repository=ports.iva_compensation_history_repository,
    )

    _persist_amendment_side_effects(
        ports=ports,
        revisions=revisions,
        filing_catalogue=updated_filing_catalogue,
        work_units=work_units,
        work_unit=work_unit,
        baseline=baseline,
        discarded=in_force if in_force.filing_record_id != baseline.filing_record_id else None,
        new_revision_id=new_revision_id,
        new_filing_id=new_filing_id,
        amendment_kind=amendment_kind,
        override_count=len(canonical_overrides),
        observation_writes=filed_revision_observation_writes(
            prepared_observation,
            repository=ports.observation_repository,
            taxpayer_nif=None,
            filing_record_id=new_filing_id,
        ),
        actor=actor,
        now=now,
    )

    return new_filing


def _amendment_result_disposition(
    *,
    work_unit: WorkUnit,
    amendment: CalculationRevision,
    supplied: ResultDisposition | None,
    ports: AmendmentActionPorts,
    operation: PinnedAuthorityOperation,
) -> ResultDisposition | None:
    """Return the correction's disposition.

    A supplied disposition wins. Otherwise the period's recorded disposition is
    kept, and with none recorded the disposition the corrected result implies
    before any refund or payment election is used.
    """
    if supplied is not None or work_unit.modelo != Modelo("303").value:
        return supplied
    recorded = ports.observation_repository.load_observation(work_unit.modelo, work_unit.period)
    if recorded is not None and recorded.result_disposition is not None:
        return recorded.result_disposition.disposition
    return base_modelo_result_disposition(
        work_unit=work_unit,
        revision=amendment,
        period=work_unit.period,
        operation=operation,
    )


def _require_amendment_detail_rows(
    *,
    modelo: str,
    filing_year: int,
    supplied: Sequence[ModeloDetailRow] | None,
) -> tuple[ModeloDetailRow, ...]:
    """Return the rows an amendment declares, refusing to guess them.

    For a modelo whose rows constitute the declaration, ``None`` is not an
    empty set: it is the caller having said nothing, and the two amendment
    kinds would read that silence differently (LGT art. 122.2 para. 2). An
    explicitly empty sequence IS an answer -- "this period had none" -- and is
    accepted as one.

    Every other modelo has no detail rows to declare, so ``None`` there is
    simply their normal shape and yields the empty tuple.
    """
    if modelo not in detail_row_declaration_modelos(effective_date=date(filing_year, 12, 31)):
        return tuple(supplied or ())
    if supplied is None:
        raise AmendmentDetailRowsRequiredError(
            translated_message="errors.refused.refused_modelo_amendment_detail_rows_required",
            context={"modelo": modelo, "reason": "amendment_detail_rows_required"},
        )
    return tuple(supplied)


def _build_amendment_draft_revision(
    *,
    new_revision_id: CalculationRevisionId,
    registry_snapshot_ref: RegistrySnapshotRef,
    baseline: ModeloRecord,
    baseline_revision: CalculationRevision,
    corrected_values: dict[CasillaId, Decimal],
    amendment_observations: tuple[CasillaObservation, ...],
    amendment_identity: CalculationRevisionAmendmentIdentity,
    detail_rows: tuple[ModeloDetailRow, ...],
    reason: str,
    now: datetime,
    filing_instance_evidence: FilingInstanceEvidence | None,
    aggregate_context: CalculationRevisionAggregateContext,
) -> CalculationRevision:
    """Build the BORRADOR an amendment is filed from, carrying the baseline forward.

    The lifecycle fields are deliberately absent: this is a new draft, so
    ``verified_at``, ``filed_at``, ``superseded_at`` and the discard trio must
    not inherit the baseline's.

    ``detail_rows`` arrives already resolved, from
    :func:`_require_amendment_detail_rows`. Neither
    :func:`_verified_amendment_revision` nor :func:`_filed_amendment_revision`
    recomputes anything — both are pure state transitions — so whatever is set
    here is what an amended M347, M349, M184 or M232 declares. Defaulting it
    silently filed those declaring no counterparties at all; inheriting the
    baseline's rows would have been no better, because the amendment supplies
    corrected aggregate totals and says nothing about which counterpart moved,
    so inherited rows could contradict the totals filed beside them. The caller
    states the rows instead.

    It is threaded into ``derive_calculation_revision_id`` as well, and that is
    not symmetry for its own sake: ``detail_rows`` is part of the revision's
    content address, so a draft carrying rows the id was not derived over would
    address itself as a revision with none — and the ``upsert`` would then
    overwrite whatever already sat at that address.

    ``ledger_filing_snapshot`` and ``ledger_filing_evidence`` are absent on the
    DRAFT and supplied by :func:`_amendment_ledger_anchor` at the verify
    transition, which is where the verify path captures them too.
    """
    return CalculationRevision.model_validate(
        {
            "calculation_revision_id": new_revision_id,
            "work_unit_id": baseline.work_unit_id,
            "registry_snapshot_ref": registry_snapshot_ref,
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
            "detail_rows": detail_rows,
            "amendment_reason": reason.strip(),
            "filing_instance_evidence": filing_instance_evidence,
            "m303_regimen_simplificado_annual_summary_handoff": None,
        },
        context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: aggregate_context},
    )


def _build_amendment_filing_updates(
    *,
    baseline: ModeloRecord,
    in_force: ModeloRecord,
    filing_catalogue: ModeloRecordCatalogue,
    new_revision_id: CalculationRevisionId,
    declaration_kind: FilingDeclarationKind,
    actor: str,
    now: datetime,
) -> tuple[str, ModeloRecord, ModeloRecordCatalogue]:
    new_filing_id = derive_filing_record_id(
        work_unit_id=in_force.work_unit_id,
        calculation_revision_id=new_revision_id,
        filed_by=actor.strip(),
        member_nif=in_force.member_nif,
    )
    new_filing = _build_amendment_filing_record(
        filing_record_id=new_filing_id,
        in_force=in_force,
        baseline=baseline,
        calculation_revision_id=new_revision_id,
        declaration_kind=declaration_kind,
        filed_at=now,
        filed_by=actor.strip(),
    )
    updated_filing_catalogue = filing_catalogue
    if in_force.filing_record_id != baseline.filing_record_id:
        # A pending entry leaves the chain unpresented; retiring it first keeps
        # its stale amendment link out of the two-sided link check.
        discarded = in_force.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
                "confirmation": AeatConfirmationState.DESCARTADA,
            },
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, discarded)
    baseline_update: dict[str, object] = {"superseded_by_filing_record_id": new_filing_id}
    if baseline.status is ModeloRecordStatus.VIGENTE:
        baseline_update |= {"status": ModeloRecordStatus.SUPERSEDIDO, "superseded_at": now}
    updated_filing_catalogue = upsert_filing_record(
        updated_filing_catalogue,
        baseline.model_copy(update=baseline_update),
    )
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    return new_filing_id, new_filing, updated_filing_catalogue


def _amendment_ledger_anchor(
    *,
    amendment_draft: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    now: datetime,
) -> tuple[LedgerFilingSnapshot, LedgerFilingEvidence] | tuple[None, None]:
    """Capture the ledger facts an amendment is verified against, at amend time.

    Verify anchors a revision to the ledger it was computed from, and an
    amendment stands in for verify without ever calling it -- so an amended
    return used to carry no anchor at all, and ``stale_filed_revisions`` skips
    a revision whose snapshot is ``None``. An amended filing could therefore
    never be reported stale, whatever its books did afterwards.

    The capture is FRESH rather than inherited from the baseline. The
    amendment is being filed now, against the ledger as it stands now, and
    copying the baseline's anchor would assert that those older facts were the
    ones checked -- backdating a claim by exactly the interval the amendment
    exists to correct.

    A revision with no contributing rows anchors to nothing, and says so with
    ``None`` rather than an empty snapshot that would read as "checked, and
    the ledger was empty".
    """
    if not amendment_draft.source_transaction_ids:
        return (None, None)
    catalogue = transaction_repository.load()
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=amendment_draft.source_transaction_ids,
        catalogue=catalogue,
        captured_at=now,
    )
    evidence = capture_revision_ledger_evidence(
        revision=amendment_draft,
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=now,
    )
    assert_evidence_covers_snapshot(snapshot, evidence)
    return (snapshot, evidence)


def _verified_amendment_revision(
    amendment_draft: CalculationRevision,
    *,
    actor: str,
    now: datetime,
    ledger_filing_snapshot: LedgerFilingSnapshot | None,
    ledger_filing_evidence: LedgerFilingEvidence | None,
) -> CalculationRevision:
    return amendment_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
            "ledger_filing_snapshot": ledger_filing_snapshot,
            "ledger_filing_evidence": ledger_filing_evidence,
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
    in_force: ModeloRecord,
    baseline: ModeloRecord,
    calculation_revision_id: CalculationRevisionId,
    declaration_kind: FilingDeclarationKind,
    filed_at: datetime,
    filed_by: str,
) -> ModeloRecord:
    """Create the pending current filing record that replaces ``in_force`` and amends ``baseline``."""
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=in_force.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=in_force.bucket_id,
        modelo=in_force.modelo,
        filing_year=in_force.filing_year,
        period=in_force.period,
        member_nif=in_force.member_nif,
        filed_at=filed_at,
        filed_by=filed_by,
        notes=None,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=declaration_kind,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=None,
        amends_filing_record_id=baseline.filing_record_id,
    )


def _persist_amendment_side_effects(
    *,
    ports: AmendmentActionPorts,
    revisions: CalculationRevisionCatalogue,
    filing_catalogue: ModeloRecordCatalogue,
    work_units: WorkUnitCatalogue,
    work_unit: WorkUnit,
    baseline: ModeloRecord,
    discarded: ModeloRecord | None,
    new_revision_id: CalculationRevisionId,
    new_filing_id: str,
    amendment_kind: CalculationRevisionAmendmentKind,
    override_count: int,
    observation_writes: tuple[SecureObjectWrite, ...],
    actor: str,
    now: datetime,
) -> None:
    """Persist amendment catalogues, work-unit pointers, observations, and the bucket event.

    All of them commit in ONE unit of work. Saved separately with the event emitted
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
            "discarded_filing_record_id": discarded.filing_record_id if discarded is not None else "",
        },
    )
    ports.filing_repository.save_with_secure_object_writes(
        filing_catalogue,
        (
            ports.calculation_repository.to_secure_object_write(revisions),
            ports.work_unit_repository.to_secure_object_write(advanced_work_units),
            _bucket_event_write(ports.bucket_event_repository, (amended_event,)),
            *observation_writes,
        ),
    )
