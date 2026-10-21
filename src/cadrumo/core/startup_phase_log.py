"""Fixed-vocabulary runtime startup phase timing diagnostics."""

from __future__ import annotations

import time
from asyncio import CancelledError
from collections.abc import Generator
from contextlib import contextmanager
from logging import DEBUG, ERROR
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
    expected_refusals: tuple[type[Exception], ...] = (),
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
        if isinstance(primary_error, expected_refusals):
            outcome = "refused"
        fields["outcome"] = outcome
        fields.update(diagnostic_error_fields(primary_error))
    diagnostic_event(
        logger,
        f"runtime_startup phase={phase} transition={transition} elapsed_seconds={elapsed:.6f}",
        fields=fields,
        level=ERROR if outcome == "failed" else DEBUG,
        primary_error=primary_error,
    )


@contextmanager
def startup_phase(
    logger: Logger, phase: str, *, expected_refusals: tuple[type[Exception], ...] = ()
) -> Generator[None]:
    """Time a phase; declared policy refusals stay distinct from startup faults.

    Every exception still escapes unchanged. Callers must name their expected
    refusal types explicitly; transport and unexpected errors remain failures.
    """
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
            log_startup_phase(
                logger, phase, "leave", elapsed, primary_error=primary, expected_refusals=expected_refusals
            )
