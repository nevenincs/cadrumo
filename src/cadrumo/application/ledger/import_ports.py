"""Application-owned capabilities for ledger source imports.

The ledger import action coordinates source parsing and persistence, but it
does not choose a provider implementation or know the secure-object namespace
used by the transaction catalogue.  Those choices are supplied by an outer
composition root through the two capabilities in :class:`LedgerImportPorts`.

The value records in this module are the small application boundary DTOs.  An
inbound adapter may use richer parser records internally, but it must translate
them to these records before handing control to the application action.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.raw_transaction import RawTransaction
from .protocols import FinancialProviderProtocol


@dataclass(frozen=True, slots=True)
class LedgerParsedRow:
    """Application view of one parsed source row."""

    raw: RawTransaction
    direction: TransactionDirection


@dataclass(frozen=True, slots=True)
class LedgerProviderValidation:
    """Application view of provider validation facts."""

    is_valid: bool
    warnings: tuple[str, ...] = ()
    detected_encoding: str | None = None
    detected_dialect: str | None = None
    unavailable_optional_extra: Mapping[str, str | bool] | None = None


@runtime_checkable
class LedgerProviderResolverProtocol(Protocol):
    """Resolve one canonical provider ID to an application source port."""

    def resolve(self, *, provider_id: str, path: Path) -> FinancialProviderProtocol | None:
        """Return a source provider, or ``None`` when detection declines it.

        Implementations translate all provider-specific parser errors to the
        application transaction-validation error before they cross this port.
        """
        ...


@runtime_checkable
class TransactionCatalogueLocationProtocol(Protocol):
    """Render the application-facing location of a persisted catalogue."""

    def path_for(self, *, bucket_id: str) -> str:
        """Return the stable display/reference path for one bucket catalogue."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerImportPorts:
    """Required source and catalogue-location capabilities for ledger import."""

    provider_resolver: LedgerProviderResolverProtocol
    catalogue_location: TransactionCatalogueLocationProtocol


__all__ = [
    "LedgerImportPorts",
    "LedgerParsedRow",
    "LedgerProviderResolverProtocol",
    "LedgerProviderValidation",
    "TransactionCatalogueLocationProtocol",
]
