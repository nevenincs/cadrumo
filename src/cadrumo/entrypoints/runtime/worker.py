"""Installed profile worker: native parent verification precedes all private custody."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import cast
from uuid import UUID

from ...adapters.local_runtime.framing import VerifiedRuntimeConnection
from ...adapters.local_runtime.posix_channel import PosixRuntimeChannel
from ...adapters.local_runtime.runtime_frame_io import read_document, write_document
from ...adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.local_runtime.worker_native_identity import worker_operation_namespace
from ...adapters.local_runtime.worker_transport import WorkerChannel, worker_endpoint
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_worker import (
    ProfileWorkerIdentity,
)
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    close_async_resources,
)
from ...core.config import override_settings
from ..adapter_composition import profile_adapter_composition
from ..exchange_rate_composition import live_exchange_rate_composition
from . import worker_cleanup as _worker_cleanup
from . import worker_service as _worker_service
from .operation_host import ProfileWorkerOperationHost
from .profile_login import ProfileWorkerHumanLogin


def _require_native_parent(channel: WorkerChannel, parent_pid: int) -> None:
    """Check the socket's live kernel peer before admitting profile custody."""
    if channel.peer.process_id != parent_pid:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    if isinstance(channel, PosixRuntimeChannel):
        with channel.capture_peer_pidfd():
            if channel.peer.process_id != parent_pid:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)


@contextmanager
def installed_profile_worker_composition() -> Generator[None]:
    """Bind the installed worker's persistence and live reference-rate dependencies."""
    with profile_adapter_composition(), live_exchange_rate_composition():
        yield


@dataclass(slots=True)
class _WorkerRunResources:
    """Resources acquired incrementally so every partial handshake remains releasable."""

    channel: WorkerChannel | None = None
    operation_channel: WorkerChannel | None = None
    custody: ProfileWorkerCustody | None = None
    channel_release: RuntimeTransportCleanup | None = None
    operation_channel_release: RuntimeTransportCleanup | None = None
    handshake_release: RuntimeTransportCleanup | None = None
    endpoint_releases: list[AsyncCloseable] = field(default_factory=list)


