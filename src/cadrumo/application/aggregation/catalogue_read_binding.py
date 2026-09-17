"""Refuse catalogue read ports bound to a different profile bucket."""

from __future__ import annotations

from ...core.i18n.translatable import Translatable as tr
from ..invoices.catalogue_reads_ports import BucketBoundCatalogueReader, InvoiceCatalogueReadPorts
from .errors import AggregationValidationError


def require_catalogue_reads_bound_to(ports: InvoiceCatalogueReadPorts, *, bucket_id: str) -> None:
    """Refuse ports whose readers declare a bucket other than ``bucket_id``.

    Composition binds both readers to one bucket, but an aggregation entry
    point is handed the ports and must not trust that: a reader bound to
    another bucket, or to none, would silently aggregate someone else's
    ledger. A reader that declares no bucket at all is an in-memory
    projection with no store behind it and is not checked.
    """
    for reader, message in (
        (ports.transaction_reader, "aggregation.renta_ledger.errors.bucket_mismatch"),
        (ports.invoice_reader, "aggregation.renta_ledger.errors.invoice_bucket_mismatch"),
    ):
        if isinstance(reader, BucketBoundCatalogueReader) and reader.bucket_id != bucket_id:
            raise AggregationValidationError(
                tr(message),
                context={"bucket_id": bucket_id, "repository_bucket_id": reader.bucket_id},
            )


__all__ = ["require_catalogue_reads_bound_to"]
