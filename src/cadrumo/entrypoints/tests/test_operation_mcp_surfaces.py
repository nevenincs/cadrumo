"""Every named MCP surface, held to the live registry through the real access policy.

A surface is enforced where an operation access is evaluated, so each claim
here is put to that evaluation for every registered operation: the production
registry, the recorded MCP decisions and the access policy are the real ones.
The session is a key session whose grant, scope and login facts admit every
operation, so a refusal is the frontend list's or the surface's and nothing
else's. The policy document is the widest an operation could resolve for a
submission, with and without the commit action.

A surface's operation list can grow under an unchanged name. This file passes
on membership and never on a count, so it keeps judging the whole list.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cache
from uuid import UUID

import pytest

from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_NAMES

from ...application.operations.mcp_admission import McpRuling, mcp_admission_decision
from ...application.operations.mcp_surfaces import MCP_SURFACES, McpSurfaceName
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OperationAccessPolicy,
    OperationAccessRequest,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from ...application.user_profile.operation_access_policy import evaluate_operation_access
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_FULL = McpSurfaceName.FULL
_READ_ONLY_LOCAL = McpSurfaceName.READ_ONLY_LOCAL
_ALLOWED = "allowed"
_FRONTEND_DENIED = "frontend_denied"
_COMMITTING = frozenset(AccessAction)
_READING = _COMMITTING - {AccessAction.COMMIT}

_NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
_BOOT = UUID("5bb00000-0000-4000-8000-000000000001")
_CONNECTION = UUID("5bb00000-0000-4000-8000-000000000002")
_PARENT_CONNECTION = UUID("5bb00000-0000-4000-8000-000000000003")
_CLIENT = UUID("5bb00000-0000-4000-8000-000000000004")
_SESSION = UUID("5bb00000-0000-4000-8000-000000000005")
_PARENT_SESSION = UUID("5bb00000-0000-4000-8000-000000000006")
_GRANT = UUID("5bb00000-0000-4000-8000-000000000007")
_KEY = UUID("5bb00000-0000-4000-8000-000000000008")
_BINDING = ProfileAccessBinding(
    profile_id=UUID("5bb00000-0000-4000-8000-000000000009"),
    installation_id=UUID("5bb00000-0000-4000-8000-00000000000a"),
    os_owner_id="synthetic-owner",
    custody_generation=1,
    dek_epoch=UUID("5bb00000-0000-4000-8000-00000000000b"),
)


@cache
def _registry() -> OperationRegistry:
    return build_production_operation_registry()


@cache
def _definition_ids() -> tuple[str, ...]:
    return tuple(sorted(item.contract.definition_id for item in _registry().public_registrations))


@cache
def _mcp_listed() -> frozenset[str]:
    return frozenset(
        item.contract.definition_id
        for item in _registry().public_registrations
        if _MCP in item.contract.permitted_frontends
    )


@cache
def _whole_scope() -> AccessScope:
    """Every registered operation and every action, so no scope ceiling refuses anything."""
    return AccessScope(
        operations=frozenset(_definition_ids()),
        actions=_COMMITTING,
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
    )


@cache
def _grant() -> AutomationGrant:
    return AutomationGrant(
        grant_id=_GRANT,
        binding=_BINDING,
        client_id=_CLIENT,
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=_whole_scope(),
        valid_from=_NOW - timedelta(days=1),
        expires_at=_NOW + timedelta(days=364),
        unattended=True,
        allow_os_lock=True,
    )


@cache
def _key() -> ApiKeyRecord:
    grant = _grant()
    return ApiKeyRecord(
        key_id=_KEY,
        grant_id=grant.grant_id,
        binding=_BINDING,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )


def _lease(
    surface: McpSurfaceName | None,
    *,
    session_id: UUID = _SESSION,
    connection_id: UUID = _CONNECTION,
    parent_session_id: UUID | None = None,
) -> AccessSession:
    return AccessSession(
        session_id=session_id,
        binding=_BINDING,
        profile_lock_generation=0,
        runtime_boot_id=_BOOT,
        connection_id=connection_id,
        client_id=_CLIENT,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=_whole_scope(),
        parent_session_id=parent_session_id,
        grant_id=_GRANT,
        grant_generation=1,
        key_id=_KEY,
        key_generation=1,
        issued_at=_NOW,
        expires_at=_NOW + ACCESS_LEASE_MAXIMUM,
        issued_monotonic=100.0,
        surface=surface,
    )


@cache
def _profile() -> ProfileAccessState:
    return ProfileAccessState(
        binding=_BINDING,
        lock_generation=0,
        globally_locked=False,
        automation_enabled=True,
        scope=_whole_scope(),
        storage=Availability.AVAILABLE,
        automation_custody=Availability.AVAILABLE,
    )


@cache
def _context() -> AccessEvaluationContext:
    return AccessEvaluationContext(
        now=_NOW,
        monotonic_now=100.0,
        clock_rollback_detected=False,
        runtime_boot_id=_BOOT,
        connection_id=_CONNECTION,
        authenticated_client_id=_CLIENT,
        login_contexts=(
            OsLoginContext(
                login_id="login-a",
                os_owner_id=_BINDING.os_owner_id,
                active=True,
                lock_state=OsLockState.UNLOCKED,
                unattended=LoginEligibility.ELIGIBLE,
                credential_facilities=Availability.AVAILABLE,
            ),
        ),
        private_work_available=True,
    )


def _answer(
    definition_id: str,
    surface: McpSurfaceName | None,
    *,
    action: AccessAction = AccessAction.SUBMIT,
    resolved: frozenset[AccessAction] = _READING,
    frontend: OperationFrontendProjection = _MCP,
    parent_surface: McpSurfaceName | None = None,
    delegated: bool = False,
) -> str:
    """Put one access to the real policy and name what it answered.

    ``resolved`` is the action set the operation's policy document holds.
    ``delegated`` evaluates a child lease that names no surface under a parent
    that names ``parent_surface``.
    """
    contract = _registry().lookup_public_contract(definition_id)
    session = _lease(surface, parent_session_id=_PARENT_SESSION if delegated else None)
    ancestors: tuple[AccessSession, ...] = ()
    if delegated:
        ancestors = (_lease(parent_surface, session_id=_PARENT_SESSION, connection_id=_PARENT_CONNECTION),)
    decision = evaluate_operation_access(
        request=OperationAccessRequest(
            profile_id=_BINDING.profile_id,
            definition_id=definition_id,
            action=action,
            frontend=frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=_CLIENT,
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest=contract.definition_contract_digest,
            actions=resolved,
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
        registry=_registry(),
        session=session,
        ancestors=ancestors,
        grant=_grant(),
        key=_key(),
        profile=_profile(),
        context=_context(),
    )
    return decision.code.value if isinstance(decision, AccessDenied) else _ALLOWED


def _answers(definition_id: str, surface: McpSurfaceName | None) -> set[str]:
    """What a submission is answered, whether or not its policy document holds the commit action."""
    return {_answer(definition_id, surface, resolved=resolved) for resolved in (_READING, _COMMITTING)}


def _recorded_as_changing_or_reaching(definition_id: str) -> bool:
    decision = mcp_admission_decision(definition_id)
    return decision.changes_records or decision.reaches_network


def _barred_by_the_two_facts() -> list[str]:
    """Every registered operation recorded as changing records or reaching the network."""
    return [definition_id for definition_id in _definition_ids() if _recorded_as_changing_or_reaching(definition_id)]


def _read_only_local_operations() -> frozenset[str]:
    operations = MCP_SURFACES[_READ_ONLY_LOCAL].operations
    assert operations
    return operations


def test_without_a_surface_the_session_is_admitted_to_exactly_what_the_registry_opens_to_mcp() -> None:
    """The session used throughout is refused by the frontend list alone."""
    listed = _mcp_listed()
    assert listed
    assert listed != set(_definition_ids())
    unexpected: dict[str, set[str]] = {}
    for definition_id in _definition_ids():
        answers = _answers(definition_id, None)
        if answers != {_ALLOWED if definition_id in listed else _FRONTEND_DENIED}:
            unexpected[definition_id] = answers
    assert not unexpected, f"operations the baseline session is not answered for by the frontend list: {unexpected}"


def test_the_full_surface_answers_every_access_as_no_surface_does() -> None:
    """Naming the full surface changes no admission and no refusal, for any operation or action."""
    differing: dict[str, tuple[str, str]] = {}
    seen: set[str] = set()
    for definition_id in _definition_ids():
        for action in AccessAction:
            for resolved in (_READING, _COMMITTING):
                unnamed = _answer(definition_id, None, action=action, resolved=resolved)
                named = _answer(definition_id, _FULL, action=action, resolved=resolved)
                seen.add(unnamed)
                if unnamed != named:
                    differing[f"{definition_id} {action.value}"] = (unnamed, named)
    assert not differing, f"accesses the full surface answers differently from no surface: {differing}"
    # Two refusals of everything would also agree, so the comparison must cover admissions.
    assert {_ALLOWED, _FRONTEND_DENIED} <= seen


def test_the_read_only_local_surface_refuses_every_operation_that_changes_records_or_reaches_the_network() -> None:
    """The refusal holds for the whole registry, whatever the operation's policy resolves."""
    barred = _barred_by_the_two_facts()
    assert barred
    admitted: dict[str, set[str]] = {}
    for definition_id in barred:
        answers = _answers(definition_id, _READ_ONLY_LOCAL)
        if answers != {_FRONTEND_DENIED}:
            admitted[definition_id] = answers
    assert not admitted, f"writes or network reaches the read-only local surface does not refuse: {admitted}"
    # Some of them are open to MCP, so it is the surface that refuses those.
    assert any(_answers(definition_id, None) == {_ALLOWED} for definition_id in barred)


