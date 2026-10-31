"""Ledger transaction projection fixture shared by operation request and result tests."""

from __future__ import annotations

from ..transaction_projection import LedgerTransactionProjection

_DEFAULT_FIELDS: dict[str, object] = {
    "transaction_id": "b" * 64,
    "date": "2026-04-15",
    "booked_date": "2026-04-15",
    "value_date": None,
    "amount": "121.00",
    "currency": "EUR",
    "direction": "OUTFLOW",
    "counterparty": "Client SL",
    "description": "Invoice 1",
    "business_classification": "MIXED",
    "business_pct": "0.5",
    "category_id": None,
    "taxable_base": None,
    "iva_rate": None,
    "iva_amount": None,
    "iva_category": None,
    "counterparty_country": None,
    "counterparty_identification_state": None,
    "irpf_category": None,
    "m210_income_classification": None,
    "usage_ratio_id": None,
    "prorrata_reference": None,
    "purchase_invoice_evidence_id": None,
    "invoice_id": None,
    "attachment_ids": (),
    "notes": "",
    "lifecycle_state": "ACTIVE",
    "classified_by": "manual",
    "classified_at": None,
    "classification_reason": "",
    "classification_confidence": None,
    "source_jurisdiction": None,
    "value_in_eur": None,
    "fx_rate": None,
    "created_at": "2026-04-15T09:30:00+00:00",
    "modified_at": "2026-04-15T09:30:00+00:00",
}


def ledger_transaction_projection(**overrides: object) -> LedgerTransactionProjection:
    """Return a mixed-use outflow projection; each override replaces one named field."""
    unknown = overrides.keys() - _DEFAULT_FIELDS.keys()
    assert not unknown, f"not projection fields: {sorted(unknown)}"
    return LedgerTransactionProjection.model_validate({**_DEFAULT_FIELDS, **overrides})
