"""Registered execution coverage for profile-bound reconciliation persistence."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...application.modelo.reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    ModeloReconciliationImportProjection,
    ModeloReconciliationImportRequest,
)
from ...application.modelo.reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
)
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.user_profile.access_contracts import AccessAction
from ...core.config import override_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from . import modelo_operation_test_support
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _CommitWitness:
    """Observe exact operation identity and its guarded persistence boundary."""

    def __init__(self, definition_id: str = MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID) -> None:
        self.definition_id = definition_id
        self.profile_id: UUID | None = None
        self.active = False
        self.active_operation_id: str | None = None
        self.events: list[tuple[str, str]] = []
        self.checked_actions: list[AccessAction] = []

    def _assert_exact_identity(self, identity: OperationIdentity) -> None:
        assert self.profile_id is not None
        assert identity.definition_id == self.definition_id
        assert identity.subject_ref == profile_operation_subject(str(self.profile_id))

    async def require[Payload: BaseModel](
        self,
        *,
        identity: OperationIdentity,
        request: OperationRequest[Payload],
        action: AccessAction,
    ) -> None:
        self._assert_exact_identity(identity)
        assert request.definition_id == self.definition_id
        assert request.subject_ref == identity.subject_ref
        assert getattr(request.payload, "profile_id", None) == self.profile_id
        self.checked_actions.append(action)

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        self._assert_exact_identity(identity)
        assert not self.active
        self.active = True
        self.active_operation_id = identity.operation_id
        self.events.append(("commit-enter", identity.operation_id))
        try:
            yield
        finally:
            self.events.append(("commit-exit", identity.operation_id))
            self.active_operation_id = None
            self.active = False


def test_registered_import_checks_exact_profile_and_guards_atomic_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """The real registered executor refuses retargeting and settles its write as UPDATED."""
    witness = _CommitWitness()
    original_compose = conformance.compose_operation_services
    monkeypatch.setattr(
        conformance,
        "compose_operation_services",
        partial(original_compose, execution_authority=witness),
    )

    original_persist = ModeloReconciliationPersistence.persist_with_event

    def guarded_persist(
        persistence: ModeloReconciliationPersistence,
        record: ModeloReconciliationRecord,
        event: BucketEvent,
    ) -> None:
        assert witness.active
        assert witness.active_operation_id is not None
        assert record.bucket_id == str(witness.profile_id)
        assert record.bucket_event_id == event.event_id
        witness.events.append(("atomic-persist", event.event_id))
        original_persist(persistence, record, event)

    monkeypatch.setattr(ModeloReconciliationPersistence, "persist_with_event", guarded_persist)

    with conformance._runtime(tmp_path / "modelo-reconciliation-import", cleanup=conformance._CloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        witness.profile_id = profile_id
        subject_ref = profile_operation_subject(str(profile_id))
        with override_settings(cadrumo_active_profile=str(profile_id)):
            work_unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            records_before = tuple(ModeloReconciliationPersistence().iter_records())
            events_before = BucketEventHistoryRepository().load().events

        request = ModeloReconciliationImportRequest(
            profile_id=profile_id,
            work_unit_id=work_unit.work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=str(
                Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
            ),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        )

        other_profile_id = uuid4()
        with override_settings(cadrumo_active_profile=str(other_profile_id)):
            refused_submission, refused_observation = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
        refused_snapshot = asyncio.run(
            driver.services.submission.supervisor.inspect(refused_submission.receipt.operation_id)
        )
        refused_receipt = refused_snapshot.terminal_receipt
        assert refused_receipt is not None
        assert refused_receipt.identity.subject_ref == subject_ref
        assert refused_receipt.condition is OperationTerminalCondition.REFUSED
        assert refused_receipt.effect is OperationEffect.NONE
        assert refused_receipt.result_ref is None
        assert refused_observation.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert witness.events == []

        with override_settings(cadrumo_active_profile=str(profile_id)):
            submission, observation = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
            terminal_snapshot = asyncio.run(
                driver.services.submission.supervisor.inspect(submission.receipt.operation_id)
            )
            records_after = tuple(ModeloReconciliationPersistence().iter_records())
            events_after = BucketEventHistoryRepository().load().events

        receipt = terminal_snapshot.terminal_receipt
        assert receipt is not None
        assert receipt.identity.definition_id == MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID
        assert receipt.identity.subject_ref == subject_ref
        assert receipt.condition is OperationTerminalCondition.SUCCEEDED
        assert receipt.effect is OperationEffect.UPDATED
        assert receipt.result_ref is not None
        assert observation.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observation.projection.effect is OperationEffect.UPDATED

        projection = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
            operation_id=submission.receipt.operation_id,
            terminal_revision=observation.projection.revision,
            projection_type=ModeloReconciliationImportProjection,
        )
        assert isinstance(projection, ModeloReconciliationImportProjection)
        assert projection.bucket_id == str(profile_id)
        assert projection.work_unit_id == work_unit.work_unit_id
        assert projection.source_path == request.source_path

        assert records_after[: len(records_before)] == records_before
        assert len(records_after) == len(records_before) + 1
        persisted = records_after[-1]
        assert persisted.bucket_id == str(profile_id)
        assert persisted.work_unit_id == work_unit.work_unit_id
        assert persisted.bucket_event_id in events_after
        assert set(events_before).issubset(events_after)
        assert witness.checked_actions.count(AccessAction.START) >= 2
        assert witness.events[:3] == [
            ("commit-enter", submission.receipt.operation_id),
            ("atomic-persist", persisted.bucket_event_id),
            ("commit-exit", submission.receipt.operation_id),
        ]
        assert not witness.active