def _parse_worker_arguments(arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--worker-id", required=True, type=UUID)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args(arguments)


def _open_control_channel(options: argparse.Namespace, resources: _WorkerRunResources) -> ProfileWorkerIdentity:
    endpoint = worker_endpoint(storage_root=options.storage_root, worker_namespace=options.worker_id)
    resources.endpoint_releases.append(_worker_cleanup.WorkerRelease(lambda: asyncio.to_thread(endpoint.close)))
    channel = endpoint.connect()
    resources.channel = channel
    channel_release = RuntimeTransportCleanup(channel)
    resources.channel_release = channel_release
    _require_native_parent(channel, options.parent_pid)
    deadline = time.monotonic() + 10
    resources.handshake_release = channel_release
    connection = VerifiedRuntimeConnection(
        channel,
        expected=RuntimeClientHello(
            product_version=options.expected_version, storage_identity=endpoint.storage_identity
        ),
        deadline=deadline,
    )
    resources.handshake_release = None
    identity = read_document(channel, ProfileWorkerIdentity, deadline=deadline)
    if (
        identity.worker_id != options.worker_id
        or identity.runtime_boot_id != connection.hello.boot_id
        or identity.binding.os_owner_id != channel.peer.os_owner_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    custody = ProfileWorkerCustody(identity, storage_root=options.storage_root)
    resources.custody = custody
    write_document(channel, identity, deadline=deadline)
    return identity


def _open_operation_channel(
    options: argparse.Namespace, resources: _WorkerRunResources, identity: ProfileWorkerIdentity
) -> None:
    channel = cast(WorkerChannel, resources.channel)
    operation_endpoint = worker_endpoint(
        storage_root=options.storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
    )
    resources.endpoint_releases.append(
        _worker_cleanup.WorkerRelease(lambda: asyncio.to_thread(operation_endpoint.close))
    )
    operation_channel = operation_endpoint.connect()
    resources.operation_channel = operation_channel
    operation_channel_release = RuntimeTransportCleanup(operation_channel)
    resources.operation_channel_release = operation_channel_release
    if operation_channel.peer != channel.peer:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    _require_native_parent(operation_channel, options.parent_pid)
    deadline = time.monotonic() + 10
    resources.handshake_release = operation_channel_release
    verified = VerifiedRuntimeConnection(
        operation_channel,
        expected=RuntimeClientHello(
            product_version=options.expected_version, storage_identity=operation_endpoint.storage_identity
        ),
        deadline=deadline,
    )
    resources.handshake_release = None
    if (
        verified.hello.boot_id != identity.runtime_boot_id
        or read_document(operation_channel, ProfileWorkerIdentity, deadline=deadline) != identity
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    write_document(operation_channel, identity, deadline=deadline)


def _serve_connected_worker(
    options: argparse.Namespace,
    resources: _WorkerRunResources,
    identity: ProfileWorkerIdentity,
    composition_factory: Callable[[], AbstractContextManager[None]] | None,
) -> None:
    channel = cast(WorkerChannel, resources.channel)
    operation_channel = cast(WorkerChannel, resources.operation_channel)
    custody = cast(ProfileWorkerCustody, resources.custody)
    with ExitStack() as composition:
        composition.enter_context(
            override_settings(
                cadrumo_local_storage_root=options.storage_root,
                cadrumo_active_profile=str(identity.binding.profile_id),
            )
        )
        composition.enter_context((composition_factory or installed_profile_worker_composition)())
        operations = ProfileWorkerOperationHost(
            custody,
            authorization=WorkerAuthorizationClient(
                identity=identity, root=options.storage_root, parent_pid=options.parent_pid
            ),
        )
        human = ProfileWorkerHumanLogin(custody, decode=operations.profile_decode_context)
        asyncio.run(_worker_service._serve(channel, operation_channel, custody, human, operations))


def _run_worker(
    options: argparse.Namespace,
    resources: _WorkerRunResources,
    composition_factory: Callable[[], AbstractContextManager[None]] | None,
) -> None:
    if options.expected_version != version("cadrumo"):
        raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
    identity = _open_control_channel(options, resources)
    _open_operation_channel(options, resources, identity)
    _serve_connected_worker(options, resources, identity, composition_factory)


def _collect_worker_failures(primary_error: BaseException | None) -> tuple[BaseException, ...]:
    if primary_error is None:
        return ()
    _worker_cleanup.retain_task_failures(primary_error, ())
    failures: tuple[BaseException, ...] = (primary_error,)
    task_failures = primary_error.__dict__.get("worker_task_errors")
    if isinstance(task_failures, tuple):
        failures += tuple(
            failure for failure in cast(tuple[object, ...], task_failures) if isinstance(failure, BaseException)
        )
    return failures


def _release_attempted_handshakes(resources: _WorkerRunResources, failures: tuple[BaseException, ...]) -> None:
    # Framing already owns an attempted failure-close; do not make a second initial attempt.
    for failure in failures:
        displaced = failure.__dict__.get("_runtime_transport_cleanup")
        if not isinstance(displaced, RuntimeTransportCleanup):
            continue
        if resources.channel_release is resources.handshake_release or displaced.resource is resources.channel:
            resources.channel_release = None
        if (
            resources.operation_channel_release is resources.handshake_release
            or displaced.resource is resources.operation_channel
        ):
            resources.operation_channel_release = None


async def _close_worker_resources(resources: _WorkerRunResources, primary_error: BaseException | None) -> None:
    custody_release = None
    if resources.custody is not None:
        custody = resources.custody
        custody_release = _worker_cleanup.WorkerRelease(lambda: asyncio.to_thread(custody.close))
    try:
        await close_async_resources(
            custody_release,
            resources.channel_release,
            resources.operation_channel_release,
            *resources.endpoint_releases,
            task_name="profile-worker-exit-close",
            primary_error=primary_error,
        )
    finally:
        if primary_error is not None:
            _worker_cleanup.retain_task_failures(primary_error, ())


def _release_worker_resources(resources: _WorkerRunResources, primary_error: BaseException | None) -> None:
    failures = _collect_worker_failures(primary_error)
    _release_attempted_handshakes(resources, failures)
    asyncio.run(_close_worker_resources(resources, primary_error))


def run(
    arguments: list[str] | None = None,
    *,
    composition_factory: Callable[[], AbstractContextManager[None]] | None = None,
) -> int:
    """Admit only an exact native runtime parent and a contained current-cohort worker."""
    options = _parse_worker_arguments(arguments)
    if sys.platform not in {"win32", "linux"} or not sys.flags.isolated:
        return 2
    resources = _WorkerRunResources()
    refusal: RuntimeRefusalError | AutomationCustodyError | None = None
    try:
        _run_worker(options, resources, composition_factory)
    except (RuntimeRefusalError, AutomationCustodyError) as error:
        refusal = error
    finally:
        _release_worker_resources(resources, sys.exception() or refusal)
    if refusal is not None:
        if isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError):
            raise refusal
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