def test_the_read_only_local_surface_refuses_every_operation_outside_its_list() -> None:
    operations = _read_only_local_operations()
    outside = [definition_id for definition_id in _definition_ids() if definition_id not in operations]
    assert outside
    admitted: dict[str, set[str]] = {}
    for definition_id in outside:
        answers = _answers(definition_id, _READ_ONLY_LOCAL)
        if answers != {_FRONTEND_DENIED}:
            admitted[definition_id] = answers
    assert not admitted, f"operations outside the read-only local list that it does not refuse: {admitted}"


def test_the_read_only_local_surface_admits_every_operation_on_its_list() -> None:
    """Every listed operation is registered and is admitted as it is without a surface."""
    operations = _read_only_local_operations()
    unregistered = sorted(operations - set(_definition_ids()))
    assert not unregistered, f"read-only local operations that are not registered: {unregistered}"
    refused: dict[str, str] = {}
    for definition_id in sorted(operations):
        assert _answer(definition_id, None) == _ALLOWED, definition_id
        answer = _answer(definition_id, _READ_ONLY_LOCAL)
        if answer != _ALLOWED:
            refused[definition_id] = answer
    assert not refused, f"listed operations the read-only local surface refuses: {refused}"


def test_no_surface_lists_an_operation_the_registry_does_not_open_to_mcp() -> None:
    """A surface narrows the registry's MCP listing and never widens it."""
    listed = _mcp_listed()
    judged = 0
    for surface in MCP_SURFACES.values():
        if surface.operations is None:
            continue
        judged += 1
        widened = sorted(surface.operations - listed)
        assert not widened, f"{surface.name}: lists operations the registry does not open to MCP: {widened}"
    assert judged


