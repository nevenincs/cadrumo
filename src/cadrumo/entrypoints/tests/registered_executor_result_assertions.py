"""Verify focused result projections produced by registered executor scenarios."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.ledger.actions_manual import command_from_patch, prepare_manual_transaction_update
from ...application.ledger.id_resolution import resolve_lineage_transaction_id
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...application.ledger.participation_operation import (
    LedgerParticipationProjection as LedgerParticipationLookupProjection,
)
from ...application.ledger.participation_operation import LedgerParticipationRequest
from ...application.ledger.participation_rebuild_operation import LedgerParticipationRebuildProjection
from ...application.ledger.review_operation import LedgerReviewProjection, LedgerReviewRequest
from ...application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest
from ...application.ledger.tracking_projection import (
    LedgerParticipationProjection as LedgerParticipationEntryProjection,
)
from ...application.modelo.calculation_report_verification import (
    CalculationSummaryCheckName,
    CalculationSummaryVerificationLayer,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
)
from ...application.modelo.calculation_report_verification_operation import (
    ModeloCalculationReportVerificationProjection,
    ModeloCalculationReportVerificationRequest,
)
from ...application.operations.registry import OperationRegistry
from ...application.review.filter import LedgerReviewStatus
from ...domain.buckets.event import BucketEvent
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.transactions.models import Transaction
from ..ledger_action_composition import compose_ledger_action_ports
from .registered_executor_case_support import _ExecutionDriver, _resolve_result_projection


def _assert_ledger_track_result(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    payload: BaseModel,
    operation_id: str,
    terminal_revision: int,
) -> None:
    assert isinstance(payload, LedgerTrackRequest)
    track = _resolve_result_projection(
        driver,
        registry,
        definition_id="ledger.track",
        operation_id=operation_id,
        terminal_revision=terminal_revision,
        projection_type=LedgerTrackProjection,
    )
    assert isinstance(track, LedgerTrackProjection)
    transaction_id = resolve_lineage_transaction_id(
        payload.transaction_prefix,
        TransactionCatalogueRepository(bucket_id=str(profile_id)).load(),
    )
    assert track.profile_id == profile_id
    assert track.transaction_prefix == payload.transaction_prefix
    assert track.transaction.transaction_id == transaction_id
    assert track.tracking.transaction_id == transaction_id
    assert track.participated_in is not None
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transaction_id)
    assert len(index.participations) == 1
    participation = index.participations[0]
    assert track.participated_in == (LedgerParticipationEntryProjection.from_participation(participation),)
    assert participation.filing_record_id is None
    assert participation.justificante_reference is None
    assert participation.revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value
    revision = (
        CalculationRevisionCatalogueRepository().load(operation=operation).get(participation.calculation_revision_id)
    )
    assert revision is not None
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert transaction_id in revision.source_transaction_ids
    assert revision.work_unit_id == participation.work_unit_id
    unit = WorkUnitCatalogueRepository().load().get(participation.work_unit_id)
    assert unit is not None
    assert participation.modelo == str(unit.modelo)
    assert participation.filing_year == unit.filing_year
    assert participation.period == unit.period


def _assert_ledger_participation_lookup_result(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    payload: LedgerParticipationRequest,
    operation_id: str,
    terminal_revision: int,
) -> None:
    participation_result = _resolve_result_projection(
        driver,
        registry,
        definition_id="ledger.participation",
        operation_id=operation_id,
        terminal_revision=terminal_revision,
        projection_type=LedgerParticipationLookupProjection,
    )
    assert isinstance(participation_result, LedgerParticipationLookupProjection)
    transaction_id = resolve_lineage_transaction_id(
        payload.transaction_prefix,
        TransactionCatalogueRepository(bucket_id=str(profile_id)).load(),
    )
    assert participation_result.profile_id == profile_id
    assert participation_result.transaction_prefix == payload.transaction_prefix
    assert participation_result.transaction_id == transaction_id
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transaction_id)
    assert len(index.participations) == 1
    assert participation_result.participations == (
        LedgerParticipationEntryProjection.from_participation(index.participations[0]),
    )
    assert index.participations[0].revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value


def _assert_ledger_participation_rebuild_result(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    operation_id: str,
    terminal_revision: int,
) -> None:
    rebuild_result = _resolve_result_projection(
        driver,
        registry,
        definition_id="ledger.participation.rebuild",
        operation_id=operation_id,
        terminal_revision=terminal_revision,
        projection_type=LedgerParticipationRebuildProjection,
    )
    assert isinstance(rebuild_result, LedgerParticipationRebuildProjection)
    assert rebuild_result.profile_id == profile_id
    assert rebuild_result.transaction_count == 1
    assert rebuild_result.participation_count == 1
    persisted_revisions = CalculationRevisionCatalogueRepository().load(operation=operation).revisions
    assert rebuild_result.revision_count == len(persisted_revisions) > 0
    assert rebuild_result.stale_removed_count == 0
    transactions = tuple(TransactionCatalogueRepository(bucket_id=str(profile_id)).load())
    assert len(transactions) == 1
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transactions[0].transaction_id)
    assert len(index.participations) == 1
    assert index.participations[0].revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value


def _assert_canonical_bulk_classification_update(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    before: Transaction,
    after: Transaction,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    event: BucketEvent,
) -> None:
    """Compare a persisted batch row and event to canonical manual-update meaning."""
    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    command = command_from_patch(
        bucket_id=bucket_id,
        current=before,
        patch=patch,
        actor=actor,
        source_command="aeat app ledger classify --file",
    )
    prepared = prepare_manual_transaction_update(
        current=before,
        command=command,
        previous_transaction_id=before.transaction_id,
        now=event.occurred_at,
        ports=ports,
    )
    assert prepared is not None
    expected_transaction, expected_events = prepared
    assert after == expected_transaction
    assert expected_events == (event,)


def _assert_ledger_review_projection(payload: BaseModel, review: BaseModel, *, profile_id: UUID) -> None:
    assert isinstance(payload, LedgerReviewRequest)
    assert isinstance(review, LedgerReviewProjection)
    assert review.profile_id == profile_id
    assert review.transaction_prefix == payload.transaction_prefix
    assert len(review.rows) == 1
    row = review.rows[0]
    assert row.description == "conformance review seed"
    assert row.status is LedgerReviewStatus.PENDING
    assert row.transaction is not None
    assert row.transaction.description == row.description
    assert payload.transaction_prefix is not None
    assert row.transaction.transaction_id.startswith(payload.transaction_prefix)


def _assert_calculation_report_verification_projection(
    payload: BaseModel, projection: BaseModel, *, profile_id: UUID
) -> None:
    assert isinstance(payload, ModeloCalculationReportVerificationRequest)
    assert isinstance(projection, ModeloCalculationReportVerificationProjection)
    assert projection.profile_id == profile_id == payload.profile_id
    assert projection.source_sha256 == payload.source_sha256
    assert projection.source_sha256 == hashlib.sha256(Path(payload.source_path).read_bytes()).hexdigest()
    assert payload.trusted_public_key_hex is None
    verdict = projection.to_verification()
    assert verdict.outcome is CalculationSummaryVerificationOutcome.REFUSED
    assert verdict.store_checked is False
    assert verdict.signing_key_fingerprint is None
    assert len(verdict.checks) == 1
    check = verdict.checks[0]
    assert check.check is CalculationSummaryCheckName.PDF
    assert check.layer is CalculationSummaryVerificationLayer.DOCUMENT
    assert check.reason is CalculationSummaryVerificationReason.PDF_UNREADABLE
