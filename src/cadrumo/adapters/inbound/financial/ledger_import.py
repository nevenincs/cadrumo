"""Adapter boundary for application-owned ledger import capabilities.

Concrete statement providers remain in :mod:`.providers`.  This module is the
translation point that makes their DTOs and failure hierarchy invisible to the
application ledger action, and it binds the storage-facing catalogue location
without exporting storage namespace metadata inward.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import override

from ....application.ledger.import_ports import (
    LedgerImportPorts,
    LedgerParsedRow,
    LedgerProviderValidation,
    TransactionCatalogueLocationProtocol,
)
from ....application.ledger.protocols import FinancialProviderProtocol
from ....core.errors.error_codes import resolve_error_message
from ....domain.transactions.errors import TransactionValidationError
from ...persistence.storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from .providers.base import FinancialProvider, FinancialProviderError
from .providers.csv import CsvProvider
from .providers.detection import detect_provider
from .providers.ofx import OfxProvider
from .providers.pdf_n26 import PdfN26Provider
from .providers.xlsx import XlsxProvider


class _FinancialProviderBoundary(FinancialProviderProtocol):
    """Translate one concrete parser to the application provider protocol."""

    def __init__(self, provider: FinancialProvider) -> None:
        self._provider = provider

    @override
    def ingest(self, path: Path) -> Iterator[LedgerParsedRow]:
        """Yield application rows while translating provider failures."""
        try:
            for row in self._provider.ingest(path):
                yield LedgerParsedRow(raw=row.raw, direction=row.direction)
        except FinancialProviderError as exc:
            raise _translate_provider_error(exc, operation="ingest", path=path) from exc

    @override
    def validate_source(self, path: Path) -> LedgerProviderValidation:
        """Return application validation facts while translating failures."""
        try:
            result = self._provider.validate_source(path)
        except FinancialProviderError as exc:
            raise _translate_provider_error(exc, operation="validate", path=path) from exc
        return LedgerProviderValidation(
            is_valid=result.is_valid,
            warnings=tuple(result.warnings),
            detected_encoding=result.detected_encoding,
            detected_dialect=result.detected_dialect,
            unavailable_optional_extra=(
                None if result.unavailable_optional_extra is None else dict(result.unavailable_optional_extra)
            ),
        )


class FinancialProviderResolverAdapter:
    """Resolve the supported provider IDs using the concrete parser registry."""

    def resolve(self, *, provider_id: str, path: Path) -> FinancialProviderProtocol | None:
        """Return a translated provider for ``provider_id`` and ``path``."""
        try:
            provider = self._resolve_concrete_provider(provider_id=provider_id, path=path)
        except FinancialProviderError as exc:
            raise _translate_provider_error(exc, operation="resolve", path=path) from exc
        return None if provider is None else _FinancialProviderBoundary(provider)

    @staticmethod
    def _resolve_concrete_provider(*, provider_id: str, path: Path) -> FinancialProvider | None:
        """Select and construct the parser owned by this adapter package."""
        if provider_id in {"auto", "n26"}:
            return detect_provider(path)
        if provider_id == "csv":
            return CsvProvider()
        if provider_id in {"ofx", "qfx"}:
            return OfxProvider()
        if provider_id in {"xlsx", "excel"}:
            return XlsxProvider()
        if provider_id in {"pdf", "pdf-n26"}:
            return PdfN26Provider()
        raise TransactionValidationError(
            translated_message="errors.transaction.unknown_ledger_provider",
            context={"provider": provider_id},
        )


class SecureTransactionCatalogueLocationAdapter(TransactionCatalogueLocationProtocol):
    """Translate the transaction catalogue namespace to its public URI form."""

    @override
    def path_for(self, *, bucket_id: str) -> str:
        """Return the stable URI used in application import summaries."""
        return f"db://secure_objects/{TRANSACTION_CATALOGUE_NAMESPACE.namespace}/transaction-catalogue:{bucket_id}"


def build_ledger_import_ports() -> LedgerImportPorts:
    """Compose the provider and catalogue-location capabilities for import."""
    return LedgerImportPorts(
        provider_resolver=FinancialProviderResolverAdapter(),
        catalogue_location=SecureTransactionCatalogueLocationAdapter(),
    )


def _translate_provider_error(
    error: FinancialProviderError,
    *,
    operation: str,
    path: Path,
) -> TransactionValidationError:
    """Translate adapter-specific provider errors at the application boundary."""
    return TransactionValidationError(
        translated_message="errors.transaction.ledger_import_failed",
        context={
            "operation": operation,
            "path": str(path),
            "reason": resolve_error_message(error),
        },
    )


__all__ = ["build_ledger_import_ports"]
