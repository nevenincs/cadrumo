"""Synthetic method-asset inputs for the installed public lifecycle journey."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import cast

from dev.acceptance.assets.oracles import first_year_machinery_constant_percentage

METHOD_ASSET_ID = "assets-tui-constant-percentage-machine-2025"

#: Basis of the machine the ledger payment records and the register first names.
METHOD_ACQUISITION_BASIS = "2000.00"

#: File beside a child receipt that names the seeded acquisition payment for that child.
ACQUISITION_SIDECAR_NAME = "acquisition-transaction-id.txt"

_TRANSACTION_ID = re.compile(r"[0-9a-f]{64}")


# The corrected EUR 1,800 machinery basis at a 30% constant percentage.
METHOD_CORRECTED_FORECAST_AMOUNT = str(first_year_machinery_constant_percentage(Decimal("1800.00")))


def method_revision_json(*, acquisition_transaction_id: str) -> str:
    """Build the machine's first revision on the ledger payment that bought it."""
    return json.dumps(
        {
            "asset_id": METHOD_ASSET_ID,
            "revision_number": 1,
            "acquisition": {
                "observed_transaction_id": acquisition_transaction_id,
                "invoice_evidence_id": "synthetic-installed-tui-material-invoice",
                "evidence_fingerprint": "b" * 64,
            },
            "acquisition_shape": "primary_purchase",
            "asset_kind": "material",
            "basis": {
                "stage": "business_allocated",
                "basis_amount": METHOD_ACQUISITION_BASIS,
                "non_deductible_iva": "0.00",
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


def method_correction_json(*, supersedes_revision_id: str, acquisition_transaction_id: str) -> str:
    """Build a synthetic correction only after public inspection supplied its ID."""
    raw_document: object = json.loads(method_revision_json(acquisition_transaction_id=acquisition_transaction_id))
    if not isinstance(raw_document, dict):  # pragma: no cover - static fixture invariant
        raise RuntimeError("method installed-TUI fixture is not a JSON object")
    document = cast("dict[str, object]", raw_document)
    document["revision_number"] = 2
    document["supersedes_revision_id"] = supersedes_revision_id
    document["basis"] = {
        "stage": "business_allocated",
        "basis_amount": "1800.00",
        "non_deductible_iva": "0.00",
        "prior_allocation_provenance": "synthetic corrected TUI allocation",
    }
    return json.dumps(document, separators=(",", ":"))


def write_acquisition_sidecar(directory: Path, transaction_id: str) -> None:
    """Hand the seeded acquisition payment to a child process that cannot reach the CLI."""
    if _TRANSACTION_ID.fullmatch(transaction_id) is None:
        raise ValueError("the acquisition payment is not a ledger transaction identity")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ACQUISITION_SIDECAR_NAME).write_text(f"{transaction_id}\n", encoding="ascii", newline="\n")


def read_acquisition_sidecar(directory: Path) -> str:
    """Read the acquisition payment the parent seeded for this child."""
    transaction_id = (directory / ACQUISITION_SIDECAR_NAME).read_text(encoding="ascii").strip()
    if _TRANSACTION_ID.fullmatch(transaction_id) is None:
        raise ValueError("the acquisition sidecar does not hold a ledger transaction identity")
    return transaction_id
