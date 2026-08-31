"""Provenance reaches the operator on BOTH evidence surfaces, whole.

Grounding parity with casilla observations (``aeat-calculation-grounding``): a
value's provenance is not an application-layer detail that stops at the boundary
-- it travels to every operator-facing JSON payload, because an operator who
cannot tell an exactly-parsed figure from a model-read one has no basis for the
extra scrutiny the second deserves before a filing is built on it.

Extract alone is not sufficient. Confirm is the surface an operator meets when a
record is actually minted, and a provenance record present at review and absent
at confirm is present exactly where it is least needed.

These cases assert the SERIALIZED envelope body, not merely the model: the
schemas are ``strict=True`` and emit-only, so what an operator receives is the
JSON document rather than a re-validated model.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ....application.ledger.invoice_draft_records import FieldAmbiguityCandidate, FieldProvenance, InvoiceDraft
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from .._command_schema import command_schema_types
from .._ledger_business_payloads import EvidenceConfirmResult, EvidenceExtractResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROVENANCE_BEARING_COMMANDS = ("ledger.evidence.extract", "ledger.evidence.confirm")


def _draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="B12345674",
        taxable_base=Decimal("1000.00"),
        provenance=(
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.RECONCILED,
                anchor="1.000,00 €",
                note="closes against the printed total",
            ),
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.VISION,
                grounding=FieldGroundingOutcome.AMBIGUOUS,
                anchor="B-12345674",
                candidates=(
                    FieldAmbiguityCandidate(value="B12345674", anchor="B-12345674"),
                    FieldAmbiguityCandidate(value="X1234567L", anchor="X-1234567-L"),
                ),
            ),
        ),
    )


@pytest.mark.parametrize("command", _PROVENANCE_BEARING_COMMANDS)
def test_both_evidence_surfaces_declare_the_provenance_channel(command: str) -> None:
    """Registered under their command paths, so the conformance gate sees them."""
    schema = command_schema_types()[command]

    assert "provenance" in schema.model_fields
    assert "discrepancies" in schema.model_fields


def test_the_extract_envelope_body_carries_every_envelope_whole() -> None:
    dumped = json.loads(_draft().model_dump_json())
    payload = {"bucket_id": "b", "evidence_id": "e", "attachment_id": None, **dumped}

    emitted = EvidenceExtractResult.model_validate_json(json.dumps(payload)).model_dump(mode="json")

    assert emitted["provenance"] == dumped["provenance"]


def test_the_confirm_envelope_body_carries_the_drafts_provenance() -> None:
    """Confirm mirrors the projection the CLI builds from ``result.draft``."""
    draft = _draft()
    payload = {
        "bucket_id": "b",
        "evidence_id": "e",
        "attachment_id": None,
        "created": True,
        "invoice_id": "a" * 64,
        "kind": "received",
        "invoice_number": "0042",
        "issued_at": "2026-03-14",
        "counterparty_name": "Proveedor Ejemplo SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": "1000.00",
        "iva_total": "210.00",
        "grand_total": "1210.00",
        "currency": "EUR",
        "payment_status": "unpaid",
        "provenance": [json.loads(envelope.model_dump_json()) for envelope in draft.provenance],
        "discrepancies": [json.loads(finding.model_dump_json()) for finding in draft.discrepancies],
    }

    emitted = EvidenceConfirmResult.model_validate_json(json.dumps(payload)).model_dump(mode="json")

    assert len(emitted["provenance"]) == 2
    reconciled = next(e for e in emitted["provenance"] if e["field"] == "taxable_base")
    assert reconciled["origin"] == FieldOrigin.EXACT_STRUCTURED.value
    assert reconciled["grounding"] == FieldGroundingOutcome.RECONCILED.value
    assert reconciled["anchor"] == "1.000,00 €"
    ambiguous = next(e for e in emitted["provenance"] if e["field"] == "supplier_tax_id")
    assert [c["value"] for c in ambiguous["candidates"]] == ["B12345674", "X1234567L"]


@pytest.mark.parametrize("command", _PROVENANCE_BEARING_COMMANDS)
def test_no_operator_surface_carries_a_numeric_model_confidence(command: str) -> None:
    """Permanently ruled out: a model's estimate of its own output is not evidence.

    Gated on the property rather than a field list, so a future field named for
    a self-reported score fails here whatever it is called. Scoped to property
    NAMES across the whole nested schema -- including ``$defs``, which is where
    the provenance and discrepancy sub-models live -- rather than to the schema
    text, which legitimately mentions the axis in the prose ruling it out.
    """
    forbidden = ("confidence", "score", "probability", "certainty", "likelihood")
    document = command_schema_types()[command].model_json_schema()

    names: list[str] = []

    def _collect(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.extend(str(key) for key in properties)
            for value in node.values():
                _collect(value)
        elif isinstance(node, list):
            for value in node:
                _collect(value)

    _collect(document)
    assert names, "the schema declares no properties; this gate is misdirected"

    offending = [name for name in names if any(token in name.lower() for token in forbidden)]
    assert not offending, f"{command} exposes a self-reported confidence axis: {sorted(set(offending))}"
