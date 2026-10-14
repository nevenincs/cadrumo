"""Fresh installed API admission from an exact protected credential reference."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessScope
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.paths import effective_storage_root

from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.deadline_budget import deadline_after, remaining_budget
from ..contracts.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from .frontend_client import FrontendClient
from .installation import read_runtime_installation
from .installed_client import open_installed_client
from .posix import posix_owner_uid, posix_storage_identity
from .windows import WindowsEndpoint


@dataclass(frozen=True, slots=True)
class _CredentialClientCleanup:
    """Keep a failed admission's native connection available for cleanup retry."""

    client: FrontendClient

    async def close(self) -> None:
        await asyncio.to_thread(self.client.close)


def _authenticate_reference(
    client: FrontendClient,
    *,
    root: Path,
    credential_reference: UUID,
    secrets_store: AutomationSecretStore | None,
    deadline: float,
) -> None:
    """Read native custody only after verified transport, then prove the key afresh."""
    remaining_budget(deadline)
    if sys.platform == "win32":
        endpoint = WindowsEndpoint(storage_root=root)
        try:
            storage_identity, owner = endpoint.storage_identity, endpoint.os_owner_id
        finally:
            endpoint.close()
    else:
        storage_identity, owner = posix_storage_identity(root), str(posix_owner_uid())
    if storage_identity != client.storage_identity:
        raise RefusalError(RefusalCode.ROOT_MISMATCH)
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
        client.login_api_key(proof, timeout=remaining_budget(deadline))
    finally:
        proof[:] = bytes(len(proof))


async def open_installed_credential_client(
    *,
    profile_id: UUID,
    credential_reference: UUID,
    frontend: OperationFrontendProjection,
    timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS,
    secrets_store: AutomationSecretStore | None = None,
    on_connected: Callable[[FrontendClient], None] | None = None,
    scope: AccessScope | None = None,
) -> FrontendClient:
    """Own a newly admitted exact-profile client without exporting its key.

    An explicit native port may be supplied by trusted composition. Ordinary
    callers use the installed non-prompting platform port. The reference is not
    authentication: native peer checks, current custody and fresh API proof
    must all succeed. Failure or cancellation closes only this new connection.
    An optional explicit scope narrows the API-key admission.
    """
    deadline = deadline_after(timeout)
    try:
        root = effective_storage_root().resolve(strict=True)
    except OSError:
        raise RefusalError(RefusalCode.UNAVAILABLE) from None
    client = await open_installed_client(
        profile_id=profile_id, frontend=frontend, timeout=remaining_budget(deadline), scope=scope
    )
    try:
        if on_connected is not None:
            on_connected(client)
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
    except BaseException as error:
        await close_async_resources(
            _CredentialClientCleanup(client), task_name="runtime-credential-cleanup", primary_error=error
        )
        raise
