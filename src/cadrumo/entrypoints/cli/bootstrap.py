"""State-free bootstrap for the ``aeat`` console script."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.currency.service import ExchangeRateProvider


def _ecb_rate_provider() -> ExchangeRateProvider:
    # Resolved on first conversion so a command that never converts does not
    # import the ECB adapter and the settings stack it reads.
    from ...adapters.outbound.fx.ecb_provider import default_ecb_rate_provider

    return default_ecb_rate_provider()


def main() -> None:
    """Defer file-backed logging until parsed CLI preflight authorizes it."""
    # Pydantic scans every installed distribution's entry points on its first
    # model build, which costs about a tenth of a second in a process that
    # builds models before it has parsed a command. Cadrumo declares no
    # pydantic plugin, and a third-party one would observe taxpayer models it
    # has no business seeing. ``setdefault`` leaves an operator's explicit
    # value alone.
    os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "__all__")

    from ...application.exchange_rate_provider import bind_exchange_rate_provider_factory
    from ...core.logging import defer_logging_configuration, resume_logging_configuration

    defer_logging_configuration()
    try:
        from .main import main as cli_main

        # The console script is the host that decides conversions use the live
        # ECB reference rates.
        with bind_exchange_rate_provider_factory(_ecb_rate_provider):
            cli_main()
    except ModuleNotFoundError as exc:
        # Backstop for a missing optional package whose feature boundary did
        # not guard it: turn the deep-stack import failure into the same
        # actionable message `require_optional_extra` gives at a boundary.
        # A module outside the declared inventory is a broken installation,
        # not a configuration choice, so that failure is re-raised untouched.
        from ...core.optional_extras import optional_extra_for_module, require_optional_extra

        extra = optional_extra_for_module(exc.name or "")
        if extra is None:
            raise
        require_optional_extra(extra)
        raise
    finally:
        resume_logging_configuration()


__all__ = ["main"]
