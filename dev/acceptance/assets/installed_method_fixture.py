"""Synthetic method-asset inputs for the installed public lifecycle journey."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

from dev.acceptance.assets.oracles import first_year_machinery_constant_percentage

METHOD_ASSET_ID = "assets-tui-constant-percentage-machine-2025"


# The corrected EUR 1,800 machinery basis at a 30% constant percentage.
METHOD_CORRECTED_FORECAST_AMOUNT = str(first_year_machinery_constant_percentage(Decimal("1800.00")))


METHOD_REVISION_JSON = json.dumps(
    {
        "asset_id": METHOD_ASSET_ID,
        "revision_number": 1,
        "acquisition": {
            "observed_transaction_id": "a" * 64,
            "invoice_evidence_id": "synthetic-installed-tui-material-invoice",
            "evidence_fingerprint": "b" * 64,
        },
        "acquisition_shape": "primary_purchase",
        "asset_kind": "material",
        "basis": {
            "stage": "business_allocated",
            "basis_amount": "2000.00",
            "prior_allocation_provenance": "synthetic installed TUI allocation",
        },
        "in_service_date": "2025-01-01",
        "opening_history": {"status": "known", "accumulated_amount": "0.00"},
        "acquired_condition": "new",
        "amortization": {
            "regime": "normal",
            "method": "constant_percentage",
            "authority_class_key": "maquinaria",
        },
    },
    separators=(",", ":"),
)


def method_correction_json(*, supersedes_revision_id: str) -> str:
    """Build a synthetic correction only after public inspection supplied its ID."""
    raw_document: object = json.loads(METHOD_REVISION_JSON)
    if not isinstance(raw_document, dict):  # pragma: no cover - static fixture invariant
        raise RuntimeError("method installed-TUI fixture is not a JSON object")
    document = cast("dict[str, object]", raw_document)
    document["revision_number"] = 2
    document["supersedes_revision_id"] = supersedes_revision_id
    document["basis"] = {
        "stage": "business_allocated",
        "basis_amount": "1800.00",
        "prior_allocation_provenance": "synthetic corrected TUI allocation",
    }
    return json.dumps(document, separators=(",", ":"))
