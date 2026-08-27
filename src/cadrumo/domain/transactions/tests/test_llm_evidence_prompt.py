"""Render-level tests: attached-evidence text reaches the prompt, selection-only.

The classifier sends prompts via stdin (never a file), so injecting evidence text
into the rendered prompt writes nothing to disk. These tests prove the evidence
text is injected and that the selection-only guard (no euro figures copied out)
travels with it.
"""

from __future__ import annotations

import json
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
    parse_response,
    prompt_spec_with_saturation_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
_EVIDENCE = "Factura Acme SL material de oficina base 100,00 IVA 21,00 total 121,00"


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="row-evidence",
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
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )


def test_evidence_text_is_injected_into_prompt() -> None:
    prompt = prompt_spec_with_saturation_fields(year=2025).render(_transaction(), evidence_text=_EVIDENCE)
    assert _EVIDENCE in prompt
    assert "begin evidence" in prompt
    # The selection-only guard must travel with the evidence: never emit its numbers.
    assert "Do NOT copy or output any euro amount" in prompt


def test_prompt_without_evidence_has_no_evidence_section() -> None:
    prompt = prompt_spec_with_saturation_fields(year=2025).render(_transaction())
    assert "begin evidence" not in prompt
    assert _EVIDENCE not in prompt


def test_multiple_components_asked_only_when_evidence_present() -> None:
    """The multiplicity judgement is requested only when there is an invoice to read.

    On the bare bank-row path the model cannot judge multiplicity, so the field
    and its instruction must be absent; with evidence text or an attached image
    they must be present.
    """
    spec = prompt_spec_with_saturation_fields(year=2025)
    bare = spec.render(_transaction())
    assert '"multiple_components"' not in bare
    assert "multiple_components true" not in bare

    with_text = spec.render(_transaction(), evidence_text=_EVIDENCE)
    assert '"multiple_components"' in with_text
    assert "multiple_components true" in with_text

    with_image = spec.render(_transaction(), evidence_image_present=True)
    assert '"multiple_components"' in with_image


def test_multiple_components_survives_the_allow_list_parse() -> None:
    """A model-emitted multiplicity flag round-trips through the allow-list parse."""
    spec = prompt_spec_with_saturation_fields(year=2025)
    flagged = parse_response(
        json.dumps(
            {
                "classification": "BUSINESS",
                "confidence": 0.9,
                "reason": "two distinct rate lines on the attached invoice",
                "iva_category": "domestic_general",
                "multiple_components": True,
            },
        ),
        spec=spec,
    )
    assert flagged.multiple_components is True

    # Absent in the payload -> None (no judgement was made / no evidence read).
    unflagged = parse_response(
        json.dumps({"classification": "BUSINESS", "confidence": 0.9, "reason": "single line"}),
        spec=spec,
    )
    assert unflagged.multiple_components is None
