"""One storage root holding a real encrypted profile, served by the real runtime with the profile acts.

The profile is created through the command line's own ``create`` verb, so a
command run in the test's process and an act served by the runtime meet the
same capsule under the same pinned authority.
"""

from __future__ import annotations

import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.core.bucket_pointer import require_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.tests.command_line_rendering import command_result

from ..installation_profiles import register_profile_acts
from .installation_registered_runtime import serving_registered_runtime
from .installation_runtime import InstallationLogin

PROFILE_LABEL = "Parity Subject"
PROFILE_INPUT = "a-sufficiently-long-operator-passphrase"


@dataclass(frozen=True, slots=True)
class ServedInstallation:
    """The storage root, its one profile, and the endpoint of the runtime serving it."""

    root: Path
    profile_id: UUID
    endpoint: WindowsRuntimeEndpoint


def installation_client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    """Open one verified connection to the runtime serving ``endpoint``."""
    return RuntimeInstallationClient(
        VerifiedRuntimeConnection(
            endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


@contextmanager
def serving_profile_acts(root: Path) -> Generator[WindowsRuntimeEndpoint]:
    """Serve the profile acts over ``root`` with a credential store held in memory."""
    native = MemoryNativePort()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    with serving_registered_runtime(
        endpoint, root, InstallationLogin(owner=owner_id()), register_profile_acts, secret_store=lambda: native
    ):
        yield endpoint


@contextmanager
def served_installation(tmp_path: Path) -> Generator[ServedInstallation]:
    """Create one profile with the ``create`` verb, close its session, and serve its root."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    with isolated_profile_storage_root(tmp_path=tmp_path), override_settings(cadrumo_output_language="en"):
        try:
            command_result(
                "config",
                "profile",
                "create",
                PROFILE_LABEL,
                "--quiet",
                "--secrets-stdin",
                stdin=json.dumps({"passphrase": PROFILE_INPUT, "passphrase_confirmation": PROFILE_INPUT}),
            )
            profile_id = UUID(require_active_bucket_id())
        finally:
            close_active_bucket_session()
        with serving_profile_acts(root) as endpoint:
            yield ServedInstallation(root=root, profile_id=profile_id, endpoint=endpoint)
