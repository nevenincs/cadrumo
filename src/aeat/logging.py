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

    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous_factory(*args, **kwargs)
        try:
            from aeat.observability._context import (
                RUN_CONTEXT_VAR,
                STEP_CONTEXT_VAR,
            )
        except ImportError:
            record.run_id = ""
            record.step_id = ""
            return record
        ctx = RUN_CONTEXT_VAR.get(None)
        record.run_id = ctx.run_id if ctx is not None else ""
        record.step_id = STEP_CONTEXT_VAR.get(None) or ""
        return record

    logging.setLogRecordFactory(_factory)
    _FACTORY_INSTALLED = True


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
            "handlers": {
                "default": {
                    "level": "INFO",
                    "formatter": "standard",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
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
