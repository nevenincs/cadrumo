"""State-free bootstrap for the ``aeat`` console script."""

from __future__ import annotations


def main() -> None:
    """Defer file-backed logging until parsed CLI preflight authorizes it."""
    from ..core.logging import defer_logging_configuration, resume_logging_configuration

    defer_logging_configuration()
    try:
        from .cli import main as cli_main

        cli_main()
    finally:
        resume_logging_configuration()


__all__ = ["main"]
