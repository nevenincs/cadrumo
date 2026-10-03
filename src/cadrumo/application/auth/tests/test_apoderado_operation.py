"""Registered apoderado request custody, projection, and canonical prewrite rules."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import apoderado_execution as apoderado_execution_module
from ..apoderado_contracts import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_REPRESENTED_NIF_SECRET_KIND,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoClearRequest,
    ApoderadoConfigureRequest,
    ApoderadoOperationProjection,
    ApoderadoStatusRequest,
    ApoderadoStatusSnapshot,
)
from ..apoderado_execution import ApoderadoOperationExecutor, ApoderadoOperationPorts
from ..apoderado_operation import build_apoderado_operation_definitions, build_apoderado_operation_registrations
from ..apoderado_service import ApoderadoStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")


def _unused_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ApoderadoOperationPorts:
    raise AssertionError(f"unexpected execution for {bucket_id}")


class _PhaseRecorder:
    def __init__(self) -> None:
        self.phases: list[str] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)


def test_apoderado_definitions_bind_the_real_public_graph_and_one_use_identity_slot() -> None:
    """All four routes compile; configure never places NIF in its request."""
    definitions = build_apoderado_operation_definitions(_unused_factory)
    registrations = build_apoderado_operation_registrations(definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert {definition.definition_id for definition in registry.definitions} == {
        "auth.apoderado.status",
        "auth.apoderado.configure",
        "auth.apoderado.clear",
        "auth.apoderado.check",
    }
    configure = registry.lookup(APODERADO_CONFIGURE_OPERATION_DEFINITION_ID)
    assert configure.ephemeral_secret is not None
    assert configure.ephemeral_secret.secret_kind == APODERADO_REPRESENTED_NIF_SECRET_KIND
    assert "represented_nif" not in ApoderadoConfigureRequest.model_fields
    assert (
        OperationFrontendProjection.MCP in registry.lookup(APODERADO_STATUS_OPERATION_DEFINITION_ID).permitted_frontends
    )
    assert (
        OperationFrontendProjection.MCP in registry.lookup(APODERADO_CHECK_OPERATION_DEFINITION_ID).permitted_frontends
    )
    assert OperationFrontendProjection.MCP not in configure.permitted_frontends


_PIN = cast(PinnedAuthorityOperation, object())
_PERIOD = Period.from_year_and_code(2026, "1T")


def _registry() -> OperationRegistry:
    definitions = build_apoderado_operation_definitions(_unused_factory)
    return OperationRegistry(
        definitions=definitions, public_registrations=build_apoderado_operation_registrations(definitions)
    )


def _apoderado_request(definition_id: str) -> OperationRequest[BaseModel]:
    payload = (
        ApoderadoClearRequest(profile_id=_PROFILE)
        if definition_id == APODERADO_CLEAR_OPERATION_DEFINITION_ID
        else ApoderadoStatusRequest(profile_id=_PROFILE)
    )
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
    )


def _submitted(
    definition_id: str,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction = AccessAction.SUBMIT,
    periods: frozenset[Period] = frozenset(),
) -> OperationAccessRequest:
    return OperationAccessRequest(
        profile_id=profile_id,
        definition_id=definition_id,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        periods=periods,
        period_independent=not periods,
        destination_id=uuid4(),
    )


def _apoderado_context(
    registry: OperationRegistry,
    definition_id: str,
    action: AccessAction,
    *,
    frontend: OperationFrontendProjection,
    admitted: OperationAccessRequest | None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(definition_id),
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


@pytest.mark.parametrize(
    ("definition_id", "action"),
    [
        (APODERADO_STATUS_OPERATION_DEFINITION_ID, AccessAction.OBSERVE),
        (APODERADO_STATUS_OPERATION_DEFINITION_ID, AccessAction.RESULT),
        (APODERADO_CLEAR_OPERATION_DEFINITION_ID, AccessAction.OBSERVE),
        (APODERADO_CLEAR_OPERATION_DEFINITION_ID, AccessAction.RESULT),
        (APODERADO_CLEAR_OPERATION_DEFINITION_ID, AccessAction.COMMIT),
    ],
)
def test_apoderado_replay_from_a_fresh_session_binds_the_admission_not_its_origin(
    definition_id: str, action: AccessAction
) -> None:
    """A later session has a new destination and frontend; profile, definition, action and scope still bind."""
    registry = _registry()
    request = _apoderado_request(definition_id)
    fresh = _apoderado_context(
        registry, definition_id, action, frontend=OperationFrontendProjection.TUI, admitted=_submitted(definition_id)
    )
    assert fresh.admitted_request is not None and fresh.admitted_request.destination_id != fresh.destination_id

    resolved = resolve_operation_access(registry=registry, request=request, context=fresh)

    assert resolved.request.destination_id == fresh.destination_id
    assert resolved.request.frontend is OperationFrontendProjection.TUI
    assert (action is AccessAction.COMMIT) is not bool(resolved.policy.disclosures)
    assert all(item.destination_id == fresh.destination_id for item in resolved.policy.disclosures)
    for foreign in (
        _submitted(definition_id, profile_id=_OTHER),
        _submitted(APODERADO_CHECK_OPERATION_DEFINITION_ID),
        _submitted(definition_id, action=AccessAction.START),
        _submitted(definition_id, periods=frozenset({_PERIOD})),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry,
                request=request,
                context=replace(fresh, admitted_request=foreign, authority_operation=_PIN),
            )
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START])
def test_apoderado_entry_actions_need_held_authority_even_with_a_matching_admission(action: AccessAction) -> None:
    registry = _registry()
    request = _apoderado_request(APODERADO_CLEAR_OPERATION_DEFINITION_ID)
    context = _apoderado_context(
        registry,
        APODERADO_CLEAR_OPERATION_DEFINITION_ID,
        action,
        frontend=OperationFrontendProjection.CLI,
        admitted=_submitted(APODERADO_CLEAR_OPERATION_DEFINITION_ID),
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=request, context=context)

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    held = replace(context, authority_operation=_PIN)
    assert resolve_operation_access(registry=registry, request=request, context=held).request.action is action


def test_apoderado_public_status_is_complete_and_rejects_a_foreign_profile() -> None:
    """The public status copies all canonical facts under one UUID binding."""
    status = ApoderadoStatus(
        bucket_id=str(_PROFILE),
        configured=True,
        represented_nif="12345678Z",
        granted_scopes=("ALL",),
        catalogue_version="v1",
        configured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    snapshot = ApoderadoStatusSnapshot.from_status(status)
    assert snapshot.bucket_id == _PROFILE
    assert snapshot.represented_nif == status.represented_nif
    assert snapshot.granted_scopes == status.granted_scopes
    with pytest.raises(ValidationError):
        ApoderadoOperationProjection(
            profile_id=_OTHER,
            operation_id=APODERADO_STATUS_OPERATION_DEFINITION_ID,
            outcome="completed",
            effect=OperationEffect.NONE,
            status=snapshot,
        )


@pytest.mark.parametrize("mismatch", ["request_subject", "context_definition", "context_subject"])
def test_apoderado_executor_refuses_identity_mismatch_before_profile_access_or_work(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    """The real executor refuses all three identity mismatches before protected work."""
    expected_subject = profile_operation_subject(str(_PROFILE))
    other_subject = profile_operation_subject(str(_OTHER))
    request_subject = other_subject if mismatch == "request_subject" else expected_subject
    context_definition = (
        "auth.apoderado.other" if mismatch == "context_definition" else APODERADO_STATUS_OPERATION_DEFINITION_ID
    )
    context_subject = other_subject if mismatch == "context_subject" else request_subject
    request = OperationRequest[BaseModel](
        definition_id=APODERADO_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=request_subject,
        payload=ApoderadoStatusRequest(profile_id=_PROFILE),
    )
    events = _PhaseRecorder()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=context_definition,
            subject_ref=context_subject,
        ),
        authority_operation=object(),
        events=events,
    )
    active_profile_lookups: list[None] = []
    factory_calls: list[str] = []

    def active_profile_must_not_be_read() -> str:
        active_profile_lookups.append(None)
        raise AssertionError("identity refusal must precede the active-profile lookup")

    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ApoderadoOperationPorts:
        factory_calls.append(bucket_id)
        raise AssertionError("identity refusal must precede the ports factory")

    monkeypatch.setattr(apoderado_execution_module, "require_active_bucket_id", active_profile_must_not_be_read)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(ApoderadoOperationExecutor(factory).execute(request, cast(OperationExecutorContext, context)))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert active_profile_lookups == []
    assert events.phases == []
    assert factory_calls == []
