"""Real-supervisor coverage for exact-profile censal file enrollment."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.user_profile.access_contracts import AccessAction
from ...application.user_profile.capsule_record import ProfileRecordStore
from ...application.user_profile.censal_file_import_operation import (
    CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
    CensalFileImportFact,
    CensalFileImportOperationRequest,
    CensalFileImportOperationResult,
    CensalFileImportProvenance,
)
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.projections import record_to_effective_facts
from ...application.workflow.persistence import WorkflowStateRepository
from ...application.workflow.state_models import WorkflowState
from ...core.config import override_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _CommitWitness:
    """Observe the exact operation identity and guarded persistence calls."""

    def __init__(self) -> None:
        self.profile_id: UUID | None = None
        self.active = False
        self.active_operation_id: str | None = None
        self.events: list[tuple[str, str]] = []
        self.checked_actions: list[AccessAction] = []

    def _assert_exact_identity(self, identity: OperationIdentity) -> None:
        assert self.profile_id is not None
        assert identity.definition_id == CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID
        assert identity.subject_ref == profile_operation_subject(str(self.profile_id))

    async def require[Payload: BaseModel](
        self,
        *,
        identity: OperationIdentity,
        request: OperationRequest[Payload],
        action: AccessAction,
    ) -> None:
        self._assert_exact_identity(identity)
        assert request.definition_id == CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID
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


def test_registered_file_import_refuses_foreign_profile_and_guards_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """The real supervisor fences profile-record and workflow writes as UPDATED."""
    witness = _CommitWitness()
    original_compose = conformance.compose_operation_services
    monkeypatch.setattr(
        conformance,
        "compose_operation_services",
        partial(original_compose, execution_authority=witness),
    )

    original_apply = ProfileRecordRepository.apply_fact_changes

    def guarded_apply_fact_changes(
        repository: ProfileRecordRepository,
        profile_id: str | UUID,
        *,
        facts: tuple[UserProfileFact, ...],
        expected_revision: int,
        expected_content_digest: str,
        event_type: BucketEventType,
        event_payload: Mapping[str, str],
        now: datetime | None = None,
    ) -> UserProfileRecord:
        assert witness.active
        operation_id = witness.active_operation_id
        assert operation_id is not None
        assert str(profile_id) == str(witness.profile_id)
        assert event_type is BucketEventType.CENSO_APPLIED
        witness.events.append(("record-apply", operation_id))
        return original_apply(
            repository,
            profile_id,
            facts=facts,
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
            event_type=event_type,
            event_payload=event_payload,
            now=now,
        )

    monkeypatch.setattr(ProfileRecordRepository, "apply_fact_changes", guarded_apply_fact_changes)

    original_save = WorkflowStateRepository.save

    def guarded_workflow_save(repository: WorkflowStateRepository, state: WorkflowState) -> None:
        assert witness.active
        operation_id = witness.active_operation_id
        assert operation_id is not None
        assert state.active_profile_bucket_id() == str(witness.profile_id)
        witness.events.append(("workflow-save", operation_id))
        original_save(repository, state)

    monkeypatch.setattr(WorkflowStateRepository, "save", guarded_workflow_save)

    _profile_create_context, profile_decode_context = conformance._profile_contexts_for_test()
    with conformance._runtime(
        tmp_path / "censal-file-import",
        cleanup=conformance._CloseWitness(),
    ) as (driver, registry, profile_id):
        witness.profile_id = profile_id
        subject_ref = profile_operation_subject(str(profile_id))
        request = CensalFileImportOperationRequest(
            profile_id=profile_id,
            facts=(
                CensalFileImportFact(
                    path="contact.fiscal_address",
                    value="Calle Mayor 1, Madrid",
                    source=CensalFileImportProvenance.ARTEFACT,
                ),
            ),
        )

        with override_settings(cadrumo_active_profile=str(profile_id)):
            repository = ProfileRecordRepository.for_current_session(
                profile_id,
                profile_decode_context=profile_decode_context,
            )
            record_before = repository.load(profile_id)
            history_before = ProfileRecordStore(session=repository.session).history()

        other_profile_id = uuid4()
        with override_settings(cadrumo_active_profile=str(other_profile_id)):
            refused_submission, refused_observation = asyncio.run(
                driver.run(
                    definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
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
                    definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
            terminal_snapshot = asyncio.run(
                driver.services.submission.supervisor.inspect(submission.receipt.operation_id)
            )
            record_after = repository.load(profile_id)
            history_after = ProfileRecordStore(session=repository.session).history()

        receipt = terminal_snapshot.terminal_receipt
        assert receipt is not None
        assert receipt.identity.definition_id == CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID
        assert receipt.identity.subject_ref == subject_ref
        assert receipt.condition is OperationTerminalCondition.SUCCEEDED
        assert receipt.effect is OperationEffect.UPDATED
        assert receipt.result_ref is not None
        assert observation.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observation.projection.effect is OperationEffect.UPDATED

        projection = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
            operation_id=submission.receipt.operation_id,
            terminal_revision=observation.projection.revision,
            projection_type=CensalFileImportOperationResult,
        )
        assert isinstance(projection, CensalFileImportOperationResult)
        assert projection.profile_id == profile_id
        assert projection.applied is True
        assert projection.fact_paths == ("contact.fiscal_address",)

        assert record_after.profile_id == str(profile_id)
        assert record_after.record_revision == record_before.record_revision + 1
        effective = record_to_effective_facts(record_after)
        assert effective["contact.fiscal_address"].value == "Calle Mayor 1, Madrid"
        assert effective["contact.fiscal_address"].source == CensalFileImportProvenance.ARTEFACT.value
        assert len(history_after) == len(history_before) + 1
        assert history_after[-1].event_type is BucketEventType.CENSO_APPLIED
        assert witness.events == [
            ("commit-enter", submission.receipt.operation_id),
            ("record-apply", submission.receipt.operation_id),
            ("workflow-save", submission.receipt.operation_id),
            ("commit-exit", submission.receipt.operation_id),
        ]
        assert witness.checked_actions.count(AccessAction.START) >= 1
        assert not witness.active
