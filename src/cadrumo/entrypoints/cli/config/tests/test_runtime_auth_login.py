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


def test_headless_qr_link_survives_worker_error_transport() -> None:
    from io import StringIO

    from cadrumo.adapters.outbound.aeat.auth.errors import AuthConfigurationError
    from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
    from cadrumo.core.authentication_links import aeat_authentication_url
    from cadrumo.core.errors.error_codes import resolve_error_message
    from cadrumo.entrypoints.cli.errors import write_stderr
    from cadrumo.entrypoints.cli.registered_operation_errors import detailed_registered_operation_error

    url = aeat_authentication_url()
    error = AuthConfigurationError(
        translated_message="adapters.auth.clave_movil.errors.desktop_unavailable",
        context={"reason": "interactive_desktop_unavailable", "authentication_url": url},
    )
    detail = build_operation_error_detail(error)
    assert detail is not None
    received = OperationErrorDetailV1.model_validate_json(detail.model_dump_json())
    rendered = resolve_error_message(detailed_registered_operation_error(received, {}), locale="en")
    assert url in rendered
    assert "QR browser launch was refused" in rendered
    assert "%{" not in rendered
    output = StringIO()
    write_stderr(rendered, stream=output)
    assert url in output.getvalue()


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


@pytest.mark.parametrize("recorded", [True, False])
def test_failed_clave_login_renders_its_typed_cause_and_diagnostic_follow_up(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], recorded: bool
) -> None:
    from cadrumo.adapters.outbound.aeat.auth.clave_movil_support import (
        ClaveMovilApprovalTimeoutError,
        ClaveMovilFailureMode,
    )
    from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
    from cadrumo.core.errors.error_codes import get_registered_error_code
    from cadrumo.core.i18n.render import tr
    from cadrumo.entrypoints.cli.errors import CliUnexpectedBoundaryError, emit_error_and_exit
    from cadrumo.entrypoints.cli.registered_operation_errors import submitted_operation_error

    diagnostic_id = "20261003T120000.000000Z-" + "c" * 32
    worker_error = ClaveMovilApprovalTimeoutError(
        translated_message="adapters.auth.clave_movil.errors.approval_timeout",
        failure_mode=ClaveMovilFailureMode.AUTH_COMPLETION_TIMEOUT,
        context={"diagnostic_id": diagnostic_id, "phone_state": "unknown"},
    )
    detail = build_operation_error_detail(worker_error)
    assert detail is not None
    received = OperationErrorDetailV1.model_validate_json(detail.model_dump_json())
    stopped = submitted_operation_error(
        "a" * 64,
        OperationTerminalCondition.FAILED.value,
        terminal_condition=OperationTerminalCondition.FAILED,
        effect=OperationEffect.UNKNOWN,
        detail=received if recorded else None,
    )

    def submit(*_args: object, **_options: object) -> object:
        raise stopped

    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: SimpleNamespace(bucket_id=uuid4()))
    monkeypatch.setattr(bridge, "require_profile_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.run_auth_login(
            cast(typer.Context, cast(object, None)), provider="clave_movil", fresh=True, reset_lock=False
        )
    with pytest.raises(typer.Exit):
        emit_error_and_exit(refused.value)
    rendered = capsys.readouterr().err
    internal = tr(get_registered_error_code(CliUnexpectedBoundaryError).message_key)

    if not recorded:
        # Without the worker's detail only the generic internal fault remains.
        assert internal in rendered
        assert diagnostic_id not in rendered
        return
    assert tr("adapters.auth.clave_movil.errors.approval_timeout") in rendered
    assert f"Failure mode: {ClaveMovilFailureMode.AUTH_COMPLETION_TIMEOUT.value}" in rendered
    assert f"Diagnostic id: {diagnostic_id}" in rendered
    assert '"operator.auth.diagnostics.view"' in rendered
    assert '["config","auth","diagnostics","view"]' in rendered
    assert f'"value":"{diagnostic_id}"' in rendered
    assert internal not in rendered
