"""Installed runtime observations and explicit native management controls."""

from __future__ import annotations

import asyncio
import math
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from cadrumo.adapters.local_runtime.runtime_manager_composition import installed_runtime_manager

from ..adapters.local_runtime.framing import VerifiedRuntimeConnection
from ..adapters.local_runtime.management_status import probe_runtime_listener
from ..adapters.local_runtime.posix import PosixRuntimeEndpoint
from ..adapters.local_runtime.startup import RuntimeEndpointConnector, RuntimeLaunchDoor
from ..adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ..application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ..application.runtime.management import (
    RuntimeConfigurableUserManager,
    RuntimeManagerInspection,
    RuntimeUserManager,
)
from ..application.runtime.management_status import (
    RuntimeListenerState,
    RuntimeManagementSnapshot,
    RuntimeManagerAvailability,
)
from ..application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from ..application.runtime.profile_access import RuntimeAccessRefusal
from ..core.async_cleanup import await_cancellation_complete
from ..core.paths import effective_storage_root


async def inspect_runtime_management(
    *,
    endpoint: RuntimeEndpointConnector,
    expected: RuntimeClientHello,
    manager: RuntimeUserManager | None,
    manager_if_absent: RuntimeManagerAvailability,
    timeout: float = 3,
) -> RuntimeManagementSnapshot:
    """Observe one exact owner and optional native manager without starting either."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    deadline = time.monotonic() + timeout
    facts: RuntimeManagerInspection | None = None
    if manager is None:
        manager_state = manager_if_absent
    else:
        try:
            facts = await asyncio.wait_for(manager.inspect(), timeout=max(0.0, deadline - time.monotonic()))
            manager_state = (
                RuntimeManagerAvailability.AVAILABLE if facts.available else RuntimeManagerAvailability.UNAVAILABLE
            )
        except RuntimeRefusalError as error:
            if error.reason is RuntimeRefusalCode.UNAVAILABLE:
                manager_state = RuntimeManagerAvailability.UNAVAILABLE
            elif error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                manager_state = RuntimeManagerAvailability.UNKNOWN
            else:
                manager_state = RuntimeManagerAvailability.REFUSED
        except (TimeoutError, OSError):
            manager_state = RuntimeManagerAvailability.UNKNOWN
    # The connector is owned by the caller. Finish its bounded thread before
    # that caller may close native handles, including on task cancellation.
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNKNOWN, manager_availability=manager_state, manager=facts
        )
    listener = await await_cancellation_complete(
        asyncio.to_thread(probe_runtime_listener, endpoint, expected=expected, timeout=remaining),
        task_name="runtime-management-status-probe",
    )
    return RuntimeManagementSnapshot(listener=listener, manager_availability=manager_state, manager=facts)


async def inspect_installed_runtime_management(*, timeout: float = 3) -> RuntimeManagementSnapshot:
    """Compose the installed root's exact manager and a passive verified probe."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        return RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNAVAILABLE,
            manager_availability=RuntimeManagerAvailability.UNKNOWN,
        )
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root, create_namespace=False)
    )
    try:
        expected = RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity)
        manager_state = (
            RuntimeManagerAvailability.UNSUPPORTED
            if sys.platform not in {"win32", "linux"}
            else RuntimeManagerAvailability.UNAVAILABLE
        )
        try:
            manager = installed_runtime_manager(root=root, endpoint=endpoint, product_version=product_version)
        except RuntimeRefusalError:
            manager = None
            manager_state = RuntimeManagerAvailability.REFUSED
        except OSError:
            manager = None
            manager_state = RuntimeManagerAvailability.UNKNOWN
        return await inspect_runtime_management(
            endpoint=endpoint,
            expected=expected,
            manager=manager,
            manager_if_absent=manager_state,
            timeout=timeout,
        )
    finally:
        endpoint.close()


