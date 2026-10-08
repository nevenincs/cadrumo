"""Canonical invoice identity selection with typed refusal facts."""

from __future__ import annotations

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
