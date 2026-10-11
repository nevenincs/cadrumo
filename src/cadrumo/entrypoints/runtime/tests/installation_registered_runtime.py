"""A real runtime that serves the installation acts a family package registers.

The native transport, the connection service, the installation door and the
framing are the real ones, and so are the handlers: the registry is built by the
package's own registration function, not by the test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import uuid4

from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore

from ..installation_composition import InstallationActRegistry
from ..profile_connections import RuntimeProfileConnections
from .installation_runtime import InstallationLogin


@contextmanager
def serving_registered_runtime(
    endpoint: WindowsRuntimeEndpoint,
    root: Path,
    login: InstallationLogin,
    register: Callable[[InstallationActRegistry], None],
    *,
    secret_store: Callable[[], AutomationSecretStore] = installed_automation_secret_store,
    product_version: str = "test",
) -> Iterator[RuntimeProfileConnections]:
    """Serve the real transport over ``root`` with the acts ``register`` adds, then drain it."""
    registry = InstallationActRegistry()
    register(registry)
    stop, boot = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _channel: login,
        secret_store=secret_store,
        installation_acts=registry,
    )
    server = RetainedRuntimeTransportServer(
        endpoint, product_version=product_version, stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(server.serve)
        try:
            if not server.ready.wait(3):
                raise TimeoutError("the installation test runtime did not become ready")
            yield profiles
        finally:
            stop.set()
            running.result(timeout=25)
