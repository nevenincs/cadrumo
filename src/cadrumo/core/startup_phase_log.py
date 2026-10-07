"""Fixed-vocabulary runtime startup phase timing diagnostics."""

from __future__ import annotations

import time
from asyncio import CancelledError
from collections.abc import Generator
from contextlib import contextmanager
from logging import INFO, WARNING
from typing import TYPE_CHECKING, Literal

from .diagnostic_log import DiagnosticValue, diagnostic_error_fields, diagnostic_event, diagnostic_scope

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
    outcome = "entered" if transition == "enter" else "completed"
    fields: dict[str, DiagnosticValue] = {
        "startup_phase": phase,
        "transition": transition,
        "elapsed_seconds": elapsed,
        "outcome": outcome,
    }
    if primary_error is not None:
        outcome = "cancelled" if isinstance(primary_error, CancelledError | KeyboardInterrupt) else "failed"
        fields["outcome"] = outcome
        fields.update(diagnostic_error_fields(primary_error))
    diagnostic_event(
        logger,
        f"runtime_startup phase={phase} transition={transition} elapsed_seconds={elapsed:.6f}",
        fields=fields,
        level=WARNING if outcome == "failed" else INFO,
        primary_error=primary_error,
    )


@contextmanager
def startup_phase(logger: Logger, phase: str) -> Generator[None]:
    """Emit only fixed phase names and elapsed native monotonic seconds."""
    with diagnostic_scope():
        started = time.monotonic()
        primary: BaseException | None = None
        log_startup_phase(logger, phase, "enter", 0.0)
        try:
            yield
        except BaseException as error:
            primary = error
            raise
        finally:
            elapsed = time.monotonic() - started
            log_startup_phase(logger, phase, "leave", elapsed, primary_error=primary)
