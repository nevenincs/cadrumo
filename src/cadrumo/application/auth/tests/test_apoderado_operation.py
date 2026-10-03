"""Registered apoderado request custody, projection, and canonical prewrite rules."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import apoderado_execution as apoderado_execution_module
from ..apoderado_contracts import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_REPRESENTED_NIF_SECRET_KIND,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
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