def _is_an_open_local_read(definition_id: str) -> bool:
    decision = mcp_admission_decision(definition_id)
    return decision.ruling is McpRuling.ADMITTED and not _recorded_as_changing_or_reaching(definition_id)


def test_the_read_only_local_list_is_every_local_read_the_registry_opens_to_mcp() -> None:
    """The list is derived from the recorded facts, and the registry's own listing agrees with it."""
    expected = {definition_id for definition_id in _mcp_listed() if _is_an_open_local_read(definition_id)}
    assert _read_only_local_operations() == expected


def test_every_surface_advertises_only_tools_the_catalogue_names() -> None:
    for surface in MCP_SURFACES.values():
        unknown = sorted(surface.tools - MCP_TOOL_NAMES)
        assert not unknown, f"{surface.name}: advertises tools the catalogue does not name: {unknown}"
    assert MCP_SURFACES[_FULL].tools == MCP_TOOL_NAMES


def _declares_a_review(definition_id: str) -> bool:
    contract = _registry().lookup_public_contract(definition_id)
    return bool(contract.interaction_kinds) or contract.review_projection_schema is not None


def test_the_tools_the_read_only_local_surface_leaves_out_serve_no_operation_on_it() -> None:
    """Only the review tools are left out, and no listed operation declares a review."""
    assert MCP_TOOL_NAMES - MCP_SURFACES[_READ_ONLY_LOCAL].tools == {"review", "respond"}
    reviewed = sorted(filter(_declares_a_review, _read_only_local_operations()))
    assert not reviewed, f"read-only local operations that need a tool the surface leaves out: {reviewed}"
    # Reviews exist elsewhere on MCP, so the check has something to find.
    assert any(_declares_a_review(definition_id) for definition_id in _mcp_listed())


