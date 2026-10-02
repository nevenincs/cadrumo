"""One installed per-user manager composition for runtime clients and status."""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

from cadrumo.adapters.local_runtime.linux_manager import LinuxUserManager
from cadrumo.adapters.local_runtime.macos_manager import MacosUserManager
from cadrumo.adapters.local_runtime.posix import PosixRuntimeEndpoint, posix_owner_uid
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_manager import WindowsTaskManager
from cadrumo.application.runtime.management import RuntimeServiceBinding, RuntimeUserManager


def installed_runtime_binding(
    *, root: Path, endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint, product_version: str
) -> RuntimeServiceBinding | None:
    """Bind an existing installed executable to the native owner and exact root."""
    executable = Path(sysconfig.get_path("scripts")) / (
        "cadrumo-runtime.exe" if sys.platform == "win32" else "cadrumo-runtime"
    )
    # A running owner remains usable without manager provisioning. Never
    # search PATH or generate a deployment during ordinary admission/status.
    if not executable.is_file():
        return None
    owner = endpoint.os_owner_id if isinstance(endpoint, WindowsRuntimeEndpoint) else str(posix_owner_uid())
    return RuntimeServiceBinding(
        executable=str(executable.resolve()),
        storage_root=str(root),
        storage_identity=endpoint.storage_identity,
        os_owner_id=owner,
        product_version=product_version,
    )


def installed_runtime_manager(
    *, root: Path, endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint, product_version: str
) -> RuntimeUserManager | None:
    """Select only an existing installed executable; never provision or control."""
    binding = installed_runtime_binding(root=root, endpoint=endpoint, product_version=product_version)
    if binding is None:
        return None
    if sys.platform == "win32":
        return WindowsTaskManager(binding)
    if sys.platform == "linux":
        return LinuxUserManager(binding)
    if sys.platform == "darwin":
        return MacosUserManager(binding)
    return None


__all__ = ["installed_runtime_binding", "installed_runtime_manager"]
