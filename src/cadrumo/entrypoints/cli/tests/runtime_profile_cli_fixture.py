"""Canonical runtime-profile fixtures for CLI suites that need a populated bucket."""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable, Generator, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from threading import Event, Lock
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....adapters.local_runtime.installation import runtime_installation
from ....adapters.local_runtime.login_policy import compose_runtime_login_policy
from ....adapters.local_runtime.profile_worker import ProfileWorkerProcess
from ....adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner, owner_id
from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ....adapters.local_runtime.windows_channel import WindowsRuntimeChannel
from ....adapters.local_runtime.worker_authorization import WorkerAuthorizationServer
from ....adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ....application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalError,
)
from ....application.runtime.operation_access import RuntimeOperationRequest
from ....application.runtime.profile_worker import ProfileWorkerRequest
from ....application.runtime.transport import RuntimeConnectionContext
from ....application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAutomationInventoryRequest,
)
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....application.user_profile.automation_custody_port import AutomationCustodyError
from ....core.config import load_settings, override_settings
from ...runtime.profile_connections import RuntimeProfileConnections

__all__ = [
    "RuntimeFailureObservation",
    "_isolated_cli_state",
    "native_cli_profile_server",
    "observe_native_runtime_failures",
    "runtime_failure_observation",
]


@dataclass(frozen=True)
class RuntimeFailureObservation:
    """Sanitized type, source-location and worker exchange-stage evidence."""

    stage: str
    exception_type: str | None
    traceback_locations: tuple[str, ...]
    nested_leaves: tuple[tuple[str, tuple[str, ...]], ...] = ()
    request_type: str | None = None
    response_type: str | None = None
    definition_id: str | None = None
    operation_exchange: bool | None = None
    action: str | None = None
    phase: str | None = None
    reason: str | None = None


