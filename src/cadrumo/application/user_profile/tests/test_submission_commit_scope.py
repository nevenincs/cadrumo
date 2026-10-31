"""A session submits a request only while it holds the COMMIT door that request can open.

Each case resolves a real registered request through its owning resolver and
evaluates the result for one delegated key session, as the runtime does at
admission. The request decides the door: a confirmed mutation resolves COMMIT,
while a read and a preview of the same mutation do not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.remove_operation import (
    LEDGER_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRemoveRequest,
    build_ledger_remove_definition,
    build_ledger_remove_registration,
)
from cadrumo.application.ledger.reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetRequest,
    build_ledger_reset_definition,
    build_ledger_reset_registration,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.tests._access_authority_support import build_access_authority, new_access_binding
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
)
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDecision, AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope, Availability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000c1")
_ALL_ACTIONS = frozenset(AccessAction)
_WITHOUT_COMMIT = _ALL_ACTIONS - {AccessAction.COMMIT}
_COMMITTING = ("profile_field_mutation", "ledger_remove", "ledger_reset")
_NOT_COMMITTING = ("profile_view", "ledger_remove_preview", "ledger_reset_preview")
_DENIED = AccessDenied(code=AccessDenialCode.OPERATION_DENIED)


def _unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")


def _profile_registry() -> OperationRegistry:
    return OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )


def _ledger_remove_registry() -> OperationRegistry:
    definition = build_ledger_remove_definition(_unused_ports)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_ledger_remove_registration(definition),)
    )


def _ledger_reset_registry() -> OperationRegistry:
    definition = build_ledger_reset_definition(_unused_ports)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_ledger_reset_registration(definition),)
    )


def _case(name: str) -> tuple[OperationRegistry, OperationRequest[BaseModel]]:
    """Return one named request with the registry of the operation that owns it."""
    payload: BaseModel
    if name == "profile_field_mutation":
        registry, definition_id = _profile_registry(), PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
        payload = ProfileFieldMutationOperationRequest(
            profile_id=_PROFILE,
            expected_revision=1,
            expected_content_digest="0" * 64,
            path="preferences.output_language",
            value="es",
        )
    elif name == "profile_view":
        registry, definition_id = _profile_registry(), PROFILE_VIEW_OPERATION_DEFINITION_ID
        payload = ProfileViewOperationRequest(profile_id=_PROFILE, page_kind=ProfileViewPageKind.FACTS)
    elif name in {"ledger_remove", "ledger_remove_preview"}:
        registry, definition_id = _ledger_remove_registry(), LEDGER_REMOVE_OPERATION_DEFINITION_ID
        payload = LedgerRemoveRequest(
            profile_id=_PROFILE, transaction_id="a" * 64, dry_run=name == "ledger_remove_preview"
        )
    elif name in {"ledger_reset", "ledger_reset_preview"}:
        registry, definition_id = _ledger_reset_registry(), LEDGER_RESET_OPERATION_DEFINITION_ID
        payload = LedgerResetRequest(
            profile_id=_PROFILE, reason="reset contaminated import", dry_run=name == "ledger_reset_preview"
        )
    else:
        raise AssertionError(f"unknown case {name}")
    return registry, OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
    )


def _decision(
    name: str,
    *,
    action: AccessAction = AccessAction.SUBMIT,
    session_actions: frozenset[AccessAction] = _ALL_ACTIONS,
    profile_actions: frozenset[AccessAction] = _ALL_ACTIONS,
) -> AccessDecision:
    """Resolve the named request as its owner does, then evaluate it for one delegated key session.

    The grant holds every action, so the session and the profile are the
    ceilings a case narrows.
    """
    registry, request = _case(name)
    client_id = uuid4()
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=client_id,
            action=action,
            frontend=OperationFrontendProjection.CLI,
            contract=registry.lookup_public_contract(request.definition_id),
            published_authority=Availability.AVAILABLE,
        ),
    )

    def scope(actions: frozenset[AccessAction]) -> AccessScope:
        return AccessScope(
            operations=frozenset({request.definition_id}),
            actions=actions,
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )

    authority = build_access_authority(
        binding=new_access_binding(_PROFILE),
        now=_NOW,
        grant_scope=scope(_ALL_ACTIONS),
        session_scope=scope(session_actions),
        profile_scope=scope(profile_actions),
        grant_validity=timedelta(days=364),
        session_lease=ACCESS_LEASE_MAXIMUM,
        allow_os_lock=True,
        login_id="login-a",
        client_id=client_id,
    )
    return authority.evaluate(registry=registry, request=resolved.request, policy=resolved.policy)


@pytest.mark.parametrize("narrowed", ["session", "profile"])
@pytest.mark.parametrize("name", _COMMITTING)
def test_a_ceiling_without_commit_cannot_submit_a_request_that_can_commit(name: str, narrowed: str) -> None:
    decision = _decision(
        name,
        session_actions=_WITHOUT_COMMIT if narrowed == "session" else _ALL_ACTIONS,
        profile_actions=_WITHOUT_COMMIT if narrowed == "profile" else _ALL_ACTIONS,
    )

    assert decision == _DENIED


@pytest.mark.parametrize("name", _NOT_COMMITTING)
def test_a_scope_without_commit_still_submits_a_read_or_a_preview(name: str) -> None:
    decision = _decision(name, session_actions=_WITHOUT_COMMIT, profile_actions=_WITHOUT_COMMIT)

    assert isinstance(decision, AccessAllowed)


@pytest.mark.parametrize("name", (*_COMMITTING, *_NOT_COMMITTING))
def test_a_scope_holding_commit_submits_every_request(name: str) -> None:
    assert isinstance(_decision(name), AccessAllowed)


@pytest.mark.parametrize("name", _COMMITTING)
def test_the_commit_door_is_still_decided_when_it_opens(name: str) -> None:
    assert isinstance(_decision(name, action=AccessAction.COMMIT), AccessAllowed)
    assert _decision(name, action=AccessAction.COMMIT, session_actions=_WITHOUT_COMMIT) == _DENIED


@pytest.mark.parametrize("name", _NOT_COMMITTING)
def test_a_read_or_a_preview_resolves_no_commit_door_for_any_scope(name: str) -> None:
    assert _decision(name, action=AccessAction.COMMIT) == _DENIED


@pytest.mark.parametrize("action", [AccessAction.START, AccessAction.RESUME])
@pytest.mark.parametrize("name", _COMMITTING)
def test_only_submission_looks_ahead_to_the_commit_door(name: str, action: AccessAction) -> None:
    assert isinstance(_decision(name, action=action, session_actions=_WITHOUT_COMMIT), AccessAllowed)
