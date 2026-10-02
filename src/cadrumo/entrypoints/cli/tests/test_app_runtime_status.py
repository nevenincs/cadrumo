"""The public CLI reports installed runtime management without profile admission."""

from __future__ import annotations

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
import typer
import typer.main

from ....adapters.local_runtime.server import RuntimeTransportServer
from ....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ....application.operator_surface.command_ports import ProfileAuthenticationPosture
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.management_status import RuntimeListenerState, RuntimeManagerAvailability
from ....core.async_cleanup import AsyncResourceCleanupError
from ....core.config import override_settings
from ....tests.cli_envelope import require_error_document, unwrap_schema_envelope
from ...runtime_management import RuntimeStopConsent
from ...tests.test_runtime_management import StopFixture
from .._profile_authentication_contract import command_needs_state_tree, profile_authentication_posture
from ..app_runtime import runtime_stop
from ..app_runtime_payloads import RuntimeStopResult
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.hex_entrypoint]


def _stop_context() -> typer.Context:
    app = typer.Typer()
    app.command()(runtime_stop)
    return typer.Context(typer.main.get_command(app))


@pytest.mark.unit
def test_stop_reports_accepted_ack_before_cleanup_failure_and_retains_retry_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = StopFixture(channel_failures=2)
    results: list[RuntimeStopResult] = []
    monkeypatch.setattr("cadrumo.entrypoints.cli.app_runtime.preview_installed_runtime_stop", fixture.open)
    monkeypatch.setattr(
        "cadrumo.entrypoints.cli.app_runtime.emit_envelope", lambda _ctx, **kwargs: results.append(kwargs["result"])
    )
    context = _stop_context()
    with pytest.raises(AsyncResourceCleanupError) as failed:
        runtime_stop(context, acknowledge_all_profiles_and_work=True)
    assert len(results) == 1
    result = results[0]
    assert result.runtime_boot_id == fixture.channel.boot
    assert result.scope == "all_profiles_and_work"
    assert fixture.consent.accepted is not None
    assert fixture.channel.close_calls == fixture.endpoint.close_calls == 1
    with pytest.raises(AsyncResourceCleanupError) as retry_failed:
        asyncio.run(failed.value.retry_cleanup())
    asyncio.run(retry_failed.value.retry_cleanup())
    assert fixture.channel.close_calls == 3 and fixture.endpoint.close_calls == 1
    assert fixture.channel.confirmations == 1 and fixture.consent.released


@pytest.mark.unit
def test_stop_mapping_keeps_original_refusal_with_native_retry_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = StopFixture(channel_failures=2, outcome="lost")
    results: list[object] = []
    monkeypatch.setattr("cadrumo.entrypoints.cli.app_runtime.preview_installed_runtime_stop", fixture.open)
    monkeypatch.setattr(
        "cadrumo.entrypoints.cli.app_runtime.emit_envelope", lambda _ctx, **kwargs: results.append(kwargs["result"])
    )
    context = _stop_context()
    with pytest.raises(RuntimeRefusalError) as failed:
        runtime_stop(context, acknowledge_all_profiles_and_work=True)
    assert failed.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert results == [] and fixture.consent.uncertain
    cleanup = failed.value.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert fixture.channel.close_calls == 2
    asyncio.run(cleanup.retry_cleanup())
    assert fixture.channel.close_calls == 3 and fixture.channel.confirmations == 1


