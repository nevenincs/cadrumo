"""Synthetic encrypted profiles shared by native worker acceptance tests."""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import time
from collections.abc import Iterator
from concurrent.futures import CancelledError as FutureCancelledError
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from datetime import timedelta
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.server import RuntimeListener
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    await_cancellation_complete,
    close_async_resources,
)
from cadrumo.core.time.clock import now

from .retained_server import RetainedRuntimeTransportServer

PROFILE_INPUT = "synthetic-worker-password"


class NativeRuntimeFixtureOwner:
    """Retain an in-process native host until canonical drain releases its listener."""

    def __init__(self, endpoint: RuntimeListener, stop: Event, *, timeout: float, drained: Event | None = None) -> None:
        self.endpoint, self.stop = endpoint, stop
        self.timeout, self.drained = timeout, drained
        self.server: RetainedRuntimeTransportServer | None = None
        self.running: Future[None] | None = None
        self.auxiliary: list[Future[None]] = []
        self.executor: ThreadPoolExecutor | None = None
        self.after_drain: AsyncCloseable | None = None
        self.released = False
        self._runtime_released = False
        self._endpoint_owner = RuntimeTransportCleanup(endpoint)
        self._primary: BaseException | None = None
        self._primary_reported = False
        self._auxiliary_cleanup: AsyncResourceCleanupError | None = None

    def _retain_terminal_failure(self, error: BaseException) -> None:
        """Preserve the first terminal body and retain later terminal diagnostics."""
        if self._primary is None:
            self._primary = error
        elif error is not self._primary:
            previous = self._primary.__dict__.get("terminal_errors", ())
            self._primary.__dict__["terminal_errors"] = (*previous, error) if isinstance(previous, tuple) else (error,)

    def _retain_auxiliary_failure(self, error: BaseException) -> None:
        """Transfer completed approval cleanup to this fixture's sole retry path."""
        self._retain_terminal_failure(error)
        for name in ("async_cleanup_error", "cleanup_error"):
            cleanup = error.__dict__.get(name)
            if isinstance(cleanup, AsyncResourceCleanupError):
                if self._auxiliary_cleanup is None:
                    self._auxiliary_cleanup = cleanup
                elif self._auxiliary_cleanup is not cleanup:
                    self._auxiliary_cleanup = self._auxiliary_cleanup.merged_with(cleanup)
                # The fixture now owns this exact cleanup. Keeping the direct
                # attachment as well would retry native release twice through
                # both the resource and its enclosing fixture owner.
                del error.__dict__[name]

    async def _settle_auxiliary(self, *, deadline: float) -> None:
        """Settle original approval futures and retain their native cleanup."""
        for future in tuple(self.auxiliary):

            def settle(owned: Future[None]) -> BaseException | None:
                try:
                    owned.result(timeout=max(0.0, deadline - time.monotonic()))
                except BaseException as error:
                    if not owned.done():
                        raise
                    if owned.cancelled():
                        return error if isinstance(error, FutureCancelledError) else FutureCancelledError()
                    return owned.exception()
                return None

            try:
                terminal = await await_cancellation_complete(
                    asyncio.to_thread(settle, future),
                    task_name="native-fixture-approval-settlement",
                )
            except BaseException as error:
                if not future.done():
                    raise
                self.auxiliary.remove(future)
                terminal = error if future.cancelled() else future.exception()
                if terminal is not None:
                    self._retain_auxiliary_failure(terminal)
                if isinstance(error, asyncio.CancelledError) and error is not terminal:
                    raise
            else:
                self.auxiliary.remove(future)
                if terminal is not None:
                    self._retain_auxiliary_failure(terminal)
        cleanup = self._auxiliary_cleanup
        if cleanup is not None:
            if time.monotonic() >= deadline:
                raise TimeoutError("native approval cleanup budget exhausted")
            settled = False

            async def release() -> None:
                nonlocal settled
                await cleanup.retry_cleanup()
                settled = True

            try:
                await await_cancellation_complete(release(), task_name="native-fixture-approval-cleanup")
            except BaseException as error:
                retained = error.__dict__.get("cleanup_error")
                if isinstance(error, AsyncResourceCleanupError):
                    self._auxiliary_cleanup = error
                elif isinstance(retained, AsyncResourceCleanupError):
                    self._auxiliary_cleanup = retained
                elif settled:
                    self._auxiliary_cleanup = None
                raise
            else:
                self._auxiliary_cleanup = None

    def close_from_sync(self, *, task_name: str, primary_error: BaseException | None) -> None:
        """Run canonical cleanup from either a synchronous caller or an active SDK loop."""

        def release() -> None:
            asyncio.run(close_async_resources(self, task_name=task_name, primary_error=primary_error))

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            release()
            return
        context = copy_context()
        result: Future[None] = Future()

        def threaded_release() -> None:
            try:
                context.run(release)
            except BaseException as error:
                result.set_exception(error)
            else:
                result.set_result(None)

        thread = Thread(target=threaded_release, name="native-fixture-cleanup")
        thread.start()
        try:
            result.result()
        finally:
            thread.join()

    async def close(self) -> None:
        """Use one absolute budget to settle the original serve task and retry its drain."""
        if self.released:
            return
        deadline = time.monotonic() + self.timeout
        self.stop.set()
        try:
            await self._settle_auxiliary(deadline=deadline)
            if not self._runtime_released:
                if self.running is not None:
                    try:
                        await await_cancellation_complete(
                            asyncio.to_thread(self.running.result, timeout=max(0.0, deadline - time.monotonic())),
                            task_name="native-fixture-serve-settlement",
                        )
                    except asyncio.CancelledError as error:
                        if not self.running.done() or self.running.exception() is not error:
                            raise
                        self._retain_terminal_failure(error)
                    except TimeoutError as error:
                        if not self.running.done():
                            raise
                        self._retain_terminal_failure(error)
                    except (RuntimeShutdownIncompleteError, AsyncResourceCleanupError):
                        # These terminal cleanup refusals can now be resolved by the
                        # retained server, rather than replaying the failed Future.
                        pass
                    except BaseException as error:
                        if not self.running.done():
                            raise
                        self._retain_terminal_failure(error)
                    self.running = None
                if self.server is not None:
                    try:
                        await await_cancellation_complete(
                            asyncio.to_thread(self.server.retry_drain, deadline=deadline),
                            task_name="native-fixture-drain",
                        )
                    except RuntimeRefusalError as error:
                        if error.reason is not RuntimeRefusalCode.UNAVAILABLE:
                            raise
                        # The public retry contract reports missing receipts/host
                        # failure only after actual containment and listener release.
                        if self._primary is None:
                            self._primary = error
                else:
                    await await_cancellation_complete(
                        self._endpoint_owner.close(), task_name="native-fixture-endpoint-close"
                    )
                self._runtime_released = True
                if self.drained is not None:
                    self.drained.set()
                self.server = None
            if self.after_drain is not None:
                await close_async_resources(
                    self.after_drain, task_name="native-fixture-custody-retirement", primary_error=None
                )
            self.released = True
            if self.executor is not None:
                self.executor.shutdown(wait=False, cancel_futures=False)
                self.executor = None
            if self._primary is not None and not self._primary_reported:
                self._primary_reported = True
                raise self._primary
        except asyncio.CancelledError as error:
            if not self.released:
                failure = error.__dict__.get("cleanup_error")
                cleanup = AsyncResourceCleanupError(
                    (self,),
                    (failure if isinstance(failure, BaseException) else error,),
                    retry_task_name="native-fixture-cancelled-cleanup",
                    close_attempts=1,
                )
                error.__dict__["async_cleanup_error"] = cleanup
                error.__dict__["cleanup_error"] = cleanup
            raise
        except BaseException as failure:
            if self._primary is not None and failure is not self._primary:
                cleanup = AsyncResourceCleanupError(
                    (self,), (failure,), retry_task_name="native-fixture-primary-cleanup", close_attempts=1
                )
                previous = self._primary.__dict__.get("async_cleanup_error")
                if isinstance(previous, AsyncResourceCleanupError):
                    cleanup = previous.merged_with(cleanup)
                self._primary.__dict__["async_cleanup_error"] = cleanup
                self._primary.add_note("Native fixture cleanup also failed; retry through attached async_cleanup_error")
                self._primary_reported = True
                raise self._primary from failure
            raise
        finally:
            if self.executor is not None:
                self.executor.shutdown(wait=False, cancel_futures=False)


