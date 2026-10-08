"""Connection-scoped MCP lease cleanup and retained failure diagnostics."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.core.async_cleanup import AsyncResourceCleanupError


@dataclass(frozen=True, slots=True)
class RuntimeClientCleanup:
    """Retain a blocking connection owner until close succeeds or is retried."""

    client: RuntimeFrontendClient
    on_closed: Callable[[], None] | None = None

    async def close(self) -> None:
        """Close the owned runtime client and retire it after success."""
        await asyncio.to_thread(self.client.close)
        if self.on_closed is not None:
            self.on_closed()


@dataclass(frozen=True, slots=True)
class RuntimeAdmissionCleanup:
    """Own cleanup left by an admission that never returned its connection."""

    failure: AsyncResourceCleanupError
    on_closed: Callable[[], None]

    async def close(self) -> None:
        """Retry a retained native admission cleanup and retire it after success."""
        await self.failure.retry_cleanup()
        self.on_closed()


def retain_cleanup_failure(
    target: BaseException,
    sources: Sequence[BaseException],
    diagnostics: dict[int, BaseException],
    *,
    capture_only: bool = False,
) -> None:
    """Attach retryable cleanup owners and retain earlier raw diagnostics."""
    retained = _collect_cleanup_failures(target, sources, diagnostics)
    if retained is None or capture_only:
        return
    _attach_cleanup_diagnostics(target, retained, diagnostics)


def _collect_cleanup_failures(
    target: BaseException,
    sources: Sequence[BaseException],
    diagnostics: dict[int, BaseException],
) -> AsyncResourceCleanupError | None:
    retained: AsyncResourceCleanupError | None = None
    seen_cleanup: set[int] = set()
    merged_cleanup: set[int] = set()
    seen_errors: set[int] = set()
    pending = [target, *sources]
    while pending:
        error = pending.pop(0)
        if id(error) in seen_errors:
            continue
        seen_errors.add(id(error))
        _collect_error_cleanup(error, pending, diagnostics, seen_cleanup)
        retained = _merge_error_cleanup(error, retained, seen_cleanup, merged_cleanup)
    return retained


def _collect_error_cleanup(
    error: BaseException,
    pending: list[BaseException],
    diagnostics: dict[int, BaseException],
    seen_cleanup: set[int],
) -> None:
    body_error = error.__dict__.get("body_error")
    if isinstance(body_error, BaseException):
        pending.append(body_error)
    candidates: list[object] = [error] if isinstance(error, AsyncResourceCleanupError) else []
    candidates.extend(error.__dict__.get(name) for name in ("async_cleanup_error", "cleanup_error"))
    for candidate in candidates:
        if isinstance(candidate, AsyncResourceCleanupError):
            seen_cleanup.add(id(candidate))
        elif isinstance(candidate, BaseException):
            diagnostics[id(candidate)] = candidate


def _merge_error_cleanup(
    error: BaseException,
    retained: AsyncResourceCleanupError | None,
    seen_cleanup: set[int],
    merged_cleanup: set[int],
) -> AsyncResourceCleanupError | None:
    candidates: list[object] = [error] if isinstance(error, AsyncResourceCleanupError) else []
    candidates.extend(error.__dict__.get(name) for name in ("async_cleanup_error", "cleanup_error"))
    for candidate in candidates:
        if (
            not isinstance(candidate, AsyncResourceCleanupError)
            or id(candidate) not in seen_cleanup
            or id(candidate) in merged_cleanup
        ):
            continue
        merged_cleanup.add(id(candidate))
        retained = candidate if retained is None else retained.merged_with(candidate)
    return retained


def _attach_cleanup_diagnostics(
    target: BaseException,
    retained: AsyncResourceCleanupError,
    diagnostics: dict[int, BaseException],
) -> None:
    if diagnostics:
        diagnostic = AsyncResourceCleanupError(
            (),
            tuple(diagnostics.values()),
            retry_task_name="mcp-runtime-close-diagnostics",
            close_attempts=1,
        )
        retained = retained.merged_with(diagnostic)
        retained.__cause__ = (
            next(iter(diagnostics.values()))
            if len(diagnostics) == 1
            else BaseExceptionGroup("Earlier MCP cleanup diagnostics", list(diagnostics.values()))
        )
    target.__dict__["async_cleanup_error"] = retained
    target.__dict__["cleanup_error"] = retained


def cleanup_sources(
    failures: Sequence[BaseException], primary_error: BaseException | None
) -> tuple[BaseException, ...]:
    """Preserve failures followed by an active body error for cleanup retention."""
    return (*failures, *((primary_error,) if primary_error is not None else ()))


def preserve_cancellation_body_error(
    cancellation: asyncio.CancelledError,
    sources: Sequence[BaseException],
    primary_error: BaseException | None,
) -> None:
    """Attach the original body failure to cancellation when cleanup reports none."""
    if "body_error" in cancellation.__dict__:
        return
    for error in sources:
        body_error = error.__dict__.get("body_error")
        if isinstance(body_error, BaseException):
            cancellation.__dict__["body_error"] = body_error
            return
    if primary_error is not None and not isinstance(primary_error, asyncio.CancelledError):
        cancellation.__dict__["body_error"] = primary_error
