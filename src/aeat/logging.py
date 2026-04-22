"""Logging configuration entry point.

Provides a consistent logger factory to avoid scattered bare logging instances.
The root logger carries the run-trace context filter from
:mod:`aeat.observability._sink` so every record automatically picks up
the active ``run_id`` / ``step_id`` while a run context is bound.
"""

import logging
import logging.config
from typing import Any

_CONFIGURED = False
_FACTORY_INSTALLED = False


def _install_run_context_record_factory() -> None:
    """Install a :class:`LogRecord` factory that stamps ``run_id`` / ``step_id``.

    The contextvars live in :mod:`aeat.observability._context`. They are
    imported lazily inside the closure so this function never triggers
    a partial import of :mod:`aeat.observability` (which would create a
    cycle through :mod:`aeat.config` → :mod:`aeat.auth` → this module).
    """
    global _FACTORY_INSTALLED
    if _FACTORY_INSTALLED:
        return
    previous_factory = logging.getLogRecordFactory()
    # Cache the contextvars across record creations. The `import` statement
    # is cheap after the first call (``sys.modules`` lookup), but hoisting
    # it into the closure eliminates the repeated try/except on every
    # single log record — the factory runs in the hottest path of the
    # logging subsystem.
    cached_vars: tuple[Any, Any] | None = None

    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        nonlocal cached_vars
        record = previous_factory(*args, **kwargs)
        if cached_vars is None:
            try:
                from .observability._context import (
                    RUN_CONTEXT_VAR,
                    STEP_CONTEXT_VAR,
                )
            except ImportError:
                # Partial import during module bootstrap — degrade
                # gracefully and retry next time.
                record.run_id = ""
                record.step_id = ""
                return record
            cached_vars = (RUN_CONTEXT_VAR, STEP_CONTEXT_VAR)
        run_var, step_var = cached_vars
        ctx = run_var.get(None)
        record.run_id = ctx.run_id if ctx is not None else ""
        record.step_id = step_var.get(None) or ""
        return record

    logging.setLogRecordFactory(_factory)
    _FACTORY_INSTALLED = True


class _DropRunEventFilter(logging.Filter):
    """Suppress observability ``run_event`` records on the stderr handler.

    Records carrying a ``run_event`` extra are the per-run JSONL sink's
    diet — they're already persisted to ``events.jsonl`` via
    :class:`aeat.observability.JsonlRunSink`. Echoing them on stderr as
    well would spam the console with one ``run.event NAVIGATION`` line
    per step; suppressing them here removes the noise while leaving
    the record intact for any other handler (including the JSONL
    sink). See audit finding S2 (vaultspec-code-reviewer, 2026-04-21).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "run_event", None) is None


def configure_logging() -> None:
    """Configures the project-wide logging defaults."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
            },
            "filters": {
                "drop_run_event": {"()": f"{__name__}._DropRunEventFilter"},
            },
            "handlers": {
                "default": {
                    "level": "INFO",
                    "formatter": "standard",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "filters": ["drop_run_event"],
                },
            },
            "root": {
                "handlers": ["default"],
                "level": "INFO",
            },
        }
    )

    # Local import: the observability layer imports ``aeat.logging`` for
    # its own get_logger() seed, so attaching the filter at module
    # import time would create a circular import. Inside this function
    # the import is safe because configure_logging() runs after both
    # modules finish loading.
    _install_run_context_record_factory()

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger for the given module name.

    Args:
        name: The name of the module, typically __name__.

    Returns:
        A configured logging.Logger instance.
    """
    configure_logging()
    return logging.getLogger(name)