def changed[T: BaseModel](model: T, **values: object) -> T:
    return model.__class__.model_validate(
        {**{name: getattr(model, name) for name in model.__class__.model_fields}, **values}
    )


def owner_id() -> str:
    if sys.platform != "win32":
        return str(os.getuid())
    import win32api
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 8)
    try:
        sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
        return win32security.ConvertSidToStringSid(sid)
    finally:
        win32api.CloseHandle(token)


@contextmanager
def worker_profiles(tmp_path: Path) -> Iterator[tuple[Path, tuple[tuple[ProfileWorkerIdentity, bytes], ...]]]:
    create, decode = profile_authority_contexts()
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        targets: list[tuple[ProfileWorkerIdentity, bytes]] = []
        boot, installation = uuid4(), uuid4()
        try:
            for index in range(2):
                result = register_profile_with_credentials(
                    label=f"Worker profile {index}",
                    passphrase=PROFILE_INPUT,
                    profile_create_context=create,
                    profile_decode_context=decode,
                )
                material = load_committed_profile_password_material(UUID(result.profile_id), root=root)
                session = current_active_bucket_session()
                assert session is not None
                targets.append(
                    (
                        ProfileWorkerIdentity(
                            worker_id=uuid4(),
                            runtime_boot_id=boot,
                            binding=ProfileAccessBinding(
                                profile_id=UUID(result.profile_id),
                                installation_id=installation,
                                os_owner_id=owner_id(),
                                custody_generation=material.envelope.password_generation,
                                dek_epoch=UUID(bytes=base64.b64decode(material.envelope.dek_epoch)),
                            ),
                        ),
                        session.dek,
                    )
                )
                close_active_bucket_session()
            yield root, tuple(targets)
        finally:
            close_active_bucket_session()


def lease(identity: ProfileWorkerIdentity, *, seconds: float = 120) -> AccessSession:
    instant = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        runtime_boot_id=identity.runtime_boot_id,
        profile_lock_generation=0,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        grant_id=uuid4(),
        grant_generation=1,
        key_id=uuid4(),
        key_generation=1,
        issued_at=instant,
        issued_monotonic=time.monotonic(),
        expires_at=instant + timedelta(seconds=seconds),
    )
