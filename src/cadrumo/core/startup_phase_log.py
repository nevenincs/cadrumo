"""Fixed-vocabulary runtime startup phase timing diagnostics."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal

from .logging import LogExtra

if TYPE_CHECKING:
    from logging import Logger


def log_startup_phase(
    logger: Logger,
    phase: str,
    transition: Literal["enter", "leave"],
    elapsed: float,
    *,
    primary_error: BaseException | None = None,
) -> None:
    """Keep diagnostic failures from replacing an existing product primary."""
    try:
        logger.info(
            "runtime_startup phase=%s transition=%s elapsed_seconds=%.6f",
            phase,
            transition,
            elapsed,
            extra=LogExtra(
                {"startup_phase": phase, "transition": transition, "elapsed_seconds": elapsed}
            ).for_logging(),
        )
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise


@contextmanager
def startup_phase(logger: Logger, phase: str) -> Generator[None]:
    """Emit only fixed phase names and elapsed native monotonic seconds."""
    started = time.monotonic()
    primary: list[BaseException] = []
    log_startup_phase(logger, phase, "enter", 0.0)
    try:
        yield
    except BaseException as error:
        primary.append(error)
        raise
    finally:
        elapsed = time.monotonic() - started
        log_startup_phase(logger, phase, "leave", elapsed, primary_error=primary[0] if primary else None)
