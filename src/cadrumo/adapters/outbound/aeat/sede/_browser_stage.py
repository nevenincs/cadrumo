"""Shared Playwright stage error mapping for Sede browser drivers."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Protocol

# LOGGING-STDLIB-RATIONALE-TYPE-CHECKING-ONLY:
# stdlib logging imported solely for type-annotation context; never
# instantiated at runtime.
if TYPE_CHECKING:
    import logging

from .._playwright import PlaywrightError, PlaywrightTimeoutError
from .errors import SedeFailureMode, SedeNavigationError, SedeParseError


class PlaywrightStageRunner(Protocol):
    """Callable shape returned by :func:`build_playwright_stage_runner`."""

    async def __call__[T](
        self,
        operation: Awaitable[T],
        *,
        stage: str,
        description: str,
        timeout_ms: int,
        timeout_is_shape_change: bool = False,
    ) -> T: ...


def build_playwright_stage_runner(
    *,
    surface_label: str,
    log_prefix: str,
    logger: logging.Logger,
) -> PlaywrightStageRunner:
    """Build a :class:`PlaywrightStageRunner` bound to the shared Sede error mapping."""

    async def _runner[T](
        operation: Awaitable[T],
        *,
        stage: str,
        description: str,
        timeout_ms: int,
        timeout_is_shape_change: bool = False,
    ) -> T:
        return await run_playwright_stage(
            operation,
            stage=stage,
            description=description,
            timeout_ms=timeout_ms,
            surface_label=surface_label,
            log_prefix=log_prefix,
            logger=logger,
            timeout_is_shape_change=timeout_is_shape_change,
        )

    return _runner


async def run_playwright_stage[T](
    operation: Awaitable[T],
    *,
    stage: str,
    description: str,
    timeout_ms: int,
    surface_label: str,
    log_prefix: str,
    logger: logging.Logger,
    timeout_is_shape_change: bool = False,
) -> T:
    """Await a Playwright operation and emit uniform Sede failure modes."""
    try:
        return await operation
    except PlaywrightTimeoutError as exc:
        if timeout_is_shape_change:
            logger.error(
                "%s expected element missing failure_mode=%s stage=%s description=%s timeout_ms=%s",
                log_prefix,
                SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                stage,
                description,
                timeout_ms,
                exc_info=True,
            )
            raise SedeParseError(
                f"{surface_label} expected page element was not visible: {description}",
                failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                context={"stage": stage, "expected": description, "timeout_ms": timeout_ms},
            ) from exc
        logger.error(
            "%s playwright stage timed out failure_mode=%s stage=%s description=%s timeout_ms=%s",
            log_prefix,
            SedeFailureMode.LIVE_NAVIGATION_FAILED,
            stage,
            description,
            timeout_ms,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"{surface_label} browser stage timed out: {description}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": stage, "description": description, "timeout_ms": timeout_ms},
        ) from exc
    except PlaywrightError as exc:
        logger.error(
            "%s playwright stage failed failure_mode=%s stage=%s description=%s exc_type=%s",
            log_prefix,
            SedeFailureMode.LIVE_NAVIGATION_FAILED,
            stage,
            description,
            type(exc).__name__,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"{surface_label} browser stage failed: {description}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": stage, "description": description, "cause_type": type(exc).__name__},
        ) from exc


__all__ = ["build_playwright_stage_runner", "run_playwright_stage"]
