"""The two Google stored-record reads serve any session; every other Google leaf takes a person's, on any frontend."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.operations import profile_guard
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.user_profile import google_configuration_operation as worker
from cadrumo.application.user_profile import google_configuration_operation_contracts as contracts
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDecision,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.google_configuration_executor import GoogleConfigurationExecutor
from cadrumo.application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
    GoogleConfigurationOperationPorts,
    GoogleConfigurationRun,
)
from cadrumo.application.user_profile.google_configuration_result_projection import project_google_configuration_result
from cadrumo.application.user_profile.operation_access_policy import evaluate_operation_access
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_harness.mcp.access_scope import surface_scope
from cadrumo_harness.mcp.surfaces import MCP_SURFACES, McpSurfaceName

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("38383838-3838-4383-8383-383838383838")
_NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
_PIN = cast(PinnedAuthorityOperation, object())
_CLI = OperationFrontendProjection.CLI
_MCP = OperationFrontendProjection.EXTERNAL_CLIENT

_STORED_RECORD_READS: tuple[tuple[str, contracts.GoogleConfigurationRequest], ...] = (
    (contracts.GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, contracts.GoogleFolderViewRequest(profile_id=_PROFILE)),
    (contracts.GOOGLE_STATUS_OPERATION_DEFINITION_ID, contracts.GoogleStatusRequest(profile_id=_PROFILE)),
)
_PERSON_LEAVES: tuple[tuple[str, contracts.GoogleConfigurationRequest], ...] = (
    (
        contracts.GOOGLE_FOLDER_ORGANIZE_OPERATION_DEFINITION_ID,
        contracts.GoogleFolderOrganizeRequest(profile_id=_PROFILE),
    ),
    (contracts.GOOGLE_LOGIN_OPERATION_DEFINITION_ID, contracts.GoogleLoginRequest(profile_id=_PROFILE)),
    (contracts.GOOGLE_LOGOUT_OPERATION_DEFINITION_ID, contracts.GoogleLogoutRequest(profile_id=_PROFILE)),
    (contracts.GOOGLE_PROBE_OPERATION_DEFINITION_ID, contracts.GoogleProbeRequest(profile_id=_PROFILE)),
)


def _unopened(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleConfigurationOperationPorts:
    raise AssertionError(f"access resolution constructed Google capabilities for {profile_id} under {operation!r}")


def _registered(definition_id: str) -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = next(
        item for item in worker.build_google_configuration_definitions(_unopened) if item.definition_id == definition_id
    )
    registration = worker.build_google_configuration_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _decision(
    definition_id: str,
    payload: contracts.GoogleConfigurationRequest,
    *,
    frontend: OperationFrontendProjection,
    kind: SessionKind,
    actions: frozenset[AccessAction] = frozenset(AccessAction),
    surface: McpSurfaceName | None = None,
) -> AccessDecision:
    """Resolve the request as its owner does, then evaluate it for one session of the given kind.

    ``actions`` is what the session, its grant and the profile hold; ``surface``
    selects the harness ceiling applied to the session's explicit generic scope.
    """
    registry, registration = _registered(definition_id)
    client_id, boot, connection_id = uuid4(), uuid4(), uuid4()
    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
        ),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=client_id,
            action=AccessAction.SUBMIT,
            frontend=frontend,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        ),
    )
    scope = AccessScope(
        operations=frozenset({definition_id}),
        actions=actions,
        disclosures=resolved.policy.disclosures,
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    session_scope = scope
    if surface is not None:
        ceiling = surface_scope(MCP_SURFACES[surface])
        session_scope = scope.model_copy(
            update={
                "operations": scope.operations & ceiling.operations,
                "actions": scope.actions & ceiling.actions,
                "allow_changes_records": ceiling.allow_changes_records,
                "allow_network": ceiling.allow_network,
            }
        )
    binding = ProfileAccessBinding(
        profile_id=_PROFILE,
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    grant: AutomationGrant | None = None
    key: ApiKeyRecord | None = None
    if kind is SessionKind.API_KEY:
        grant = AutomationGrant(
            grant_id=uuid4(),
            binding=binding,
            client_id=client_id,
            generation=1,
            profile_lock_generation=0,
            state=AuthorityState.ACTIVE,
            scope=scope,
            valid_from=_NOW - timedelta(days=1),
            expires_at=_NOW + timedelta(days=1),
            unattended=True,
            allow_os_lock=True,
        )
        key = ApiKeyRecord(
            key_id=uuid4(),
            grant_id=grant.grant_id,
            binding=binding,
            generation=1,
            state=AuthorityState.ACTIVE,
            valid_from=grant.valid_from,
            expires_at=grant.expires_at,
        )
        session = AccessSession(
            session_id=uuid4(),
            binding=binding,
            profile_lock_generation=0,
            runtime_boot_id=boot,
            connection_id=connection_id,
            client_id=client_id,
            kind=SessionKind.API_KEY,
            state=SessionState.ACTIVE,
            scope=session_scope,
            grant_id=grant.grant_id,
            grant_generation=grant.generation,
            key_id=key.key_id,
            key_generation=key.generation,
            issued_at=_NOW,
            expires_at=_NOW + timedelta(minutes=5),
            issued_monotonic=100.0,
        )
    else:
        session = AccessSession(
            session_id=uuid4(),
            binding=binding,
            profile_lock_generation=0,
            runtime_boot_id=boot,
            connection_id=connection_id,
            client_id=client_id,
            kind=SessionKind.HUMAN,
            originating_login_id="login-a",
            state=SessionState.ACTIVE,
            scope=session_scope,
            issued_at=_NOW,
            expires_at=_NOW + timedelta(minutes=5),
            issued_monotonic=100.0,
        )
    return evaluate_operation_access(
        request=resolved.request,
        policy=resolved.policy,
        registry=registry,
        session=session,
        ancestors=(),
        grant=grant,
        key=key,
        profile=ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=scope,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        context=AccessEvaluationContext(
            now=_NOW,
            monotonic_now=100.0,
            clock_rollback_detected=False,
            runtime_boot_id=boot,
            connection_id=connection_id,
            authenticated_client_id=client_id,
            login_contexts=(
                OsLoginContext(
                    login_id="login-a",
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    lock_state=OsLockState.UNLOCKED,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        ),
    )


@pytest.mark.parametrize(("definition_id", "payload"), _STORED_RECORD_READS)
@pytest.mark.parametrize("frontend", list(OperationFrontendProjection))
@pytest.mark.parametrize("kind", [SessionKind.HUMAN, SessionKind.API_KEY])
def test_a_stored_record_read_is_admitted_under_the_sign_in_and_under_an_enrolled_key(
    definition_id: str,
    payload: contracts.GoogleConfigurationRequest,
    frontend: OperationFrontendProjection,
    kind: SessionKind,
) -> None:
    assert isinstance(_decision(definition_id, payload, frontend=frontend, kind=kind), AccessAllowed)


@pytest.mark.parametrize("frontend", list(OperationFrontendProjection))
@pytest.mark.parametrize(("definition_id", "payload"), _PERSON_LEAVES)
def test_every_other_google_leaf_takes_the_persons_session_and_refuses_an_enrolled_key_on_every_frontend(
    definition_id: str, payload: contracts.GoogleConfigurationRequest, frontend: OperationFrontendProjection
) -> None:
    assert _decision(definition_id, payload, frontend=frontend, kind=SessionKind.API_KEY) == AccessDenied(
        code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
    )
    # The sign-in session is of the human kind on every frontend.
    assert isinstance(_decision(definition_id, payload, frontend=frontend, kind=SessionKind.HUMAN), AccessAllowed)


def _receipt(definition_id: str) -> tuple[OperationIdentity, OperationTerminalReceipt]:
    identity = OperationIdentity(
        operation_id="a" * 64, definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE))
    )
    return identity, OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
        result_ref="d" * 64,
    )


def _succeeded(
    identity: OperationIdentity, projection: contracts.GoogleConfigurationProjection
) -> contracts.GoogleConfigurationExecutionResult:
    return contracts.GoogleConfigurationExecutionResult(
        identity=identity,
        projection=contracts.GoogleConfigurationOutcome(profile_id=_PROFILE, outcome="succeeded", result=projection),
        effect="none",
    )


def test_the_released_stored_records_declare_no_field_that_could_hold_a_credential() -> None:
    assert set(contracts.GoogleFolderViewProjection.model_fields) == {"profile_id", "configured", "root_folder_id"}
    assert set(contracts.GoogleStatusProjection.model_fields) == {
        "profile_id",
        "session_present",
        "account_email",
        "granted_scopes",
        "issued_at",
    }


def test_the_projector_releases_each_read_only_as_its_own_stored_record() -> None:
    status_identity, status_receipt = _receipt(contracts.GOOGLE_STATUS_OPERATION_DEFINITION_ID)
    folder_identity, folder_receipt = _receipt(contracts.GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID)
    status = contracts.GoogleStatusProjection(
        profile_id=_PROFILE,
        session_present=True,
        account_email="persona@example.invalid",
        granted_scopes=("https://www.googleapis.com/auth/drive.file",),
        issued_at="2026-10-01T09:00:00+00:00",
    )
    folder = contracts.GoogleFolderViewProjection(
        profile_id=_PROFILE, configured=True, root_folder_id="synthetic-root-folder"
    )
    probe = contracts.GoogleProbeProjection(
        profile_id=_PROFILE,
        reachable=False,
        writable=False,
        read_only=True,
        root_folder_id="synthetic-root-folder",
        detail="service unreachable: synthetic provider failure text",
    )

    released_status = project_google_configuration_result(_succeeded(status_identity, status), status_receipt)
    released_folder = project_google_configuration_result(_succeeded(folder_identity, folder), folder_receipt)

    assert isinstance(released_status, contracts.GoogleConfigurationOutcome) and released_status.result == status
    assert isinstance(released_folder, contracts.GoogleConfigurationOutcome) and released_folder.result == folder
    # A read's receipt releases its own record alone, so the probe's failure
    # text cannot leave under a read an automation may run.
    for identity, receipt in ((status_identity, status_receipt), (folder_identity, folder_receipt)):
        with pytest.raises(ValueError):
            project_google_configuration_result(_succeeded(identity, probe), receipt)
    with pytest.raises(ValueError):
        project_google_configuration_result(_succeeded(status_identity, folder), status_receipt)


_WITHOUT_COMMIT = frozenset(AccessAction) - {AccessAction.COMMIT}


def _submission_actions(
    definition_id: str, payload: contracts.GoogleConfigurationRequest, frontend: OperationFrontendProjection
) -> frozenset[AccessAction]:
    registry, registration = _registered(definition_id)
    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
        ),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=frontend,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        ),
    )
    return resolved.policy.actions


def test_only_the_stored_record_reads_resolve_no_commit_door_and_declare_a_read() -> None:
    reading = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    for definition_id, payload in _STORED_RECORD_READS:
        _registry, registration = _registered(definition_id)
        for frontend in (_CLI, _MCP):
            assert AccessAction.COMMIT not in _submission_actions(definition_id, payload, frontend)
        assert registration.contract.permitted_effects == reading
    for definition_id, payload in _PERSON_LEAVES:
        _registry, registration = _registered(definition_id)
        assert AccessAction.COMMIT in _submission_actions(definition_id, payload, _CLI)
        assert registration.contract.permitted_effects == frozenset(OperationEffect)


@pytest.mark.parametrize(("definition_id", "payload"), _STORED_RECORD_READS)
@pytest.mark.parametrize("kind", [SessionKind.HUMAN, SessionKind.API_KEY])
def test_a_stored_record_read_is_admitted_on_mcp_for_a_session_whose_scope_holds_no_commit(
    definition_id: str, payload: contracts.GoogleConfigurationRequest, kind: SessionKind
) -> None:
    decision = _decision(definition_id, payload, frontend=_MCP, kind=kind, actions=_WITHOUT_COMMIT)

    assert isinstance(decision, AccessAllowed)


@pytest.mark.parametrize(("definition_id", "payload"), _PERSON_LEAVES)
def test_every_other_google_leaf_is_refused_at_submission_without_the_commit_it_can_reach(
    definition_id: str, payload: contracts.GoogleConfigurationRequest
) -> None:
    decision = _decision(definition_id, payload, frontend=_CLI, kind=SessionKind.HUMAN, actions=_WITHOUT_COMMIT)

    assert decision == AccessDenied(code=AccessDenialCode.OPERATION_DENIED)


@pytest.mark.parametrize(("definition_id", "payload"), _STORED_RECORD_READS)
@pytest.mark.parametrize("kind", [SessionKind.HUMAN, SessionKind.API_KEY])
@pytest.mark.parametrize("actions", [frozenset(AccessAction), _WITHOUT_COMMIT], ids=["every-action", "no-commit"])
def test_a_stored_record_read_is_admitted_at_submission_on_the_read_only_local_surface(
    definition_id: str,
    payload: contracts.GoogleConfigurationRequest,
    kind: SessionKind,
    actions: frozenset[AccessAction],
) -> None:
    surface = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
    assert not surface.changes_records and surface.admits(definition_id)

    decision = _decision(
        definition_id, payload, frontend=_MCP, kind=kind, actions=actions, surface=McpSurfaceName.READ_ONLY_LOCAL
    )

    assert isinstance(decision, AccessAllowed)


def test_the_read_only_local_surface_still_refuses_a_google_leaf_that_is_not_a_stored_record_read() -> None:
    definition_id, payload = _PERSON_LEAVES[-1]
    assert definition_id == contracts.GOOGLE_PROBE_OPERATION_DEFINITION_ID

    decision = _decision(
        definition_id, payload, frontend=_MCP, kind=SessionKind.HUMAN, surface=McpSurfaceName.READ_ONLY_LOCAL
    )

    assert decision == AccessDenied(code=AccessDenialCode.OPERATION_DENIED)


class _UnopenedCommitSection:
    """A commit section that a read must never open."""

    def irreversible_section(self) -> AbstractAsyncContextManager[None]:
        raise AssertionError("a stored-record read opened an irreversible section")


class _RecordedEvents:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        assert phase.startswith("config.google.")

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _RecordedOperands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "d" * 64


def _registered_executor(definition_id: str, run: GoogleConfigurationRun) -> GoogleConfigurationExecutor:
    """Build the executor the registered definition builds, over one synthetic record reader."""

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleConfigurationOperationPorts:
        return GoogleConfigurationOperationPorts(profile_id, operation, run, lambda: None)

    definition = next(
        item for item in worker.build_google_configuration_definitions(factory) if item.definition_id == definition_id
    )
    executor = definition.executor_factory.build()
    assert isinstance(executor, GoogleConfigurationExecutor)
    return executor


def _read_execution(
    definition_id: str, payload: contracts.GoogleConfigurationRequest
) -> tuple[OperationRequest[BaseModel], OperationExecutorContext, _RecordedEvents, _RecordedOperands]:
    request = OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
    )
    events, operands = _RecordedEvents(), _RecordedOperands()
    context = SimpleNamespace(
        identity=OperationIdentity(operation_id="a" * 64, definition_id=definition_id, subject_ref=request.subject_ref),
        revision=0,
        authority_operation=_PIN,
        events=events,
        operands=operands,
        cancellation=_UnopenedCommitSection(),
    )
    return request, cast(OperationExecutorContext, cast(object, context)), events, operands


@pytest.mark.asyncio
async def test_the_registered_status_read_stores_its_record_without_opening_a_commit_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    status = contracts.GoogleStatusProjection(
        profile_id=_PROFILE,
        session_present=True,
        account_email="persona@example.invalid",
        granted_scopes=("https://www.googleapis.com/auth/drive.file",),
        issued_at="2026-10-01T09:00:00+00:00",
    )

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        assert isinstance(request, contracts.GoogleStatusRequest) and terminal_admission is None
        return status

    definition_id = contracts.GOOGLE_STATUS_OPERATION_DEFINITION_ID
    request, context, events, operands = _read_execution(
        definition_id, contracts.GoogleStatusRequest(profile_id=_PROFILE)
    )

    reference = await _registered_executor(definition_id, run).execute(request, context)

    assert reference == "d" * 64
    assert events.effects == [OperationEffect.NONE, OperationEffect.NONE]
    (private,) = operands.values
    assert isinstance(private, contracts.GoogleConfigurationExecutionResult)
    assert private.effect == "none" and private.projection.result == status
    _identity, receipt = _receipt(definition_id)
    assert project_google_configuration_result(private, receipt) == private.projection


@pytest.mark.parametrize("boundary", ["commit", "before_handoff", "acknowledged"])
@pytest.mark.asyncio
async def test_a_stored_record_read_that_asks_to_save_or_reach_the_provider_is_refused_and_stores_nothing(
    monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        if boundary == "commit":
            commit(lambda: True, changed=lambda saved: saved)
        elif boundary == "before_handoff":
            before_handoff("drive.files.get")
        else:
            acknowledged("drive.files.get", writes=True)
        return contracts.GoogleFolderViewProjection(profile_id=request.profile_id, configured=False)

    definition_id = contracts.GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID
    request, context, events, operands = _read_execution(
        definition_id, contracts.GoogleFolderViewRequest(profile_id=_PROFILE)
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await _registered_executor(definition_id, run).execute(request, context)

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
    assert operands.values == []
    assert events.effects == [OperationEffect.NONE]
