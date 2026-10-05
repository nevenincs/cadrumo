"""Host-composed exchange-rate provider for euro conversion.

Which rate authority converts foreign amounts is decided once by the process
host -- the ``aeat`` console script, the workbench, the MCP server -- and read
here by every conversion path. Application and adapter code never constructs a
transport of its own, so a host that must not reach the network (a test run)
composes a different provider without any branch in the code that converts.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar

from ..core.errors.hierarchy import InternalInvariantError
from ..domain.currency.service import ExchangeRateProvider

type ExchangeRateProviderFactory = Callable[[], ExchangeRateProvider]
"""Return the host's provider; called on each use so importing it stays lazy."""

_BOUND_EXCHANGE_RATE_PROVIDER_FACTORY: ContextVar[ExchangeRateProviderFactory] = ContextVar(
    "cadrumo_exchange_rate_provider_factory",
)


@contextmanager
def bind_exchange_rate_provider_factory(
    factory: ExchangeRateProviderFactory,
) -> Generator[ExchangeRateProviderFactory]:
    """Bind the host's exchange-rate provider factory for one runtime scope."""
    token = _BOUND_EXCHANGE_RATE_PROVIDER_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_EXCHANGE_RATE_PROVIDER_FACTORY.reset(token)


def exchange_rate_provider() -> ExchangeRateProvider:
    """Return the provider the process host composed."""
    try:
        factory = _BOUND_EXCHANGE_RATE_PROVIDER_FACTORY.get()
    except LookupError as error:
        raise InternalInvariantError("the exchange-rate provider has not been composed by the host") from error
    return factory()


__all__ = [
    "ExchangeRateProviderFactory",
    "bind_exchange_rate_provider_factory",
    "exchange_rate_provider",
]
