"""Every named external client surface, held to the live registry through the real access policy.

A surface is enforced where an operation access is evaluated, so each claim
here is put to that evaluation for every registered operation: the production
registry, the recorded surface facts and the access policy are the real ones.
The session is a key session whose grant, scope and login facts admit every
operation, so a refusal of a submission is the surface's and nothing else's.
The policy document is the widest an operation could resolve for a
submission, with and without the commit action.

A surface's operation list can grow under an unchanged name. This file passes
on membership and never on a count, so it keeps judging the whole list.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cache
from uuid import UUID

import pytest

from cadrumo.application.operations.access_resolution import ResolvedOperationAccess
from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    DisclosurePermission,
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
from cadrumo.application.user_profile.access_policy import intersect_scopes
from cadrumo.application.user_profile.operation_access_policy import evaluate_operation_access
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo_harness.mcp.access_scope import surface_scope
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_NAMES
from cadrumo_harness.mcp.surface_facts import operation_surface_facts
from cadrumo_harness.mcp.surfaces import MCP_SURFACES, McpSurfaceName

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.EXTERNAL_CLIENT
_FULL = McpSurfaceName.FULL
_READ_ONLY_LOCAL = McpSurfaceName.READ_ONLY_LOCAL
_ALLOWED = "allowed"
_SCOPE_DENIED = AccessDenialCode.OPERATION_DENIED.value
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


def _is_persons_act(definition_id: str) -> bool:
    contract = _registry().lookup_public_contract(definition_id)
    return operation_is_persons_act(definition_id, ephemeral_secret_required=contract.ephemeral_secret_required)


def _agent_operation_ids() -> tuple[str, ...]:
    """Every registered operation an automation may run: all but the person's own acts, which no surface holds."""
    return tuple(definition_id for definition_id in _definition_ids() if not _is_persons_act(definition_id))


@cache
def _whole_scope(disclosures: frozenset[DisclosurePermission] = frozenset()) -> AccessScope:
    """Every registered operation and every action, so no scope ceiling refuses anything.

    ``disclosures`` is what a policy under test discloses, so that a real
    policy is not refused for a permission the synthetic scope never held.
    """
    return AccessScope(
        operations=frozenset(_definition_ids()),
        actions=_COMMITTING,
        disclosures=disclosures,
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
    )


@cache
def _grant(disclosures: frozenset[DisclosurePermission] = frozenset()) -> AutomationGrant:
    return AutomationGrant(
        grant_id=_GRANT,
        binding=_BINDING,
        client_id=_CLIENT,
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=_whole_scope(disclosures),
        valid_from=_NOW - timedelta(days=1),
        expires_at=_NOW + timedelta(days=364),
        unattended=True,
        allow_os_lock=True,
    )


@cache
def _key(disclosures: frozenset[DisclosurePermission] = frozenset()) -> ApiKeyRecord:
    grant = _grant(disclosures)
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
    disclosures: frozenset[DisclosurePermission] = frozenset(),
) -> AccessSession:
    scope = _whole_scope(disclosures)
    if surface is not None:
        ceiling = surface_scope(MCP_SURFACES[surface]).model_copy(
            update={
                # This synthetic policy control already owns these disclosures and
                # delegation rights; a surface only narrows its operational ceiling.
                "disclosures": scope.disclosures,
                "disclosure_categories": scope.disclosure_categories,
                "allow_delegation": scope.allow_delegation,
            }
        )
        scope = intersect_scopes((scope, ceiling))
    return AccessSession(
        session_id=session_id,
        binding=_BINDING,
        profile_lock_generation=0,
        runtime_boot_id=_BOOT,
        connection_id=connection_id,
        client_id=_CLIENT,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=scope,
        parent_session_id=parent_session_id,
        grant_id=_GRANT,
        grant_generation=1,
        key_id=_KEY,
        key_generation=1,
        issued_at=_NOW,
        expires_at=_NOW + ACCESS_LEASE_MAXIMUM,
        issued_monotonic=100.0,
    )


