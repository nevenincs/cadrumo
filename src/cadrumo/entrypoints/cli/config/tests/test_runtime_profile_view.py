"""Installed CLI profile view reads one encrypted profile through native IPC."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-runtime-view-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply only test-owned login facts for the native profile worker."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_named_profile_view_uses_installed_runtime_and_preserves_cli_envelope(tmp_path: Path) -> None:
    """A named CLI view authenticates and projects the selected encrypted record."""
    with worker_profiles(tmp_path) as (root, targets):
        selected_id = targets[0][0].binding.profile_id
        other_id = targets[1][0].binding.profile_id
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                    shown = invoke_cached_cli(
                        (
                            "--format",
                            "json",
                            "--profile",
                            "Worker profile 0",
                            "--profile-secrets-stdin",
                            "config",
                            "profile",
                            "view",
                        ),
                        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
                    )
                assert shown.exit_code == 0, shown.output
                document = json.loads(shown.stdout)
                assert document["command"] == "config.profile.view"
                assert document["result"]["profile_id"] == "<profile-id>"
                assert str(selected_id) not in shown.output
                assert str(other_id) not in shown.output
                assert document["result"]["display_name"] == "Worker profile 0"
                assert document["result"]["setup_state"] == "incomplete"
                assert document["result"]["valid"] is True
                assert any(issue["code"] == "required_field_missing" for issue in document["result"]["issues"])
                assert all("passphrase" not in fact["path"] for fact in document["result"]["facts"])
                assert PROFILE_INPUT not in shown.output
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
