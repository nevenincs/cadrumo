"""Application-layer port protocols for the ledger service.

Defines structural :class:`typing.Protocol` interfaces consumed by
:mod:`cadrumo.application.ledger.actions_import` so that the application layer
depends only on these protocol types, not on concrete adapter classes.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.raw_transaction import RawTransaction


@runtime_checkable
class ParsedLedgerRowProtocol(Protocol):
    """Structural view of one parsed financial source row."""

    @property
    def raw(self) -> RawTransaction:
        """Return the domain raw transaction carried by this row."""
        ...

    @property
    def direction(self) -> TransactionDirection:
        """Return the authoritative flow direction for this row."""
        ...


@runtime_checkable
class ProviderValidationProtocol(Protocol):
    """Structural validation result returned by a financial source port."""

    @property
    def is_valid(self) -> bool:
        """Whether the source can be ingested."""
        ...

    @property
    def warnings(self) -> tuple[str, ...]:
        """Warnings produced while validating the source."""
        ...

    @property
    def detected_encoding(self) -> str | None:
        """Detected source encoding, when the provider reports one."""
        ...

    @property
    def detected_dialect(self) -> str | None:
        """Detected source dialect or layout, when available."""
        ...

    @property
    def unavailable_optional_extra(self) -> Mapping[str, str | bool] | None:
        """Optional-extra facts when the provider cannot run locally."""
        ...


@runtime_checkable
class FinancialProviderProtocol(Protocol):
    """Protocol satisfied by any file-backed raw transaction provider.

    Covers exactly the two methods called by the ledger import service:
    :meth:`ingest` and :meth:`validate_source`.  Adapter-internal helpers
    (``build_provenance``, ``_read_source_bytes``, etc.) remain private
    to the adapter implementation.
    """

    def ingest(self, path: Path) -> Iterator[ParsedLedgerRowProtocol]:
        """Yield parsed ledger rows from ``path``.

        Each yielded item carries a magnitude :class:`RawTransaction` plus its
        :class:`TransactionDirection`, parsed from the provider-format file.
        """
        ...

    def validate_source(self, path: Path) -> ProviderValidationProtocol:
        """Validate ``path`` and return a structured validation result."""
        ...


__all__ = [
    "FinancialProviderProtocol",
    "ParsedLedgerRowProtocol",
    "ProviderValidationProtocol",
]
