"""Canonical invoice identity selection with typed refusal facts."""

from __future__ import annotations

from collections.abc import Collection
from enum import StrEnum

from ...domain.invoices.errors import InvoiceError


class InvoiceLookupRefusalReason(StrEnum):
    """Finite reasons why an invoice selector cannot identify one record."""

    REQUIRED = "required"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


class InvoiceLookupRefusedError(InvoiceError):
    """Retain only canonical lookup facts for authorized refusal projection."""

    def __init__(
        self,
        *,
        reason: InvoiceLookupRefusalReason,
        invoice_id: str,
        candidate_ids: tuple[str, ...] = (),
    ) -> None:
        """Bind the reason to the actual selector and ordered candidate identities."""
        self.reason = reason
        self.invoice_id = invoice_id
        self.candidate_ids = candidate_ids
        key = {
            InvoiceLookupRefusalReason.REQUIRED: "application.invoices.lifecycle.errors.invoice_id_required",
            InvoiceLookupRefusalReason.NOT_FOUND: "application.invoices.lifecycle.errors.invoice_not_found",
            InvoiceLookupRefusalReason.AMBIGUOUS: "application.invoices.lifecycle.errors.ambiguous_invoice_prefix",
        }[reason]
        context = {"invoice_id": invoice_id}
        if reason is InvoiceLookupRefusalReason.AMBIGUOUS:
            context["candidates"] = ", ".join(candidate_ids)
        super().__init__(translated_message=key, context=context)


def select_catalogue_invoice_id(invoice_ids: Collection[str], selector: str) -> str:
    """Return the one invoice id ``selector`` names, exactly or by unambiguous prefix.

    An exact id wins outright. Otherwise a case-sensitive prefix is accepted
    only when exactly one id carries it; candidates keep ``invoice_ids`` order.

    Raises:
        InvoiceLookupRefusedError: when the selector is empty, matches nothing
            or matches more than one id.
    """
    trimmed = selector.strip()
    if not trimmed:
        raise InvoiceLookupRefusedError(reason=InvoiceLookupRefusalReason.REQUIRED, invoice_id=trimmed)
    if trimmed in invoice_ids:
        return trimmed
    matches = tuple(invoice_id for invoice_id in invoice_ids if invoice_id.startswith(trimmed))
    if not matches:
        raise InvoiceLookupRefusedError(reason=InvoiceLookupRefusalReason.NOT_FOUND, invoice_id=trimmed)
    if len(matches) > 1:
        raise InvoiceLookupRefusedError(
            reason=InvoiceLookupRefusalReason.AMBIGUOUS,
            invoice_id=trimmed,
            candidate_ids=matches,
        )
    return next(iter(matches))
