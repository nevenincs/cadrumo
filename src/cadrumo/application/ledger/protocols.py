"""Application-layer port protocols for the ledger service.

Defines structural :class:`typing.Protocol` interfaces consumed by
:mod:`cadrumo.application.ledger.actions_import` so that the application layer
depends only on these protocol types, not on concrete adapter classes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...adapters.inbound.financial.providers.base import ParsedLedgerRow, ProviderValidation


@runtime_checkable
class FinancialProviderProtocol(Protocol):
    """Protocol satisfied by any file-backed raw transaction provider.

    Covers exactly the two methods called by the ledger import service:
    :meth:`ingest` and :meth:`validate_source`.  Adapter-internal helpers
    (``_build_provenance``, ``_read_source_bytes``, etc.) remain private
    to the adapter implementation.
    """

    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield parsed ledger rows from ``path``.

        Each yielded item is a :class:`ParsedLedgerRow` (a magnitude
        :class:`RawTransaction` plus its :class:`TransactionDirection`)
        parsed from the provider-format file at ``path``.
        """
        ...

    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate ``path`` and return a :class:`ProviderValidation` result."""
        ...


__all__ = ["FinancialProviderProtocol"]
