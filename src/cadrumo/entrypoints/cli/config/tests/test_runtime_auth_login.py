"""Provider login preserves the worker's exact receipt at the CLI boundary."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import typer
from pydantic import BaseModel

from .....application.auth.operation_definitions import (
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    AuthSessionAcquireOperationRequest,
)
from .....application.auth.operator_results import AuthLoginResult
from .....application.auth.session_acquire_operation_access import AuthSessionAcquireOperationProjection
from .....core.auth_provider import AuthProviderKind
from .....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...errors import CliRefusedBoundaryError
from ...registered_operation_contracts import RegisteredOperationCompletion
from .. import runtime_auth_login as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("fault", [None, "profile", "provider", "fresh", "authentication", "effect", "terminal"])
def test_login_uses_registered_worker_and_correlates_terminal_outcome(
    monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    profile_id = uuid4()
    client = SimpleNamespace(profile_id=profile_id)
    calls: list[tuple[BaseModel, dict[str, object]]] = []
    result = AuthLoginResult(
        provider="clave_movil" if fault == "provider" else "certificate",
        authenticated=fault != "authentication",
        reused_persisted_session=False,
        fresh=fault != "fresh",
        removed_sessions=1,
        acquired_lock=True,
        verification_status="verified",
    )
    completion = RegisteredOperationCompletion(
        operation_id="a" * 64,
        projection=AuthSessionAcquireOperationProjection(
            profile_id=uuid4() if fault == "profile" else profile_id, result=result
        ),
        effect=OperationEffect.UNKNOWN if fault == "effect" else OperationEffect.UPDATED,
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
    ) -> RegisteredOperationCompletion[AuthSessionAcquireOperationProjection]:
        assert actual_client is client
        calls.append((request, options))
        return completion

    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: SimpleNamespace(bucket_id=profile_id))
    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    ctx = cast(typer.Context, cast(object, None))
    if fault is None:
        assert bridge.run_auth_login(ctx, provider="certificate", fresh=True, reset_lock=True) == result
    else:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            bridge.run_auth_login(ctx, provider="certificate", fresh=True, reset_lock=True)
        assert refused.value.context is not None
        assert refused.value.context["operation_id"] == completion.operation_id
        assert refused.value.context["effect"] == completion.effect.value
        assert refused.value.context["terminal_condition"] == completion.terminal_condition.value
    request, options = calls[0]
    assert request == AuthSessionAcquireOperationRequest(
        provider=AuthProviderKind.CERTIFICATE, fresh=True, reset_lock=True
    )
    assert options["subject_ref"] == profile_operation_subject(str(profile_id))
    assert options["definition_id"] == AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID


def test_unknown_provider_refuses_before_opening_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected() -> None:
        raise AssertionError("invalid provider must not reach profile admission")

    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", unexpected)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.run_auth_login(
            cast(typer.Context, cast(object, None)), provider="unknown", fresh=False, reset_lock=False
        )
    assert refused.value.translated_message == "cli.config.auth.unknown_provider"
