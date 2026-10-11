"""The four repair operations through their real executors and resolvers over a real encrypted profile."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import AnyHttpUrl, BaseModel

from ...adapters.outbound.aeat.browser.site_health_records import SiteHealthEvidence, SiteHealthStatus
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.secure_object_namespaces import (
    TEST_RUNTIME_PROFILE_NAMESPACE,
    TEST_SESSION_LIFECYCLE_NAMESPACE,
)
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.diagnostics_repair import WORKFLOW_PROGRESS_RESET_ACTOR
from ...application.diagnostics_repair_documents import (
    RepairConnectivityDocument,
    RepairIntegrityObjectsDocument,
    RepairQuarantineDocument,
    RepairResetProgressDocument,
)
from ...application.diagnostics_repair_operations import (
    CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
    SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
    SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
    WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
    ConnectivityProbeRequest,
    SecureObjectsCheckRequest,
    SecureObjectsQuarantineRequest,
    WorkflowProgressResetRequest,
    build_connectivity_probe_definition,
)
from ...application.ledger.tests.bulk_classify_operation_support import CommitFence, EffectEvents, PrivateOperands
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.execution_actor import OperationExecutionCaller
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.operations.subject_reference import OperationSubjectReferenceV1
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    SessionKind,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.workflow.persistence import workflow_state_repository
from ...application.workflow.state_models import WorkflowState
from ...core.errors.hierarchy import SiteHealthState
from ...core.operations import OperationEffect, profile_operation_subject
from ...domain.buckets.event import BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..diagnostics_repair_composition import DiagnosticsRepairOperations, build_diagnostics_repair_operations

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("93939393-9393-4393-8393-939393939393")
_SOUND_NAMESPACE = TEST_SESSION_LIFECYCLE_NAMESPACE.namespace
_TORN_NAMESPACE = TEST_RUNTIME_PROFILE_NAMESPACE.namespace
_SEEDED_PROGRESS_AT = datetime(2026, 4, 2, 9, 30, 11, tzinfo=UTC)
_AGENT_CLIENT = UUID("a4a4a4a4-a4a4-44a4-84a4-a4a4a4a4a4a4")
_OBSERVED = SiteHealthStatus(
    state=SiteHealthState.MANTENIMIENTO,
    evidence=SiteHealthEvidence(
        url=AnyHttpUrl("https://probe.example.org/"),
        http_status=503,
        html_fragment="<html>synthetic maintenance page</html>",
        detected_markers=("mantenimiento", "retry-after:120"),
    ),
    observed_at=datetime(2026, 4, 2, 9, 31, 0, tzinfo=UTC),
    retry_after_seconds=120,
)


class _Run:
    """One executor run's journal facts, commit fence and retained result."""

    def __init__(self, definition_id: str, operation: PinnedAuthorityOperation) -> None:
        self.fence, self.events, self.operands = CommitFence(), EffectEvents(), PrivateOperands()
        self.context = cast(
            OperationExecutorContext,
            cast(
                object,
                SimpleNamespace(
                    identity=OperationIdentity(
                        operation_id="a" * 64,
                        definition_id=definition_id,
                        subject_ref=profile_operation_subject(str(_PROFILE)),
                    ),
                    authority_operation=operation,
                    cancellation=self.fence,
                    events=self.events,
                    operands=self.operands,
                ),
            ),
        )


def _request(definition_id: str, payload: BaseModel, *, profile: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(profile)), payload=payload
    )


def _definition(operations: DiagnosticsRepairOperations, definition_id: str) -> OperationDefinition:
    return next(item for item in operations.definitions if item.definition_id == definition_id)


def _execute[ResultT: BaseModel](
    definition: OperationDefinition, payload: BaseModel, operation: PinnedAuthorityOperation, result_type: type[ResultT]
) -> tuple[ResultT, _Run]:
    run = _Run(definition.definition_id, operation)
    asyncio.run(definition.executor_factory.create().execute(_request(definition.definition_id, payload), run.context))
    (result,) = run.operands.values
    assert isinstance(result, result_type)
    return result, run


