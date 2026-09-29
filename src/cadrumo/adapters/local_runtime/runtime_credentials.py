"""Fresh installed API admission from an exact protected credential reference."""

from __future__ import annotations

import asyncio
import math
import sys
import time
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import read_runtime_installation
from cadrumo.adapters.local_runtime.posix import posix_owner_uid, posix_storage_identity
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.paths import effective_storage_root


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _authenticate_reference(
    client: RuntimeFrontendClient,
    *,
    root: Path,
    credential_reference: UUID,
    secrets_store: AutomationSecretStore | None,
    deadline: float,
) -> None:
    """Read native custody only after verified transport, then prove the key afresh."""
    _remaining(deadline)
    if sys.platform == "win32":
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        try:
            storage_identity, owner = endpoint.storage_identity, endpoint.os_owner_id
        finally:
            endpoint.close()
    else:
        storage_identity, owner = posix_storage_identity(root), str(posix_owner_uid())
    if storage_identity != client.storage_identity:
        raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
    installation = read_runtime_installation(storage_root=root, os_owner_id=owner, storage_identity=storage_identity)
    binding = current_automation_profile_binding(
        profile_id=client.profile_id, installation_id=installation.installation_id, os_owner_id=owner, root=root
    )
    handle = NativeClientCredentialStore.resolve_reference(
        credential_reference=credential_reference,
        binding=binding,
        secrets_store=secrets_store if secrets_store is not None else installed_automation_secret_store(),
    )
    proof = bytearray(handle.read().get_secret_value())
    try:
        client.login_api_key(proof, timeout=_remaining(deadline))
    finally:
        proof[:] = bytes(len(proof))


async def open_installed_credential_client(
    *,
    profile_id: UUID,
    credential_reference: UUID,
    frontend: OperationFrontendProjection,
    timeout: float = 30,
    secrets_store: AutomationSecretStore | None = None,
) -> RuntimeFrontendClient:
    """Own a newly admitted exact-profile client without exporting its key.

    An explicit native port may be supplied by trusted composition. Ordinary
    callers use the installed non-prompting platform port. The reference is not
    authentication: native peer checks, current custody and fresh API proof
    must all succeed. Failure or cancellation closes only this new connection.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    deadline = time.monotonic() + timeout
    try:
        root = effective_storage_root().resolve(strict=True)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    client = await open_installed_runtime_client(profile_id=profile_id, frontend=frontend, timeout=_remaining(deadline))
    try:
        await await_cancellation_complete(
            asyncio.to_thread(
                _authenticate_reference,
                client,
                root=root,
                credential_reference=credential_reference,
                secrets_store=secrets_store,
                deadline=deadline,
            ),
            task_name="runtime-credential-admission",
        )
        return client
    except BaseException:
        await await_cancellation_complete(asyncio.to_thread(client.close), task_name="runtime-credential-cleanup")
        raise
