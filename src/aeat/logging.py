"""Logging configuration entry point.

Provides a consistent logger factory to avoid scattered bare logging instances.
"""

import logging
import logging.config

_CONFIGURED = False


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