@cache
def _profile(disclosures: frozenset[DisclosurePermission] = frozenset()) -> ProfileAccessState:
    return ProfileAccessState(
        binding=_BINDING,
        lock_generation=0,
        globally_locked=False,
        automation_enabled=True,
        scope=_whole_scope(disclosures),
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
    ``delegated`` evaluates an unrestricted child under a parent whose generic
    operation/effect ceiling is narrowed by ``parent_surface``.
    """
    contract = _registry().lookup_public_contract(definition_id)
    session = _lease(surface, parent_session_id=_PARENT_SESSION if delegated else None)
    ancestors: tuple[AccessSession, ...] = ()
    if delegated:
        ancestors = (_lease(parent_surface, session_id=_PARENT_SESSION, connection_id=_PARENT_CONNECTION),)
    return _evaluate(
        OperationAccessRequest(
            profile_id=_BINDING.profile_id,
            definition_id=definition_id,
            action=action,
            frontend=frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=_CLIENT,
        ),
        OperationAccessPolicy(
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
        session=session,
        ancestors=ancestors,
        registry=_registry(),
    )


def _evaluate(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    *,
    session: AccessSession,
    ancestors: tuple[AccessSession, ...],
    registry: OperationRegistry,
) -> str:
    """Evaluate one access under the synthetic key session and name the answer."""
    disclosures = policy.disclosures
    decision = evaluate_operation_access(
        request=request,
        policy=policy,
        registry=registry,
        session=session,
        ancestors=ancestors,
        grant=_grant(disclosures),
        key=_key(disclosures),
        profile=_profile(disclosures),
        context=_context(),
    )
    return decision.code.value if isinstance(decision, AccessDenied) else _ALLOWED


def human_lease(scope_of: AccessSession) -> AccessSession:
    """An independent human control with the scope, connection and client of a key session."""
    return AccessSession.model_validate(
        {
            **dict(scope_of),
            "kind": SessionKind.HUMAN,
            "originating_login_id": _context().login_contexts[0].login_id,
            "grant_id": None,
            "grant_generation": None,
            "key_id": None,
            "key_generation": None,
            "expires_at": _NOW + timedelta(hours=1),
        }
    )


def answer_for_resolved_access(
    resolved: ResolvedOperationAccess,
    surface: McpSurfaceName | None,
    *,
    registry: OperationRegistry,
    human: bool = False,
) -> str:
    """Name what a session is answered for an access its operation's own resolver produced.

    The request is the resolver's, with the profile replaced by the one this
    file's synthetic session is bound to; the policy is used as resolved, and
    the session's ceilings hold every action and exactly the disclosures the
    policy makes. A refusal is therefore the surface's or the policy's own.
    The session is a key session, or an independent HUMAN/CLI policy control
    where ``human``. The latter is never a real external MCP admission.
    """
    request = resolved.request.model_copy(
        update={
            "profile_id": _BINDING.profile_id,
            "frontend": OperationFrontendProjection.CLI if human else resolved.request.frontend,
        }
    )
    disclosures = resolved.policy.disclosures
    key_session = _lease(surface, disclosures=disclosures)
    decision = evaluate_operation_access(
        request=request,
        policy=resolved.policy,
        registry=registry,
        session=human_lease(key_session) if human else key_session,
        ancestors=(),
        grant=None if human else _grant(disclosures),
        key=None if human else _key(disclosures),
        profile=_profile(disclosures),
        context=_context(),
    )
    return decision.code.value if isinstance(decision, AccessDenied) else _ALLOWED


def _answers(definition_id: str, surface: McpSurfaceName | None) -> set[str]:
    """What a submission is answered, whether or not its policy document holds the commit action."""
    return {_answer(definition_id, surface, resolved=resolved) for resolved in (_READING, _COMMITTING)}


def _recorded_as_changing_or_reaching(definition_id: str) -> bool:
    facts = operation_surface_facts(definition_id)
    return facts.changes_records or facts.reaches_network


def _barred_by_the_two_facts() -> list[str]:
    """Every registered operation recorded as changing records or reaching the network."""
    return [
        definition_id for definition_id in _agent_operation_ids() if _recorded_as_changing_or_reaching(definition_id)
    ]


def _read_only_local_operations() -> frozenset[str]:
    operations = MCP_SURFACES[_READ_ONLY_LOCAL].operations
    assert operations is not None and operations
    return operations


def test_without_a_surface_the_session_is_admitted_to_every_registered_operation() -> None:
    """The session used throughout is refused nothing, so each refusal below is a surface's."""
    assert _agent_operation_ids()
    refused: dict[str, set[str]] = {}
    for definition_id in _agent_operation_ids():
        answers = _answers(definition_id, None)
        if answers != {_ALLOWED}:
            refused[definition_id] = answers
    assert not refused, f"operations the baseline session is refused with no surface named: {refused}"


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
    # Two refusals of everything would also agree, so the comparison must cover admissions and refusals.
    assert _ALLOWED in seen
    assert seen - {_ALLOWED}


def test_the_read_only_local_surface_refuses_every_operation_that_changes_records_or_reaches_the_network() -> None:
    """The refusal holds for the whole registry, whatever the operation's policy resolves."""
    barred = _barred_by_the_two_facts()
    assert barred
    admitted: dict[str, set[str]] = {}
    for definition_id in barred:
        answers = _answers(definition_id, _READ_ONLY_LOCAL)
        if answers != {_SCOPE_DENIED}:
            admitted[definition_id] = answers
    assert not admitted, f"writes or network reaches the read-only local surface does not refuse: {admitted}"
    # Without the surface each is admitted, so it is the surface that refuses them.
    assert all(_answers(definition_id, None) == {_ALLOWED} for definition_id in barred)


def test_the_read_only_local_surface_refuses_every_operation_outside_its_list() -> None:
    operations = _read_only_local_operations()
    outside = [definition_id for definition_id in _agent_operation_ids() if definition_id not in operations]
    assert outside
    admitted: dict[str, set[str]] = {}
    for definition_id in outside:
        answers = _answers(definition_id, _READ_ONLY_LOCAL)
        if answers != {_SCOPE_DENIED}:
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


def test_no_surface_lists_an_operation_that_is_not_registered() -> None:
    """A surface narrows the registry and never names anything outside it."""
    registered = set(_definition_ids())
    judged = 0
    for surface in MCP_SURFACES.values():
        if surface.operations is None:
            continue
        judged += 1
        unregistered = sorted(surface.operations - registered)
        assert not unregistered, f"{surface.name}: lists operations that are not registered: {unregistered}"
    assert judged


def test_the_read_only_local_list_is_every_registered_local_read() -> None:
    """The list is derived from the recorded facts alone, and no local read is left off it."""
    expected = {
        definition_id for definition_id in _definition_ids() if not _recorded_as_changing_or_reaching(definition_id)
    }
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
    # Reviews exist elsewhere in the registry, so the check has something to find.
    assert any(_declares_a_review(definition_id) for definition_id in _definition_ids())


def test_a_read_only_surface_refuses_the_commit_section_and_a_submission_that_could_open_it() -> None:
    """A listed operation is still refused where its own policy says the access could commit."""
    commit = AccessAction.COMMIT
    for definition_id in sorted(_read_only_local_operations()):
        assert _answer(definition_id, None, action=commit, resolved=_COMMITTING) == _ALLOWED, definition_id
        assert _answer(definition_id, None, resolved=_COMMITTING) == _ALLOWED, definition_id
        opened = _answer(definition_id, _READ_ONLY_LOCAL, action=commit, resolved=_COMMITTING)
        assert opened == _SCOPE_DENIED, definition_id
        submitted = _answer(definition_id, _READ_ONLY_LOCAL, resolved=_COMMITTING)
        assert submitted == _SCOPE_DENIED, definition_id


def test_the_persons_acts_are_refused_to_mcp_on_every_surface_and_admitted_to_the_command_line() -> None:
    """An operation that needs a secret or administers keys is the person's, whatever surface an automation names."""
    persons = [definition_id for definition_id in _definition_ids() if _is_persons_act(definition_id)]
    assert persons, "no registered operation is the person's act; the denominator is empty"
    for definition_id in persons:
        for surface in (None, _FULL, _READ_ONLY_LOCAL):
            assert _answers(definition_id, surface) == {AccessDenialCode.PERSON_ACT_REQUIRED.value}, definition_id
        assert _answer(definition_id, None, frontend=OperationFrontendProjection.CLI) == _ALLOWED, definition_id


def test_a_lease_that_names_no_surface_is_held_to_the_surface_its_parent_named() -> None:
    barred = sorted(_barred_by_the_two_facts())
    assert barred
    for definition_id in barred:
        free = _answer(definition_id, None, delegated=True, resolved=_COMMITTING)
        assert free == _ALLOWED, definition_id
        held = _answer(definition_id, None, delegated=True, parent_surface=_READ_ONLY_LOCAL, resolved=_COMMITTING)
        assert held == _SCOPE_DENIED, definition_id
    for definition_id in sorted(_read_only_local_operations()):
        kept = _answer(definition_id, None, delegated=True, parent_surface=_READ_ONLY_LOCAL)
        assert kept == _ALLOWED, definition_id


def test_each_frontend_obeys_the_same_generic_operation_and_effect_ceiling() -> None:
    """Scope ceilings constrain every frontend without a named MCP field on the lease."""
    judged = 0
    for definition_id in sorted(_read_only_local_operations()):
        for frontend in sorted(OperationFrontendProjection):
            judged += 1
            assert _answer(definition_id, None, frontend=frontend) == _ALLOWED, definition_id
            assert _answer(definition_id, _FULL, frontend=frontend) == _ALLOWED, definition_id
            assert _answer(definition_id, _READ_ONLY_LOCAL, frontend=frontend) == _ALLOWED, definition_id
            assert _answer(definition_id, None, frontend=frontend, resolved=_COMMITTING) == _ALLOWED, definition_id
            assert _answer(definition_id, _FULL, frontend=frontend, resolved=_COMMITTING) == _ALLOWED, definition_id
            assert _answer(definition_id, _READ_ONLY_LOCAL, frontend=frontend, resolved=_COMMITTING) == _SCOPE_DENIED, (
                definition_id
            )
    assert judged
