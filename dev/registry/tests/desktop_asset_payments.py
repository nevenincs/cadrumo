"""The ledger payments a desktop Assets request is built against, as the ledger accounts for them.

The contract test builds its requests against a synthetic payment of its own,
since it only decodes them. The creation corpus builds its requests against the
payments the scenario register really holds, so a recorded creation names a
payment the register can take as its acquisition. Both shapes are the same
candidate the register serves, so they live together here.
"""

from __future__ import annotations

from typing import Any

_HEX = {name: name * 64 for name in "abce"}


def candidate(
    *,
    transaction_id: str,
    invoice_evidence_id: str | None,
    evidence_fingerprint: str | None,
    description: str,
    booked_date: str,
    taxable_base: str,
    iva_amount: str,
) -> dict[str, Any]:
    """One payment the register offers, in the shape its read model serves."""
    base = float(taxable_base) + float(iva_amount)
    return {
        "transaction_id": transaction_id,
        "booked_date": booked_date,
        "description": description,
        "amount": {"decimal": f"{base:.2f}"},
        "currency": "EUR",
        "paid_in_euro": {"decimal": f"{base:.2f}"},
        "taxable_base": {"decimal": taxable_base},
        "iva_amount": {"decimal": iva_amount},
        "non_deductible_iva_state": "known",
        "non_deductible_iva_state_key": "ledger.actividad_asset.non_deductible_iva_state.known",
        "non_deductible_iva": {"decimal": "0.00"},
        "invoice_evidence_id": invoice_evidence_id,
        "evidence_fingerprint": evidence_fingerprint,
    }


#: The purchase the contract test's person picks, which it only decodes.
CANDIDATE = candidate(
    transaction_id=_HEX["a"],
    invoice_evidence_id=_HEX["b"],
    evidence_fingerprint=_HEX["c"],
    description="Compra",
    booked_date="2026-05-06",
    taxable_base="900.00",
    iva_amount="189.00",
)

#: The later payment that test's person picks for an element bought outside the ledger.
LATER_PAYMENT = {
    **CANDIDATE,
    "transaction_id": _HEX["e"],
    "description": "Segundo plazo",
    "invoice_evidence_id": None,
    "evidence_fingerprint": None,
}