@pytest.mark.unit
@pytest.mark.parametrize("outcome", ["lost", "refused"])
def test_stop_mapping_distinguishes_unknown_dispatch_from_explicit_refusal(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    fixture = StopFixture(outcome="lost" if outcome == "lost" else "refused")
    monkeypatch.setattr("cadrumo.entrypoints.cli.app_runtime.preview_installed_runtime_stop", fixture.open)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        runtime_stop(_stop_context(), acknowledge_all_profiles_and_work=True)
    assert refused.value.context is not None
    assert refused.value.context["stop_outcome"] == ("unknown" if outcome == "lost" else "refused")
    assert fixture.channel.confirmations == 1 and fixture.consent.released
    assert fixture.channel.close_calls == fixture.endpoint.close_calls == 1


@pytest.mark.unit
def test_stop_output_failure_keeps_pending_cancellation_and_native_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = StopFixture(channel_failures=1)
    fixture.channel.continue_reply.clear()
    observed: list[asyncio.CancelledError] = []
    cancellers: list[asyncio.Task[None]] = []
    rendering = OSError("synthetic hidden output detail")

    original_confirm = fixture.consent.confirm

    async def confirm() -> object:
        try:
            return await original_confirm()
        except asyncio.CancelledError as error:
            observed.append(error)
            raise

    async def opened() -> RuntimeStopConsent:
        caller = asyncio.current_task()
        assert caller is not None

        async def cancel_after_dispatch() -> None:
            assert await asyncio.to_thread(fixture.channel.confirming.wait, 2)
            caller.cancel("original-cli-stop-cancellation")
            fixture.channel.continue_reply.set()

        cancellers.append(asyncio.create_task(cancel_after_dispatch()))
        return fixture.consent

    def failed_output(_ctx: object, **_kwargs: object) -> None:
        raise rendering

    monkeypatch.setattr("cadrumo.entrypoints.cli.app_runtime.preview_installed_runtime_stop", opened)
    monkeypatch.setattr(fixture.consent, "confirm", confirm)
    monkeypatch.setattr("cadrumo.entrypoints.cli.app_runtime.emit_envelope", failed_output)
    try:
        with pytest.raises(asyncio.CancelledError) as cancelled:
            runtime_stop(_stop_context(), acknowledge_all_profiles_and_work=True)
        assert observed == [cancelled.value] and observed[0] is cancelled.value
        assert cancelled.value.args == ("original-cli-stop-cancellation",)
        assert cancelled.value.__dict__.get("runtime_stop_output_error") is rendering
        assert fixture.consent.accepted is not None
        cleanup = cancelled.value.__dict__.get("async_cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
        assert fixture.channel.close_calls == fixture.endpoint.close_calls == 1
        asyncio.run(cleanup.retry_cleanup())
        assert fixture.consent.released and fixture.channel.close_calls == 2
        assert fixture.channel.confirmations == 1
    finally:
        fixture.channel.continue_reply.set()


@pytest.mark.unit
def test_runtime_status_is_a_profile_free_public_app_leaf() -> None:
    node = COMMAND_GRAPH.node("app_runtime_status")
    assert node.path == ("aeat", "app", "runtime", "status")
    assert profile_authentication_posture(node) is ProfileAuthenticationPosture.NOT_APPLICABLE
    assert not command_needs_state_tree(node)
    assert node.spec.parameters == ()
    assert node.spec.result_schema.identity == "app.runtime.status"


@pytest.mark.unit
@pytest.mark.parametrize("action", ("start", "enable", "disable", "stop"))
def test_runtime_management_leaves_are_configuration_only(action: str) -> None:
    """Runtime control leaves stay reachable without opening profile state."""
    node = COMMAND_GRAPH.node(f"app_runtime_{action}")
    assert node.path == ("aeat", "app", "runtime", action)
    assert profile_authentication_posture(node) is ProfileAuthenticationPosture.NOT_APPLICABLE
    assert command_needs_state_tree(node)


@pytest.mark.integration
def test_missing_runtime_root_reports_unavailable_without_provisioning_or_credentials(tmp_path: Path) -> None:
    missing = tmp_path / "no-runtime-installed"
    with override_settings(cadrumo_local_storage_root=missing):
        result = invoke_cached_cli(["--format", "json", "app", "runtime", "status"])
    assert result.exit_code == 0, result.output
    # The common CLI bootstrap may create its ordinary cache, but this leaf
    # must not install or provision a runtime manager/listener.
    assert not (missing / ".runtime").exists()
    document = json.loads(result.output)
    assert document["command"] == "app.runtime.status"
    projected = unwrap_schema_envelope(result.output)
    assert projected["listener"] == RuntimeListenerState.UNAVAILABLE.value
    assert projected["manager_availability"] in {state.value for state in RuntimeManagerAvailability}
    if projected["manager"] is not None:
        assert not projected["manager"]["provisioned"]
    assert all(private not in result.output for private in ("authenticated", "storage_root", "os_owner_id", "grant_id"))


@pytest.mark.integration
def test_profile_secret_source_is_refused_before_a_passive_status_read(tmp_path: Path) -> None:
    missing = tmp_path / "no-runtime-installed"
    credential = "status-must-not-read-this-proof"
    with override_settings(cadrumo_local_storage_root=missing):
        result = invoke_cached_cli(
            ["--format", "json", "--profile-secrets-stdin", "app", "runtime", "status"],
            input=credential,
        )
    assert result.exit_code == 2, result.output
    assert require_error_document(result.output)["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert credential not in result.output
    assert not missing.exists()


@pytest.mark.integration
@pytest.mark.parametrize("action", ("start", "enable", "disable", "stop"))
def test_runtime_management_rejects_profile_secrets_before_manager_dispatch(tmp_path: Path, action: str) -> None:
    """Profile-secret input cannot reach a runtime manager control action."""
    missing = tmp_path / "no-runtime-installed"
    credential = "runtime-control-must-not-read-this-proof"
    with override_settings(cadrumo_local_storage_root=missing):
        result = invoke_cached_cli(
            ["--format", "json", "--profile-secrets-stdin", "app", "runtime", action],
            input=credential,
        )
    assert result.exit_code == 2
    assert require_error_document(result.output)["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert credential not in result.output
    assert not missing.exists()


@pytest.mark.integration
def test_runtime_stop_requires_acknowledgement_before_manager_dispatch(tmp_path: Path) -> None:
    """The bootstrap-exempt stop leaf refuses absent consent before contacting a manager."""
    missing = tmp_path / "no-runtime-installed"
    with override_settings(cadrumo_local_storage_root=missing):
        result = invoke_cached_cli(["--format", "json", "app", "runtime", "stop"])
    assert result.exit_code == 2
    error = require_error_document(result.output)
    assert error["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert error["error"]["context"]["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows owner-only pipes")
def test_existing_listener_is_reported_ready_without_profile_login_or_manager_start(tmp_path: Path) -> None:
    root = tmp_path / f"public-status-{uuid4()}"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    stop = Event()
    server = RuntimeTransportServer(endpoint, product_version=version("cadrumo"), stop=stop)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool, override_settings(cadrumo_local_storage_root=root):
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                result = invoke_cached_cli(["--format", "json", "app", "runtime", "status"])
                assert result.exit_code == 0, result.output
                projected = unwrap_schema_envelope(result.output)
                assert projected["listener"] == RuntimeListenerState.READY.value
                assert projected["manager_availability"] in {
                    RuntimeManagerAvailability.AVAILABLE.value,
                    RuntimeManagerAvailability.UNAVAILABLE.value,
                }
                assert not stop.is_set()
                assert "authenticated" not in result.output
            finally:
                stop.set()
                running.result(timeout=10)
    finally:
        endpoint.close()
