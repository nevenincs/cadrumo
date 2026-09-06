"""State-free bootstrap for the ``aeat`` console script."""

from __future__ import annotations


def main() -> None:
    """Defer file-backed logging until parsed CLI preflight authorizes it."""
    from ..core.logging import defer_logging_configuration, resume_logging_configuration

    defer_logging_configuration()
    try:
        from .cli import main as cli_main

        cli_main()
    except ModuleNotFoundError as exc:
        # Backstop for a missing optional package whose feature boundary did
        # not guard it: turn the deep-stack import failure into the same
        # actionable message `require_optional_extra` gives at a boundary.
        # A module outside the declared inventory is a broken installation,
        # not a configuration choice, so that failure is re-raised untouched.
        from ..core.optional_extras import optional_extra_for_module, require_optional_extra

        extra = optional_extra_for_module(exc.name or "")
        if extra is None:
            raise
        require_optional_extra(extra)
        raise
    finally:
        resume_logging_configuration()


__all__ = ["main"]
