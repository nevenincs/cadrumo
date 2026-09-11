"""Application-owned invoice-draft projection contracts.

Extraction is an application workflow.  The reviewable draft and its nested
provenance records therefore belong below the CLI transport; the CLI only
renders these strict contracts.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.json_contract import OutputSchema


class EvidenceDraftLinePayload(OutputSchema):
    """One extracted invoice line on a reviewable draft."""

    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    recargo_rate: str | None = None
    recargo_amount: str | None = None


class EvidenceDraftRateBreakdownPayload(OutputSchema):
    """One per-rate subtotal extracted from a multi-rate invoice."""

    iva_rate: str | None = None
    taxable_base: str | None = None
    iva_amount: str | None = None
    recargo_rate: str | None = None
    recargo_amount: str | None = None


class EvidenceFieldAmbiguityCandidatePayload(OutputSchema):
    """One competing reading a grounding pass could not decide between."""

    value: str
    anchor: str | None = None
    note: str = ""


class EvidenceFieldProvenancePayload(OutputSchema):
    """How one draft field was obtained and what checking it survived."""

    field: str
    origin: str
    grounding: str
    anchor: str | None = None
    refused_anchor: str | None = None
    candidates: list[EvidenceFieldAmbiguityCandidatePayload] = []
    anchor_self_reported: bool = False
    derived_from: list[str] = []
    role_evidence: str | None = None
    attribution_unverified: bool = False
    note: str = ""


class EvidenceDraftDiscrepancyPayload(OutputSchema):
    """One deterministic check the read document failed."""

    kind: str
    field: str | None = None
    detail: str = ""
    expected: str | None = None
    observed: str | None = None


class EvidenceExtractResult(OutputSchema):
    """Reviewable application result for best-effort invoice extraction."""

    bucket_id: BucketId
    evidence_id: str | None = None
    attachment_id: str | None = None
    supplier_tax_id: TaxIdIdentityToken | None = None
    supplier_name: str | None = None
    customer_tax_id: TaxIdIdentityToken | None = None
    customer_name: str | None = None
    supplier_postal_code: str | None = None
    customer_postal_code: str | None = None
    supplier_country: str | None = None
    customer_country: str | None = None
    supplier_country_code: str | None = None
    customer_country_code: str | None = None
    supplier_stated_country_code: str | None = None
    customer_stated_country_code: str | None = None
    invoice_number: str | None = None
    invoice_series: str | None = None
    rectifies_invoice_number: str | None = None
    proposed_supply_nature: str | None = None
    invoice_date: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    grand_total: str | None = None
    currency: str | None = None
    recargo_amount: str | None = None
    retencion_rate: str | None = None
    retencion_amount: str | None = None
    suplidos_amount: str | None = None
    lines: list[EvidenceDraftLinePayload] = []
    iva_breakdown: list[EvidenceDraftRateBreakdownPayload] = []
    iva_category: str | None = None
    regime_legend: str | None = None
    suggested_kind: str | None = None
    transcription_sha256: str | None = None
    provenance: list[EvidenceFieldProvenancePayload] = []
    discrepancies: list[EvidenceDraftDiscrepancyPayload] = []
    raw_text_length: int = 0
    off_host_provider: str | None = None
    off_host_acknowledged_surface: str | None = None


__all__ = [
    "EvidenceDraftDiscrepancyPayload",
    "EvidenceDraftLinePayload",
    "EvidenceDraftRateBreakdownPayload",
    "EvidenceExtractResult",
    "EvidenceFieldAmbiguityCandidatePayload",
    "EvidenceFieldProvenancePayload",
]
