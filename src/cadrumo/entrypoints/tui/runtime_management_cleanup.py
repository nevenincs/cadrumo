"""Retain installed runtime stop outcomes and failed native owners."""

from __future__ import annotations

import asyncio

from ...adapters.local_runtime.framing import RuntimeTransportCleanup
from ...core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    async_cleanup_failures,
    close_async_resources,
    direct_cleanup_owners,
)
from ..runtime_management import RuntimeStopConsent


class RuntimeManagementCleanup:
    """Retain stop outcome and actual failed native owners across management screens."""

    def __init__(self) -> None:
        """Start one explicit management cleanup scope without native I/O."""
        self._consent: RuntimeStopConsent | None = None
        self._failure: BaseException | None = None
        self._resources: dict[int, AsyncCloseable] = {}
        self._retired: dict[int, AsyncCloseable] = {}

    @property
    def consent(self) -> RuntimeStopConsent | None:
        """Return the last exact consent, including its single-use dispatch fence."""
        return self._consent

    @property
    def failure(self) -> BaseException | None:
        """Return the original body failure or the current pending cleanup failure."""
        return self._failure

    @property
    def pending(self) -> bool:
        """Report actual release owners still retained by the enclosing scope."""
        return any(
            not isinstance(resource, RuntimeTransportCleanup) or not resource.released
            for resource in self._resources.values()
        )

    def retain_consent(self, consent: RuntimeStopConsent) -> None:
        """Keep the native outcome before its screen or worker can disappear."""
        self._consent = consent

    def retain(self, error: BaseException) -> None:
        """Adopt canonical owners directly, without adding an aggregate retry owner.

        Owners carried by a wrapped body failure are adopted too, so a cleanup
        that failed beneath the screen's own error is still released later.
        """
        owners = async_cleanup_failures(error)
        self._retain_resources(owners)
        retained = self._merged_owner(owners)
        if retained is None:
            return
        if retained is not error:
            error.__dict__["async_cleanup_error"] = retained
            if isinstance(error.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
                error.__dict__["cleanup_error"] = retained
        self._retain_failure(error, retained)

    def _retain_resources(self, owners: tuple[AsyncResourceCleanupError, ...]) -> None:
        for owner in owners:
            for resource in owner.resources:
                if self._is_retained_resource(resource):
                    self._resources[id(resource)] = resource

    @staticmethod
    def _merged_owner(owners: tuple[AsyncResourceCleanupError, ...]) -> AsyncResourceCleanupError | None:
        merged: AsyncResourceCleanupError | None = None
        for owner in owners:
            merged = owner if merged is None else merged.merged_with(owner)
        return merged

    def _is_retained_resource(self, resource: AsyncCloseable) -> bool:
        if self._retired.get(id(resource)) is resource:
            return False
        return not isinstance(resource, RuntimeTransportCleanup) or not resource.released

    def _retain_failure(self, error: BaseException, retained: AsyncResourceCleanupError) -> None:
        if self._failure is None or isinstance(error, asyncio.CancelledError):
            self._replace_failure(error)
            return
        if self._failure is not error:
            self._merge_failure(self._failure, retained)

    def _replace_failure(self, error: BaseException) -> None:
        if self._failure is not None and self._failure is not error:
            error.__dict__["body_error"] = self._failure
        self._failure = error

    @staticmethod
    def _merge_failure(failure: BaseException, retained: AsyncResourceCleanupError) -> None:
        prior = failure.__dict__.get("async_cleanup_error")
        failure.__dict__["async_cleanup_error"] = (
            prior.merged_with(retained) if isinstance(prior, AsyncResourceCleanupError) else retained
        )

    @staticmethod
    def _replace_cleanup(error: BaseException, current: AsyncResourceCleanupError | None) -> None:
        """Keep active retry authority limited to this attempt's failed owners."""
        for name in ("async_cleanup_error", "cleanup_error"):
            previous = error.__dict__.get(name)
            if current is None:
                if isinstance(previous, AsyncResourceCleanupError):
                    error.__dict__.pop(name)
            elif (
                name == "async_cleanup_error"
                or isinstance(error, asyncio.CancelledError)
                or isinstance(previous, AsyncResourceCleanupError)
            ):
                error.__dict__[name] = current

    @staticmethod
    def _cleanup_errors(*errors: BaseException | None) -> tuple[AsyncResourceCleanupError, ...]:
        """Collect the active canonical owners before an attempt changes attachments."""
        return tuple(owner for error in errors if error is not None for owner in direct_cleanup_owners(error))

    @staticmethod
    def _current_cleanup(error: BaseException) -> AsyncResourceCleanupError | None:
        current = error if isinstance(error, AsyncResourceCleanupError) else error.__dict__.get("cleanup_error")
        return current if isinstance(current, AsyncResourceCleanupError) else None

    @classmethod
    def _failed_resources(cls, error: BaseException, resources: tuple[AsyncCloseable, ...]) -> set[int]:
        current = cls._current_cleanup(error)
        if current is not None:
            return {id(resource) for resource in current.resources}
        if isinstance(error, asyncio.CancelledError):
            return set()
        return {id(resource) for resource in resources}

    def _handle_release_failure(self, error: BaseException, primary_error: BaseException | None) -> bool:
        current = self._current_cleanup(error)
        if primary_error is not None:
            if current is not None or isinstance(error, asyncio.CancelledError):
                self._replace_cleanup(primary_error, current)
                self.retain(primary_error)
            if isinstance(primary_error, asyncio.CancelledError):
                raise primary_error from error
            if isinstance(error, asyncio.CancelledError):
                error.__dict__["body_error"] = primary_error
                self.retain(error)
                raise
            if isinstance(error, AsyncResourceCleanupError):
                return True
        if primary_error is None and isinstance(error, AsyncResourceCleanupError):
            self._retain_standalone_cleanup(error)
        else:
            self.retain(error)
        return False

    def _retain_standalone_cleanup(self, error: AsyncResourceCleanupError) -> None:
        previous_failure = self._failure
        if previous_failure is not None and not isinstance(previous_failure, AsyncResourceCleanupError):
            self._replace_cleanup(previous_failure, error)
            self.retain(previous_failure)
            raise previous_failure from error
        self._failure = error
        self.retain(error)
        if previous_failure is not None and previous_failure is not error:
            raise error from previous_failure

    def _finish_release_success(self, primary_error: BaseException | None) -> None:
        if primary_error is not None:
            self._replace_cleanup(primary_error, None)
        if isinstance(self._failure, AsyncResourceCleanupError):
            self._failure = None
        elif self._failure is not None:
            self._replace_cleanup(self._failure, None)
        if isinstance(primary_error, asyncio.CancelledError):
            raise primary_error

    def _retire_released_resources(
        self,
        resources: tuple[AsyncCloseable, ...],
        failed: set[int],
        prior_cleanup: tuple[AsyncResourceCleanupError, ...],
        primary_error: BaseException | None,
    ) -> None:
        released = tuple(resource for resource in resources if id(resource) not in failed)
        for retained in prior_cleanup + self._cleanup_errors(primary_error, self._failure):
            retained.discard_released_resources(*released)
        for resource in resources:
            if id(resource) not in failed:
                self._resources.pop(id(resource), None)
                self._retired[id(resource)] = resource
        for identity, resource in tuple(self._resources.items()):
            if isinstance(resource, RuntimeTransportCleanup) and resource.released:
                self._resources.pop(identity)
                self._retired[identity] = resource

    async def release(self, *, primary_error: BaseException | None = None) -> None:
        """Release the actual retained resources under the enclosing scope's primary."""
        if primary_error is not None:
            self.retain(primary_error)
        prior_cleanup = self._cleanup_errors(primary_error, self._failure)
        resources = tuple(self._resources.values())
        failed: set[int] = set()
        try:
            # Keep this attempt's result separate from historical attachments.
            # The canonical helper still owns repeated caller cancellation and
            # attempts every actual resource; no aggregate owner is introduced.
            await close_async_resources(*resources, task_name="tui-runtime-management-release", primary_error=None)
        except BaseException as error:
            failed = self._failed_resources(error, resources)
            if self._handle_release_failure(error, primary_error):
                return
            raise
        else:
            self._finish_release_success(primary_error)
        finally:
            self._retire_released_resources(resources, failed, prior_cleanup, primary_error)
