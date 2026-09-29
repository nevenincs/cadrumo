"""The public CLI reports installed runtime management without profile admission."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from ....adapters.local_runtime.server import RuntimeTransportServer
from ....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ....application.operator_surface.command_ports import ProfileAuthenticationPosture
from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.runtime.management_status import RuntimeListenerState, RuntimeManagerAvailability
from ....core.config import override_settings
from ....tests.cli_envelope import require_error_document, unwrap_schema_envelope
from .._profile_authentication_contract import command_needs_state_tree, profile_authentication_posture
from ..command_specs import COMMAND_GRAPH
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.hex_entrypoint]


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