def test_a_read_only_surface_refuses_the_commit_section_and_a_submission_that_could_open_it() -> None:
    """A listed operation is still refused where its own policy says the access could commit."""
    commit = AccessAction.COMMIT
    for definition_id in sorted(_read_only_local_operations()):
        assert _answer(definition_id, None, action=commit, resolved=_COMMITTING) == _ALLOWED, definition_id
        assert _answer(definition_id, None, resolved=_COMMITTING) == _ALLOWED, definition_id
        opened = _answer(definition_id, _READ_ONLY_LOCAL, action=commit, resolved=_COMMITTING)
        assert opened == _FRONTEND_DENIED, definition_id
        submitted = _answer(definition_id, _READ_ONLY_LOCAL, resolved=_COMMITTING)
        assert submitted == _FRONTEND_DENIED, definition_id


def test_a_lease_that_names_no_surface_is_held_to_the_surface_its_parent_named() -> None:
    barred = sorted(set(_barred_by_the_two_facts()) & _mcp_listed())
    assert barred
    for definition_id in barred:
        free = _answer(definition_id, None, delegated=True, resolved=_COMMITTING)
        assert free == _ALLOWED, definition_id
        held = _answer(definition_id, None, delegated=True, parent_surface=_READ_ONLY_LOCAL, resolved=_COMMITTING)
        assert held == _FRONTEND_DENIED, definition_id
    for definition_id in sorted(_read_only_local_operations()):
        kept = _answer(definition_id, None, delegated=True, parent_surface=_READ_ONLY_LOCAL)
        assert kept == _ALLOWED, definition_id


def test_a_lease_that_names_a_surface_is_refused_on_every_other_frontend() -> None:
    """A surface belongs to the MCP frontend, so a lease that names one is admitted nowhere else."""
    judged = 0
    for definition_id in sorted(_read_only_local_operations()):
        others = _registry().lookup_public_contract(definition_id).permitted_frontends - {_MCP}
        for frontend in sorted(others):
            judged += 1
            assert _answer(definition_id, None, frontend=frontend) == _ALLOWED, definition_id
            assert _answer(definition_id, _READ_ONLY_LOCAL, frontend=frontend) == _FRONTEND_DENIED, definition_id
            assert _answer(definition_id, _FULL, frontend=frontend) == _FRONTEND_DENIED, definition_id
    assert judged
