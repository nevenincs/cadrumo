"""Host composition of the live exchange-rate source.

A host process decides where currency conversions read their rates. Every
installed frontend uses the ECB reference rates, and binds them through this one
seam so no projection imports the outbound adapter itself.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.currency.service import ExchangeRateProvider


def _ecb_rate_provider() -> ExchangeRateProvider:
    # Resolved on first conversion so a session that never converts does not
    # import the ECB adapter and the settings stack it reads.
    from ..adapters.outbound.fx.ecb_provider import default_ecb_rate_provider

    return default_ecb_rate_provider()


@contextmanager
def live_exchange_rate_composition() -> Generator[None]:
    """Bind the ECB reference-rate provider for the enclosed host session."""
    from ..application.exchange_rate_provider import bind_exchange_rate_provider_factory

    with bind_exchange_rate_provider_factory(_ecb_rate_provider):
        yield


__all__ = ["live_exchange_rate_composition"]
