"""Installed runtime observations and explicit native management controls."""

from __future__ import annotations

import asyncio
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from cadrumo.adapters.local_runtime.runtime_manager_composition import installed_runtime_manager

from ..adapters.local_runtime.framing import RuntimeTransportCleanup, VerifiedRuntimeConnection
from ..adapters.local_runtime.management_status import probe_runtime_listener
from ..adapters.local_runtime.posix import PosixRuntimeEndpoint
from ..adapters.local_runtime.startup import RuntimeEndpointConnector, RuntimeLaunchDoor
from ..adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ..application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ..application.runtime.deadline_budget import deadline_after, require_finite_budget
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
from ..core.async_cleanup import await_cancellation_complete, close_async_resources, retain_merged_cleanup
from ..core.paths import effective_storage_root


def _installed_management_endpoint(*, storage_root: Path) -> WindowsRuntimeEndpoint | PosixRuntimeEndpoint:
    """Create the installed root's endpoint without creating a POSIX namespace."""
    if sys.platform == "win32":
        return WindowsRuntimeEndpoint(storage_root=storage_root)
    return PosixRuntimeEndpoint(storage_root=storage_root, create_namespace=False)


async def inspect_runtime_management(
    *,
    endpoint: RuntimeEndpointConnector,
    expected: RuntimeClientHello,
    manager: RuntimeUserManager | None,
    manager_if_absent: RuntimeManagerAvailability,
    timeout: float = 3,
) -> RuntimeManagementSnapshot:
    """Observe one exact owner and optional native manager without starting either."""
    deadline = deadline_after(timeout)
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
    require_finite_budget(timeout)
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        return RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNAVAILABLE,
            manager_availability=RuntimeManagerAvailability.UNKNOWN,
        )
    endpoint = _installed_management_endpoint(storage_root=root)
    try:
        expected = RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity)
        manager_state = (
            RuntimeManagerAvailability.UNSUPPORTED
            if sys.platform not in {"win32", "linux", "darwin"}
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
    require_finite_budget(timeout)
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = _installed_management_endpoint(storage_root=root)
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
    endpoint = _installed_management_endpoint(storage_root=root)
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
        self._connection_cleanup = RuntimeTransportCleanup(connection)
        self._endpoint_cleanup = RuntimeTransportCleanup(endpoint)
        self._confirmation: asyncio.Task[RuntimeStopAccepted | BaseException] | None = None
        self._confirmation_error: BaseException | None = None
        self._accepted: RuntimeStopAccepted | None = None
        self._refused = False

    @property
    def accepted(self) -> RuntimeStopAccepted | None:
        """Retain a validated acknowledgement, independently of native release."""
        return self._accepted

    @property
    def confirmation_started(self) -> bool:
        """Report a single-use dispatch that must never be replayed automatically."""
        return self._confirmation is not None

    @property
    def uncertain(self) -> bool:
        """Report a dispatched confirmation without acceptance or a typed refusal."""
        return self.confirmation_started and self._accepted is None and not self._refused

    @property
    def released(self) -> bool:
        """Report successful release of both actual native owners."""
        return self._connection_cleanup.released and self._endpoint_cleanup.released

    def _adopt_cleanup(self, error: BaseException | None) -> None:
        if error is not None:
            retained = error.__dict__.get("_runtime_transport_cleanup")
            if isinstance(retained, RuntimeTransportCleanup) and retained.resource is self._connection:
                self._connection_cleanup = retained

    async def confirm(self) -> RuntimeStopAccepted:
        """Acknowledge all profiles and work on the same native connection."""
        if self._closed or self.confirmation_started:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        request = RuntimeStopConfirm(
            request_id=uuid4(),
            runtime_boot_id=self.preview.runtime_boot_id,
            preview_id=self.preview.preview_id,
            acknowledge_all_profiles_and_work=True,
        )
        deadline = time.monotonic() + 5

        async def exchange() -> RuntimeStopAccepted | BaseException:
            try:
                reply = await asyncio.to_thread(self._connection.owner_control, request, deadline=deadline)
                if isinstance(reply, RuntimeAccessRefusal):
                    self._refused = True
                    reason = (
                        reply.code if isinstance(reply.code, RuntimeRefusalCode) else RuntimeRefusalCode.PEER_UNTRUSTED
                    )
                    raise RuntimeRefusalError(reason)
                if (
                    not isinstance(reply, RuntimeStopAccepted)
                    or reply.request_id != request.request_id
                    or reply.runtime_boot_id != self.preview.runtime_boot_id
                    or reply.connection_id != self.preview.connection_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                # Publish before the cancellation-complete boundary can re-raise
                # caller cancellation. Acceptance never certifies settled drain.
                self._accepted = reply
                return reply
            except BaseException as error:
                self._confirmation_error = error
                self._adopt_cleanup(error)
                return error

        self._confirmation = asyncio.create_task(exchange(), name="runtime-stop-confirm-exchange")
        try:
            outcome = await await_cancellation_complete(self._confirmation, task_name="runtime-stop-confirm")
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        except BaseException as error:
            retain_merged_cleanup(error, self._confirmation_error)
            raise

    async def release(self, *, primary_error: BaseException | None = None) -> None:
        """Fence confirmation and release native owners without replaying stop."""
        self._closed = True
        cancellation: asyncio.CancelledError | None = None
        confirmation = self._confirmation
        if confirmation is not None and not confirmation.done():
            try:
                await await_cancellation_complete(confirmation, task_name="runtime-stop-settle")
            except asyncio.CancelledError as error:
                cancellation = error
        self._adopt_cleanup(self._confirmation_error)
        self._adopt_cleanup(primary_error)
        if primary_error is not None:
            retain_merged_cleanup(primary_error, self._confirmation_error)
        try:
            await close_async_resources(
                self._connection_cleanup,
                self._endpoint_cleanup,
                task_name="runtime-stop-release",
                primary_error=primary_error,
                cancellation=cancellation,
            )
        except BaseException as error:
            retain_merged_cleanup(error, primary_error, self._confirmation_error)
            raise
        finally:
            if primary_error is not None:
                retain_merged_cleanup(primary_error)


async def preview_installed_runtime_stop(*, timeout: float = 5) -> RuntimeStopConsent:
    """Request owner consent on a fresh connection without launching a runtime."""
    require_finite_budget(timeout)
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = _installed_management_endpoint(storage_root=root)
    connection: VerifiedRuntimeConnection | None = None
    try:
        expected = RuntimeClientHello(product_version=product_version, storage_identity=endpoint.storage_identity)

        async def open_connection() -> None:
            nonlocal connection
            connection = await RuntimeLaunchDoor(endpoint, expected=expected).open(timeout=timeout)

        await await_cancellation_complete(open_connection(), task_name="runtime-stop-open")
        if connection is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        reply = await await_cancellation_complete(
            asyncio.to_thread(
                connection.owner_control,
                RuntimeStopPreviewRequest(request_id=uuid4()),
                deadline=deadline_after(timeout),
            ),
            task_name="runtime-stop-preview",
        )
        if isinstance(reply, RuntimeAccessRefusal):
            reason = reply.code if isinstance(reply.code, RuntimeRefusalCode) else RuntimeRefusalCode.PEER_UNTRUSTED
            raise RuntimeRefusalError(reason)
        if not isinstance(reply, RuntimeStopPreview):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return RuntimeStopConsent(endpoint=endpoint, connection=connection, preview=reply)
    except BaseException as primary:
        connection_owner = _runtime_stop_connection_owner(connection, primary)
        retain_merged_cleanup(primary)
        try:
            await close_async_resources(
                connection_owner,
                RuntimeTransportCleanup(endpoint),
                task_name="runtime-stop-preview-release",
                primary_error=primary,
            )
        except BaseException as error:
            retain_merged_cleanup(error, primary)
            raise
        retain_merged_cleanup(primary)
        raise


__all__ = [
    "RuntimeStopConsent",
    "configure_installed_runtime_management",
    "inspect_installed_runtime_management",
    "inspect_runtime_management",
    "preview_installed_runtime_stop",
    "start_installed_runtime_management",
]


def _runtime_stop_connection_owner(
    connection: VerifiedRuntimeConnection | None, primary: BaseException
) -> RuntimeTransportCleanup | None:
    """Reuse the retained native connection owner before composing release resources."""
    connection_owner: RuntimeTransportCleanup | None = None
    if connection is not None:
        retained = primary.__dict__.get("_runtime_transport_cleanup")
        connection_owner = (
            retained
            if isinstance(retained, RuntimeTransportCleanup) and retained.resource is connection
            else RuntimeTransportCleanup(connection)
        )
    return connection_owner