async def start_installed_runtime_management(*, timeout: float = 10) -> RuntimeManagementSnapshot:
    """Open the owner-verified launch door and report the resulting state."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root, create_namespace=False)
    )
    try:
        expected = RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity)
        manager = installed_runtime_manager(root=root, endpoint=endpoint, product_version=product_version)
        connection = await RuntimeLaunchDoor(endpoint, expected=expected, manager=manager).open(timeout=timeout)
        connection.close()
        return await inspect_runtime_management(
            endpoint=endpoint,
            expected=expected,
            manager=manager,
            manager_if_absent=RuntimeManagerAvailability.UNAVAILABLE,
        )
    finally:
        endpoint.close()


async def configure_installed_runtime_management(*, login_autostart: bool) -> RuntimeManagerInspection:
    """Apply explicit login startup on a platform that exposes this capability."""
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root, create_namespace=False)
    )
    try:
        manager = installed_runtime_manager(root=root, endpoint=endpoint, product_version=product_version)
        if not isinstance(manager, RuntimeConfigurableUserManager):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return await manager.configure(login_autostart=login_autostart)
    finally:
        endpoint.close()


class RuntimeStopConsent:
    """Own one preview and its dedicated verified connection until confirmation."""

    def __init__(
        self,
        *,
        endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint,
        connection: VerifiedRuntimeConnection,
        preview: RuntimeStopPreview,
    ) -> None:
        """Retain the exact native connection on which preview was issued."""
        self.preview = preview
        self._endpoint = endpoint
        self._connection = connection
        self._closed = False

    async def confirm(self) -> RuntimeStopAccepted:
        """Acknowledge all profiles and work on the same native connection."""
        if self._closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        request = RuntimeStopConfirm(
            request_id=uuid4(),
            runtime_boot_id=self.preview.runtime_boot_id,
            preview_id=self.preview.preview_id,
            acknowledge_all_profiles_and_work=True,
        )
        try:
            reply = await await_cancellation_complete(
                asyncio.to_thread(self._connection.owner_control, request, deadline=time.monotonic() + 5),
                task_name="runtime-stop-confirm",
            )
            if isinstance(reply, RuntimeAccessRefusal):
                reason = reply.code if isinstance(reply.code, RuntimeRefusalCode) else RuntimeRefusalCode.PEER_UNTRUSTED
                raise RuntimeRefusalError(reason)
            if not isinstance(reply, RuntimeStopAccepted):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return reply
        finally:
            self.close()

    def close(self) -> None:
        """Discard a preview without changing the shared runtime."""
        if not self._closed:
            self._closed = True
            try:
                self._connection.close()
            finally:
                self._endpoint.close()


async def preview_installed_runtime_stop(*, timeout: float = 5) -> RuntimeStopConsent:
    """Request owner consent on a fresh connection without launching a runtime."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root, create_namespace=False)
    )
    connection: VerifiedRuntimeConnection | None = None
    try:
        expected = RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity)
        connection = await RuntimeLaunchDoor(endpoint, expected=expected).open(timeout=timeout)
        reply = await await_cancellation_complete(
            asyncio.to_thread(
                connection.owner_control,
                RuntimeStopPreviewRequest(request_id=uuid4()),
                deadline=time.monotonic() + timeout,
            ),
            task_name="runtime-stop-preview",
        )
        if isinstance(reply, RuntimeAccessRefusal):
            reason = reply.code if isinstance(reply.code, RuntimeRefusalCode) else RuntimeRefusalCode.PEER_UNTRUSTED
            raise RuntimeRefusalError(reason)
        if not isinstance(reply, RuntimeStopPreview):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return RuntimeStopConsent(endpoint=endpoint, connection=connection, preview=reply)
    except BaseException:
        if connection is not None:
            connection.close()
        endpoint.close()
        raise


__all__ = [
    "RuntimeStopConsent",
    "configure_installed_runtime_management",
    "inspect_installed_runtime_management",
    "inspect_runtime_management",
    "preview_installed_runtime_stop",
    "start_installed_runtime_management",
]