@contextmanager
def _profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """One real encrypted profile, its session open, with the workflow store composed."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        composed_profile_persistence_ports(),
    ):
        yield profile


def _seed_rows(profile: TestRuntimeProfile) -> None:
    """Store one sound row and one row whose ciphertext no longer authenticates."""
    for definition in (TEST_SESSION_LIFECYCLE_NAMESPACE, TEST_RUNTIME_PROFILE_NAMESPACE):
        profile.repository.save(
            namespace=definition.namespace,
            object_key=definition.object_key_grammar,
            classification=definition.sensitivity,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=f"synthetic-{definition.key}".encode(),
        )
    with sqlite3.connect(profile.paths.database_file) as connection:
        row_id, payload = connection.execute(
            "SELECT id, payload FROM secure_objects WHERE namespace = ? ORDER BY id DESC LIMIT 1", (_TORN_NAMESPACE,)
        ).fetchone()
        connection.execute(
            "UPDATE secure_objects SET payload = ? WHERE id = ?", (payload[:-1] + bytes([payload[-1] ^ 0xFF]), row_id)
        )
    connection.close()


def _stored_rows(profile: TestRuntimeProfile) -> tuple[int, int]:
    """Count the live rows of the seeded namespaces and the rows held in quarantine."""
    with sqlite3.connect(profile.paths.database_file) as connection:
        live = connection.execute(
            "SELECT COUNT(*) FROM secure_objects WHERE namespace IN (?, ?)", (_SOUND_NAMESPACE, _TORN_NAMESPACE)
        ).fetchone()[0]
        archive = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'secure_objects_quarantine'"
        ).fetchone()
        held = (
            0 if archive is None else connection.execute("SELECT COUNT(*) FROM secure_objects_quarantine").fetchone()[0]
        )
    connection.close()
    return int(live), int(held)


def _counts(result: RepairIntegrityObjectsDocument | RepairQuarantineDocument) -> dict[str, tuple[int, int]]:
    return {
        row.namespace: (row.readable, row.unreadable)
        for row in result.namespaces or ()
        if row.namespace in {_SOUND_NAMESPACE, _TORN_NAMESPACE}
    }


def _progress_saved() -> bool:
    return secure_object_repository_for_active_bucket().exists("cadrumo.workflow", "state")


def _reset_actors() -> list[str]:
    return [
        event.payload["actor"]
        for event in BucketEventHistoryRepository().load().events.values()
        if event.event_type is BucketEventType.WORKFLOW_STATE_RESET
    ]


def test_the_family_registers_closed_schemas_profile_subjects_and_the_effects_each_may_leave() -> None:
    operations = build_diagnostics_repair_operations()
    registry = OperationRegistry(definitions=operations.definitions, public_registrations=operations.registrations)
    reads = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})

    assert [item.definition_id for item in operations.definitions] == [
        CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
        SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
        SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
        WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
    ]
    for definition in operations.definitions:
        contract = registry.lookup_public_registration(definition.definition_id).contract
        assert contract.result_schema is not None
        assert definition.subject_reference == OperationSubjectReferenceV1.profile()
        changes = definition.definition_id in {
            SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
            WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
        }
        expected = reads | {OperationEffect.UPDATED} if changes else reads
        assert definition.capabilities.permitted_effects == expected


def test_the_check_counts_the_torn_row_judges_it_and_moves_nothing(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    definition = _definition(build_diagnostics_repair_operations(), SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID)

    with _profile(tmp_path) as profile:
        _seed_rows(profile)
        whole, run = _execute(
            definition,
            SecureObjectsCheckRequest(profile_id=_PROFILE),
            authority_operation,
            RepairIntegrityObjectsDocument,
        )
        sound, _ = _execute(
            definition,
            SecureObjectsCheckRequest(profile_id=_PROFILE, namespace=_SOUND_NAMESPACE),
            authority_operation,
            RepairIntegrityObjectsDocument,
        )
        torn, _ = _execute(
            definition,
            SecureObjectsCheckRequest(profile_id=_PROFILE, namespace=_TORN_NAMESPACE),
            authority_operation,
            RepairIntegrityObjectsDocument,
        )
        absent, _ = _execute(
            definition,
            SecureObjectsCheckRequest(profile_id=_PROFILE, namespace="cadrumo-test.repair.nothing-here"),
            authority_operation,
            RepairIntegrityObjectsDocument,
        )
        stored = _stored_rows(profile)

    assert _counts(whole) == {_SOUND_NAMESPACE: (1, 0), _TORN_NAMESPACE: (0, 1)}
    assert whole.unreadable_total == 1
    assert whole.readable_total == sum(row.readable for row in whole.namespaces)
    assert (whole.check.status, whole.check.summary) == ("fail", "1 unreadable secure-object rows")
    assert (sound.check.status, sound.readable_total, sound.unreadable_total) == ("ok", 1, 0)
    assert [row.namespace for row in sound.namespaces] == [_SOUND_NAMESPACE]
    assert (torn.check.status, torn.readable_total, torn.unreadable_total) == ("fail", 0, 1)
    assert (absent.check.status, absent.namespaces, absent.readable_total) == ("ok", (), 0)
    assert absent.unreadable_total == 0
    assert run.events.effects == [OperationEffect.NONE]
    assert run.events.phases == [SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID]
    assert run.fence.entries == 0
    assert stored == (2, 0)


def test_the_quarantine_previews_without_a_commit_and_then_moves_only_the_torn_row(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    definition = _definition(build_diagnostics_repair_operations(), SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID)

    with _profile(tmp_path) as profile:
        _seed_rows(profile)
        preview, previewed = _execute(
            definition,
            SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=True),
            authority_operation,
            RepairQuarantineDocument,
        )
        after_preview = _stored_rows(profile)
        moved, committed = _execute(
            definition,
            SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=False),
            authority_operation,
            RepairQuarantineDocument,
        )
        after_commit = _stored_rows(profile)
        again, repeated = _execute(
            definition,
            SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=False),
            authority_operation,
            RepairQuarantineDocument,
        )
        after_repeat = _stored_rows(profile)

    assert preview.dry_run and _counts(preview) == {_SOUND_NAMESPACE: (1, 0), _TORN_NAMESPACE: (0, 1)}
    assert (previewed.events.effects, previewed.fence.entries) == ([OperationEffect.NONE], 0)
    assert after_preview == (2, 0)
    assert not moved.dry_run and moved.unreadable_total == 1
    assert _counts(moved) == _counts(preview)
    assert (committed.events.effects, committed.fence.entries) == (
        [OperationEffect.UNKNOWN, OperationEffect.UPDATED],
        1,
    )
    assert after_commit == (1, 1)
    assert again.unreadable_total == 0
    assert repeated.events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert after_repeat == (1, 1)


@pytest.mark.parametrize("frontend", list(OperationFrontendProjection))
def test_the_reset_describes_the_saved_progress_and_then_discards_it_under_the_sessions_actor(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    asked: list[OperationIdentity] = []

    def caller(identity: OperationIdentity) -> OperationExecutionCaller:
        asked.append(identity)
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.API_KEY, client_id=_AGENT_CLIENT)

    definition = _definition(
        build_diagnostics_repair_operations(execution_caller_reader=caller),
        WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
    )

    with _profile(tmp_path):
        workflow_state_repository().save(WorkflowState(updated_at=_SEEDED_PROGRESS_AT))
        described, previewed = _execute(
            definition,
            WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=True),
            authority_operation,
            RepairResetProgressDocument,
        )
        kept, actors_after_preview = _progress_saved(), _reset_actors()
        discarded, committed = _execute(
            definition,
            WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=False),
            authority_operation,
            RepairResetProgressDocument,
        )
        gone, actors = not _progress_saved(), _reset_actors()
        reloaded = workflow_state_repository().load()

    assert described.dry_run is True and described.fingerprint is not None
    assert described.fingerprint.reason_class == "readable"
    assert described.fingerprint.byte_length is not None and described.fingerprint.byte_length > 0
    # The result carries the real identifier of the profile whose progress it describes.
    assert described.fingerprint.recovered_bucket_id == str(_PROFILE)
    assert kept and actors_after_preview == []
    assert (previewed.events.effects, previewed.fence.entries) == ([OperationEffect.NONE], 0)
    assert discarded.dry_run is False
    assert discarded.fingerprint == described.fingerprint
    assert (committed.events.effects, committed.fence.entries) == (
        [OperationEffect.UNKNOWN, OperationEffect.UPDATED],
        1,
    )
    assert gone
    assert reloaded.model_dump(exclude={"updated_at"}) == WorkflowState().model_dump(exclude={"updated_at"})
    # The actor is attribution: an agent's reset is recorded as its session, and nothing else differs.
    expected_actor = (
        f"agent:mcp.{SessionKind.API_KEY.value}.{_AGENT_CLIENT}"
        if frontend is OperationFrontendProjection.MCP
        else WORKFLOW_PROGRESS_RESET_ACTOR
    )
    assert actors == [expected_actor]
    assert [identity.definition_id for identity in asked] == [WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID]


def test_the_probe_reports_what_the_bound_browser_observed_and_leaves_no_effect(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    probes: list[str] = []

    def observe() -> SiteHealthStatus:
        probes.append("probed")
        return _OBSERVED

    definition = build_connectivity_probe_definition(observe)

    with _profile(tmp_path):
        result, run = _execute(
            definition, ConnectivityProbeRequest(profile_id=_PROFILE), authority_operation, RepairConnectivityDocument
        )

    assert probes == ["probed"]
    assert (result.target, result.status.state) == ("aeat_sede", "mantenimiento")
    assert result.status.retry_after_seconds == 120
    assert (result.status.evidence.http_status, result.status.evidence.detected_markers) == (
        503,
        ("mantenimiento", "retry-after:120"),
    )
    assert result.status.observed_at == _OBSERVED.model_dump(mode="json")["observed_at"]
    assert (run.events.effects, run.fence.entries) == ([OperationEffect.NONE], 0)


@pytest.mark.parametrize(
    ("definition_id", "payload"),
    [
        (SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID, SecureObjectsCheckRequest(profile_id=uuid4())),
        (
            SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
            SecureObjectsQuarantineRequest(profile_id=uuid4(), dry_run=False),
        ),
        (
            WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
            WorkflowProgressResetRequest(profile_id=uuid4(), dry_run=False),
        ),
        (CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID, ConnectivityProbeRequest(profile_id=uuid4())),
    ],
)
def test_an_executor_refuses_a_request_for_a_profile_its_worker_does_not_hold(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, definition_id: str, payload: BaseModel
) -> None:
    definition = _definition(build_diagnostics_repair_operations(), definition_id)
    run = _Run(definition_id, authority_operation)
    foreign = cast(UUID, payload.model_dump()["profile_id"])

    with _profile(tmp_path) as profile:
        _seed_rows(profile)
        with pytest.raises(ProfileAccessRefusedError) as refused:
            asyncio.run(
                definition.executor_factory.create().execute(
                    _request(definition_id, payload, profile=foreign), run.context
                )
            )
        stored = _stored_rows(profile)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert (run.operands.values, run.events.effects, run.fence.entries) == ([], [], 0)
    assert stored == (2, 0)


_RESOLVED_REQUESTS: tuple[tuple[str, BaseModel, bool], ...] = (
    (SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID, SecureObjectsCheckRequest(profile_id=_PROFILE), False),
    (
        SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
        SecureObjectsCheckRequest(profile_id=_PROFILE, namespace=_TORN_NAMESPACE),
        False,
    ),
    (
        SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
        SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=True),
        False,
    ),
    (
        SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
        SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=False),
        True,
    ),
    (
        WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
        WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=True),
        False,
    ),
    (
        WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
        WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=False),
        True,
    ),
    (CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID, ConnectivityProbeRequest(profile_id=_PROFILE), False),
)


@pytest.mark.parametrize(("definition_id", "payload", "commits"), _RESOLVED_REQUESTS)
def test_each_resolver_gives_the_three_frontends_the_same_decision(
    definition_id: str, payload: BaseModel, commits: bool
) -> None:
    operations = build_diagnostics_repair_operations()
    registry = OperationRegistry(definitions=operations.definitions, public_registrations=operations.registrations)
    contract = registry.lookup_public_registration(definition_id).contract
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )
    request = _request(definition_id, payload)

    for action in (AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT):
        on_cli = resolve_operation_access(registry=registry, request=request, context=replace(context, action=action))
        assert (AccessAction.COMMIT in on_cli.policy.actions) is commits
        assert on_cli.request.period_independent and not on_cli.request.periods
        assert not on_cli.policy.requires_human
        if action is AccessAction.RESULT:
            assert {row.category for row in on_cli.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
        for frontend in OperationFrontendProjection:
            on_frontend = resolve_operation_access(
                registry=registry, request=request, context=replace(context, action=action, frontend=frontend)
            )
            assert on_frontend.policy == on_cli.policy, (action, frontend)
            assert on_frontend.request == on_cli.request.model_copy(update={"frontend": frontend}), (action, frontend)

    # Another profile's request is refused, and refused alike wherever it was submitted.
    stranger = uuid4()
    foreign = _request(definition_id, payload.model_copy(update={"profile_id": stranger}), profile=stranger)
    for frontend in OperationFrontendProjection:
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=foreign, context=replace(context, frontend=frontend))
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH, frontend
