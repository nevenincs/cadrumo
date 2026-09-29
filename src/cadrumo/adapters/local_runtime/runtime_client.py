"""Shared installed composition for authenticated frontend transport."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.posix import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.runtime_manager_composition import installed_runtime_manager
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.paths import effective_storage_root


async def open_installed_runtime_client(
    *, profile_id: UUID, frontend: OperationFrontendProjection, timeout: float = 10
) -> RuntimeFrontendClient:
    """Connect to the exact installed owner, or start existing bound provisioning.

    This opens no profile and reads no credential. The caller must explicitly
    authenticate the returned connection and own it for its frontend lifetime.
    Unsupported deployment refuses without enabling startup or direct spawning.
    """
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root)
    )
    try:
        launch = RuntimeLaunchDoor(
            endpoint,
            expected=RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity),
            manager_factory=lambda: installed_runtime_manager(
                root=root, endpoint=endpoint, product_version=product_version
            ),
        )
        return await RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=frontend, timeout=timeout)
    finally:
        endpoint.close()
