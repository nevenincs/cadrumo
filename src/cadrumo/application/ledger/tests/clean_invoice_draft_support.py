"""The arithmetically closed, anchored supplier invoice draft the confirmation-gate tests start from."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ..invoice_draft_records import FieldProvenance, InvoiceDraft

_YEAR = filing_year_envelope().horizon


def clean_invoice_draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="ESB00015016",
        supplier_name="Proveedor Ejemplo SL",
        invoice_number="PROV-2024-0001",
        invoice_date=date(_YEAR - 2, 11, 15).isoformat(),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="ESB00015016",
            ),
        ),
    )