def _qualified_exception_type(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _traceback_locations(error: BaseException) -> tuple[str, ...]:
    return tuple(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_tb(error.__traceback__)
    )


def _exception_leaves(error: BaseException) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(error, BaseExceptionGroup):
        return ()
    leaves: list[tuple[str, tuple[str, ...]]] = []
    pending = list(reversed(error.exceptions))
    while pending:
        current = pending.pop()
        if isinstance(current, BaseExceptionGroup):
            pending.extend(reversed(current.exceptions))
        else:
            leaves.append((_qualified_exception_type(current), _traceback_locations(current)))
    return tuple(leaves)


def _failure_observation(
    stage: str,
    error: BaseException | None,
    *,
    request_type: str | None = None,
    response_type: str | None = None,
    definition_id: str | None = None,
    operation_exchange: bool | None = None,
    action: str | None = None,
    phase: str | None = None,
) -> RuntimeFailureObservation:
    reason = (
        error.reason.value
        if isinstance(error, (RuntimeRefusalError, ProfileAccessRefusedError, AutomationCustodyError))
        else None
    )
    if error is None:
        locations = tuple(
            f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in traceback.extract_stack(limit=12)
        )
        return RuntimeFailureObservation(
            stage=stage,
            exception_type=None,
            traceback_locations=locations,
            request_type=request_type,
            response_type=response_type,
            definition_id=definition_id,
            operation_exchange=operation_exchange,
            action=action,
            phase=phase,
            reason=None,
        )
    return RuntimeFailureObservation(
        stage=stage,
        exception_type=_qualified_exception_type(error),
        traceback_locations=_traceback_locations(error),
        nested_leaves=_exception_leaves(error),
        request_type=request_type,
        response_type=response_type,
        definition_id=definition_id,
        operation_exchange=operation_exchange,
        action=action,
        phase=phase,
        reason=reason,
    )


def runtime_failure_observation(stage: str, error: BaseException | None) -> RuntimeFailureObservation:
    """Return only allowlisted exception identity and traceback source locations."""
    return _failure_observation(stage, error)


@contextmanager
def observe_native_runtime_failures(
    server: RetainedRuntimeTransportServer,
    profiles: RuntimeProfileConnections,
    *,
    failure_observer: Callable[[RuntimeFailureObservation], None],
) -> Iterator[None]:
    """Observe safe profile-operation, worker-exchange and server-failure facts."""
    original_failed_set = server._failed.set
    original_exchange = ProfileWorkerProcess._exchange
    original_operation = profiles.operation
    original_held_body = WorkerAuthorizationServer._held_body
    original_close = ProfileWorkerProcess.close
    guard = Lock()

    def observe(observation: RuntimeFailureObservation) -> None:
        with guard:
            failure_observer(observation)

    def observe_worker_exchange[Result: BaseModel](
        self: ProfileWorkerProcess,
        request: ProfileWorkerRequest,
        response: type[Result],
        secret: bytearray | None = None,
        *,
        operation: bool = False,
        deadline: float | None = None,
    ) -> Result:
        try:
            return original_exchange(
                self,
                request,
                response,
                secret,
                operation=operation,
                deadline=deadline,
            )
        except BaseException as error:
            definition_id = getattr(request.root, "definition_id", None)
            action = getattr(request.root, "action", None)
            observe(
                _failure_observation(
                    "profile_worker_exchange",
                    error,
                    request_type=type(request.root).__qualname__,
                    response_type=response.__qualname__,
                    definition_id=definition_id if isinstance(definition_id, str) else None,
                    operation_exchange=operation,
                    action=action if isinstance(action, str) else None,
                )
            )
            raise

    def observe_failed_set() -> None:
        active_exception = sys.exception()
        observe(_failure_observation("runtime_server_failure", active_exception))
        original_failed_set()

    def observe_profile_operation(
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeOperationRequest,
    ) -> None:
        action = request.action
        definition_id = getattr(request, "definition_id", None)
        safe_definition_id = definition_id if isinstance(definition_id, str) else None
        observe(
            RuntimeFailureObservation(
                stage="profile_operation_entered",
                exception_type=None,
                traceback_locations=(),
                request_type=type(request).__qualname__,
                definition_id=safe_definition_id,
                operation_exchange=True,
                action=action,
            )
        )
        try:
            original_operation(context, channel, request)
        except BaseException as error:
            observe(
                _failure_observation(
                    "profile_operation_raised",
                    error,
                    request_type=type(request).__qualname__,
                    definition_id=safe_definition_id,
                    operation_exchange=True,
                    action=action,
                )
            )
            raise
        else:
            observe(
                RuntimeFailureObservation(
                    stage="profile_operation_returned",
                    exception_type=None,
                    traceback_locations=(),
                    request_type=type(request).__qualname__,
                    definition_id=safe_definition_id,
                    operation_exchange=True,
                    action=action,
                )
            )

    def observe_held_body(
        self: WorkerAuthorizationServer,
        channel: WindowsRuntimeChannel,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
        *,
        permit_id: UUID,
        deadline: float,
    ) -> None:
        try:
            original_held_body(self, channel, request, permit_id=permit_id, deadline=deadline)
        except BaseException as error:
            observe(
                _failure_observation(
                    "worker_authorization_held_body_raised",
                    error,
                    request_type=type(request).__qualname__,
                    action=request.request.action.value,
                    phase=request.kind,
                )
            )
            raise

    def observe_worker_close(self: ProfileWorkerProcess, *, deadline: float | None = None) -> None:
        observe(
            _failure_observation(
                "profile_worker_close_entered",
                sys.exception(),
                request_type=type(self).__qualname__,
            )
        )
        try:
            original_close(self, deadline=deadline)
        except BaseException as error:
            observe(
                _failure_observation(
                    "profile_worker_close_raised",
                    error,
                    request_type=type(self).__qualname__,
                )
            )
            raise

    try:
        exchange_patch = pytest.MonkeyPatch()
        exchange_patch.setattr(ProfileWorkerProcess, "_exchange", observe_worker_exchange)
        cast(Any, server._failed).set = observe_failed_set
        cast(Any, profiles).operation = observe_profile_operation
        cast(Any, WorkerAuthorizationServer)._held_body = observe_held_body
        cast(Any, ProfileWorkerProcess).close = observe_worker_close
        yield
    finally:
        cast(Any, ProfileWorkerProcess).close = original_close
        cast(Any, WorkerAuthorizationServer)._held_body = original_held_body
        cast(Any, profiles).operation = original_operation
        cast(Any, server._failed).set = original_failed_set
        exchange_patch.undo()


@contextmanager
def _runtime_profile_state(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path):
        yield


@contextmanager
def native_cli_profile_server(
    storage_root: Path,
    *,
    failure_observer: Callable[[RuntimeFailureObservation], None] | None = None,
) -> Iterator[None]:
    """Serve a real worker with explicit development session admission and a synthetic native store."""
    if sys.platform != "win32":
        pytest.skip("requires native Windows profile workers")
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    stop, boot, native = Event(), uuid4(), MemoryNativePort()
    owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=15)
    primary: BaseException | None = None
    try:
        runtime_installation(
            storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        with override_settings(cadrumo_dev_runtime_session_override="1"):
            login_policy = compose_runtime_login_policy(
                os_owner_id=owner_id(), runtime_boot_id=boot, stop=stop, native_inventory=None
            )
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=login_policy.capture,
            login_inventory=login_policy.inventory,
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        failure_observations: list[RuntimeFailureObservation] = []
        pool = ThreadPoolExecutor(max_workers=1)
        owner.executor = pool
        running = pool.submit(server.serve)
        owner.running = running
        owner.server = server
        assert server.ready.wait(3)
        if failure_observer is None:
            yield
        else:

            def observe(observation: RuntimeFailureObservation) -> None:
                failure_observations.append(observation)
                del failure_observations[:-32]
                failure_observer(observation)

            with observe_native_runtime_failures(server, profiles, failure_observer=observe):
                yield
    except BaseException as error:
        primary = error
        raise
    finally:
        owner.close_from_sync(task_name="native-cli-runtime-close", primary_error=primary)


@dataclass
class NativeCliProfileFixture:
    """One registered encrypted profile plus its test-owned native worker."""

    storage_root: Path
    scope: ExitStack
    label: str | None = None
    failure_observer: Callable[[RuntimeFailureObservation], None] | None = None

    @property
    def passphrase(self) -> str:
        return load_settings().cadrumo_dev_test_database_password.get_secret_value()

    def register(self, *, label: str, facts: Mapping[str, str]) -> None:
        from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile

        if self.label is not None:
            raise AssertionError("the native CLI fixture registers exactly one profile")
        register_cli_profile(label=label, facts=facts, log_in=False)
        self.scope.enter_context(native_cli_profile_server(self.storage_root, failure_observer=self.failure_observer))
        self.label = label


@contextmanager
def native_cli_profile_scope(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Isolate storage, active local test oracle and native server cleanup."""
    with ExitStack() as scope:
        root = scope.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        scope.callback(close_active_bucket_session)
        yield NativeCliProfileFixture(storage_root=root, scope=scope)


@pytest.fixture(autouse=True)
def _isolated_cli_state(tmp_path: Path) -> Iterator[None]:
    with _runtime_profile_state(tmp_path):
        yield
