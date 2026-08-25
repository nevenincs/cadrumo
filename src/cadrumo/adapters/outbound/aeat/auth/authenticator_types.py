"""Browser protocols for concrete live AEAT authentication adapters.

The protocols mirror the subset of
:class:`adapters.outbound.aeat.browser.BrowserSession` that auth providers
need, so tests and adapter callers can satisfy the same structural contract
without importing Playwright directly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import SecretStr

from .....core.errors import AeatLoginAssertionError
from .certificate import CertificateHealth


class PersistedSessionInvalidError(AeatLoginAssertionError):
    """Raised when a persisted AEAT browser session cannot be trusted."""


@runtime_checkable
class CertificateHealthCheck(Protocol):
    """Callable shape used to evaluate a loaded certificate's health."""

    def __call__(
        self,
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        friendly_name: str | None = ...,
        now: datetime | None = ...,
    ) -> CertificateHealth:
        """Return :class:`CertificateHealth` for the supplied PKCS#12 bundle."""
        ...


__all__ = [
    "CertificateHealthCheck",
    "PersistedSessionInvalidError",
]
