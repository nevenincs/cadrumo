"""Invoice removal refuses foreign active profiles and is granted alike on every frontend."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..catalogue_lifecycle_ports import CatalogueLifecyclePorts
from ..catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    InvoiceRemoveExecutor,
    InvoiceRemoveRequest,
    build_invoice_remove_definition,
    build_invoice_remove_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000ab")
_ACCESSES = (AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT)


def _unreached_ports(*, bucket_id: str) -> CatalogueLifecyclePorts:
    raise AssertionError(f"access resolution reached invoice removal ports for {bucket_id}")


def _registry() -> OperationRegistry:
    definition = build_invoice_remove_definition(_unreached_ports)
    return OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_invoice_remove_registration(definition),),
    )


def _removal() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=INVOICE_REMOVE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=InvoiceRemoveRequest(profile_id=_PROFILE, invoice_id="a" * 64),
    )


def _context(
    registry: OperationRegistry, frontend: OperationFrontendProjection, access: AccessAction
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=_DESTINATION,
        action=access,
        frontend=frontend,
        contract=registry.lookup_public_contract(INVOICE_REMOVE_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )


@pytest.mark.parametrize("access", _ACCESSES)
def test_removal_resolves_the_same_whole_profile_commit_access_on_every_frontend(access: AccessAction) -> None:
    registry = _registry()

    resolved = {
        frontend: resolve_operation_access(
            registry=registry, request=_removal(), context=_context(registry, frontend, access)
        )
        for frontend in OperationFrontendProjection
    }

    assert len({answer.policy for answer in resolved.values()}) == 1
    for frontend, answer in resolved.items():
        assert answer.request.frontend is frontend
        assert answer.request.action is access
        assert answer.request.period_independent and answer.policy.requires_all_periods
        assert AccessAction.COMMIT in answer.policy.actions


def test_remove_executor_refuses_foreign_active_profile_before_phase_or_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = OperationRequest[InvoiceRemoveRequest](
        definition_id=INVOICE_REMOVE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=InvoiceRemoveRequest(profile_id=_PROFILE, invoice_id="a" * 64),
    )
    phases: list[str] = []
    effects: list[object] = []

    async def record_phase(phase: str) -> None:
        phases.append(phase)

    async def record_effect(effect: object) -> None:
        effects.append(effect)

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            ),
            events=SimpleNamespace(phase=record_phase, effect=record_effect),
        ),
    )
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_OTHER_PROFILE))

    def unused_factory(*, bucket_id: str) -> CatalogueLifecyclePorts:
        pytest.fail(f"foreign active profile reached invoice removal ports for {bucket_id}")

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(InvoiceRemoveExecutor(unused_factory).execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert phases == effects == []
