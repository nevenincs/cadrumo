"""Render-level tests: attached-evidence text reaches the prompt, selection-only.

The classifier sends prompts via stdin (never a file), so injecting evidence text
into the rendered prompt writes nothing to disk. These tests prove the evidence
text is injected and that the selection-only guard (no euro figures copied out)
travels with it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .. import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    prompt_spec_with_saturation_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
_EVIDENCE = "Factura Acme SL material de oficina base 100,00 IVA 21,00 total 121,00"


def _transaction() -> Transaction:
    raw = RawTransaction(
        transaction_id="row-evidence",
        booked_date=date(2025, 3, 1),
        value_date=date(2025, 3, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Acme SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "office supplies"},
    )
    return Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})


def test_evidence_text_is_injected_into_prompt() -> None:
    prompt = prompt_spec_with_saturation_fields().render(_transaction(), evidence_text=_EVIDENCE)
    assert _EVIDENCE in prompt
    assert "begin evidence" in prompt
    # The selection-only guard must travel with the evidence: never emit its numbers.
    assert "Do NOT copy or output any euro amount" in prompt


def test_prompt_without_evidence_has_no_evidence_section() -> None:
    prompt = prompt_spec_with_saturation_fields().render(_transaction())
    assert "begin evidence" not in prompt
    assert _EVIDENCE not in prompt
