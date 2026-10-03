"""Invoice removal refuses foreign active profiles before composing capabilities."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....core.operations import profile_operation_subject
from ...operations import profile_guard
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..catalogue_lifecycle_ports import CatalogueLifecyclePorts
from ..catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    InvoiceRemoveExecutor,
    InvoiceRemoveRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


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
