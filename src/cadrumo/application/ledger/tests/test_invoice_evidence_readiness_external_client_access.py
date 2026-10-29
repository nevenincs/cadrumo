"""Reader readiness is open to every frontend and releases each role's judgement."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.model_roles import ModelRole
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ...local_reader import LocalReaderStatus, RoleLane, read_local_reader_status
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ..invoice_evidence_readiness_operation import (
    LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
    LedgerEvidenceReaderReadinessExecutionResult,
    LedgerEvidenceReaderReadinessExecutor,
    LedgerEvidenceReaderReadinessProjection,
    LedgerEvidenceReaderReadinessRequest,
    build_ledger_evidence_reader_readiness_definition,
    build_ledger_evidence_reader_readiness_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _status(lanes: Mapping[ModelRole, RoleLane]) -> LocalReaderStatus:
    """Judge the real reader status."""
    return read_local_reader_status(lanes)


def _unread_status(lanes: Mapping[ModelRole, RoleLane]) -> LocalReaderStatus:
    del lanes
    raise AssertionError("registration and access resolution must not measure the reader")


def _registry() -> OperationRegistry:
    definition = build_ledger_evidence_reader_readiness_definition(_unread_status)
    registration = build_ledger_evidence_reader_readiness_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceReaderReadinessRequest(profile_id=_PROFILE),
    )


@pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection))
def test_readiness_is_admitted_alike_on_every_frontend_for_either_kind_of_session(
    frontend: OperationFrontendProjection,
) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID)

    resolved = resolve_operation_access(
        registry=registry,
        request=_request(),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=frontend,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        ),
    )
    assert resolved.request.frontend is frontend
    assert resolved.request.profile_id == _PROFILE
    # A session under the person's sign-in and one under an enrolled key differ
    # in kind alone, and only a human-only policy tells the two apart.
    assert resolved.policy.requires_human is False
    assert AccessAction.COMMIT not in resolved.policy.actions


def test_the_projection_publishes_each_role_s_judgement() -> None:
    status = _status({})

    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, status)

    assert projection.extraction_ready is status.extraction_ready
    assert [row.role for row in projection.roles] == [row.role.value for row in status.roles]
    assert [row.model for row in projection.roles] == [row.model for row in status.roles]


@pytest.mark.asyncio
async def test_the_executor_and_the_registered_projector_release_each_role_s_judgement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Operands:
        async def put(self, value: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            stored.append(value)
            return "d" * 64

    class Events:
        async def phase(self, _code: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    identity = OperationIdentity(
        operation_id="e" * 64,
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    context = cast(
        OperationExecutorContext,
        cast(object, SimpleNamespace(identity=identity, events=Events(), operands=Operands())),
    )
    request = OperationRequest[LedgerEvidenceReaderReadinessRequest](
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceReaderReadinessRequest(profile_id=_PROFILE),
    )

    reference = await LedgerEvidenceReaderReadinessExecutor(_status).execute(request, context)

    assert reference == "d" * 64 and effects == [OperationEffect.NONE]
    (private,) = stored
    assert isinstance(private, LedgerEvidenceReaderReadinessExecutionResult)
    projector = (
        _registry()
        .lookup_public_registration(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID)
        .result_projector
    )
    assert projector is not None
    released = projector(
        private,
        OperationTerminalReceipt(
            identity=identity,
            revision=1,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            settled_at=now(),
            result_ref="d" * 64,
        ),
    )
    assert isinstance(released, LedgerEvidenceReaderReadinessProjection)
