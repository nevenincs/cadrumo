"""Recovery status keeps profile identity and terminal evidence at the CLI boundary."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import typer
from pydantic import BaseModel

from .....application.user_profile.recovery_status_operation import (
    RECOVERY_STATUS_OPERATION_DEFINITION_ID,
    RecoveryStatusProjection,
    RecoveryStatusRequest,
)
from .....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...errors import CliRefusedBoundaryError
from ...registered_operation_contracts import RegisteredOperationCompletion
from .. import runtime_recovery_status as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("fault", [None, "unenrolled", "profile", "effect", "terminal"])
def test_recovery_status_correlates_worker_profile_and_receipt(
    monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    profile_id = uuid4()
    client = SimpleNamespace(profile_id=profile_id)
    result = RecoveryStatusProjection(
        profile_id=uuid4() if fault == "profile" else profile_id, enrolled=fault != "unenrolled"
    )
    completion = RegisteredOperationCompletion(
        operation_id="a" * 64,
        projection=result,
        effect=OperationEffect.UNKNOWN if fault == "effect" else OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.FAILED
        if fault == "terminal"
        else OperationTerminalCondition.SUCCEEDED,
        refusal_code=None,
    )

    def require_client(_ctx: typer.Context, *, expected_profile_id: UUID) -> object:
        assert expected_profile_id == profile_id
        return client

    def submit(
        actual_client: object, request: BaseModel, **options: object
    ) -> RegisteredOperationCompletion[RecoveryStatusProjection]:
        assert actual_client is client
        assert request == RecoveryStatusRequest(profile_id=profile_id)
        assert options["subject_ref"] == profile_operation_subject(str(profile_id))
        assert options["definition_id"] == RECOVERY_STATUS_OPERATION_DEFINITION_ID
        return completion

    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: SimpleNamespace(bucket_id=profile_id))
    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    ctx = cast(typer.Context, cast(object, None))
    if fault in {None, "unenrolled"}:
        assert bridge.read_recovery_status(ctx) == result
    else:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            bridge.read_recovery_status(ctx)
        assert refused.value.context is not None
        assert refused.value.context["operation_id"] == completion.operation_id
        assert refused.value.context["effect"] == completion.effect.value


def test_recovery_status_preserves_missing_profile_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: None)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_recovery_status(cast(typer.Context, cast(object, None)))
    assert refused.value.translated_message == "cli.config.profile.recovery.no_active_profile"
