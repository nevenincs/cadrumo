"""The draft waist is loss-forbidden: nothing read may be dropped on the way out.

The measured defect this gate exists for is a PROJECTION defect, not a reading
defect: values were recovered from documents correctly and then discarded
between the draft and the payload the operator actually sees. A field silently
absent from the confirm surface is indistinguishable, to the operator, from a
field the document never stated -- so the loss produces a plausible record and
no signal.

The gate therefore sits on the projection rather than on the reader, and it
gates on the PROPERTY (every draft field reaches the payload, carrying its
value) rather than on a field tally, which would encode today's shape and then
detect nothing.

This module reaches across into ``entrypoints.cli`` deliberately: the parity
being asserted is precisely between the application-layer draft and the CLI
payload, and a gate that could not see both ends could not assert it.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from ....entrypoints.cli._ledger_business_payloads import (
    EvidenceDraftDiscrepancyPayload,
    EvidenceDraftLinePayload,
    EvidenceDraftRateBreakdownPayload,
    EvidenceExtractResult,
    EvidenceFieldAmbiguityCandidatePayload,
    EvidenceFieldProvenancePayload,
)
from ..evidence_draft import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
)
from .test_evidence_draft_provenance import _fully_populated_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Every draft sub-model paired with the payload model that mirrors it.
#:
#: The top-level parity above stops at the waist, and the nested models are
#: hand-mirrored -- the payload envelope's own comments say "Mirrors
#: FieldProvenance.x" field by field, which is a convention and not a contract.
#: The failure that hole permits is not a silent drop but a LOUD one at the
#: wrong moment: every payload model forbids extras, so a field added to a
#: draft sub-model without its counterpart makes a valid operator command
#: return a refusal, and that was walked through in practice when a provenance
#: field gained a member its payload did not.
#:
#: Listed as pairs rather than derived by name, because the naming is not
#: mechanical (``InvoiceDraftLine`` against ``EvidenceDraftLinePayload``) and a
#: derivation that silently matched nothing would make this vacuous. The count
#: is floored below instead, so a pair dropped from this table is visible.
_NESTED_PAIRS: tuple[tuple[str, type[BaseModel], type[BaseModel]], ...] = (
    ("line", InvoiceDraftLine, EvidenceDraftLinePayload),
    ("rate breakdown", InvoiceDraftRateBreakdown, EvidenceDraftRateBreakdownPayload),
    ("ambiguity candidate", FieldAmbiguityCandidate, EvidenceFieldAmbiguityCandidatePayload),
    ("field provenance", FieldProvenance, EvidenceFieldProvenancePayload),
    ("discrepancy finding", DraftDiscrepancyFinding, EvidenceDraftDiscrepancyPayload),
)

#: Fields the extract payload carries that the draft does not: facts about the
#: CALL rather than about the document. Named explicitly so a NEW unexplained
#: payload-only field is visible rather than absorbed.
#:
#: The first three are the operator's own reference into the call. The last two
#: record how the read was authorised to travel, and they belong here for the
#: same structural reason: consent is granted per invocation, so it is a
#: property of the call and has no per-field draft origin to mirror. Putting
#: them on the draft would have forced a per-field copy of a single fact.
_REFERENCE_FIELDS = frozenset(
    {
        "bucket_id",
        "evidence_id",
        "attachment_id",
        "off_host_provider",
        "off_host_acknowledged_surface",
    },
)


def test_every_draft_field_exists_on_the_extract_payload() -> None:
    """Structural parity: no draft field may lack a home on the operator surface."""
    draft_fields = set(InvoiceDraft.model_fields)
    payload_fields = set(EvidenceExtractResult.model_fields)

    missing = draft_fields - payload_fields
    assert not missing, f"the extract payload drops these draft fields entirely: {sorted(missing)}"


def test_the_payload_adds_nothing_beyond_the_declared_reference_fields() -> None:
    """The other direction: a payload field with no draft origin is unexplained.

    Without this, parity could be satisfied by a payload that carries every
    draft field plus arbitrary invented ones, which is a different contract from
    the one the waist claims.
    """
    extra = set(EvidenceExtractResult.model_fields) - set(InvoiceDraft.model_fields) - _REFERENCE_FIELDS
    assert not extra, f"the extract payload carries fields with no draft origin: {sorted(extra)}"


def test_every_populated_draft_value_survives_into_the_payload() -> None:
    """Presence is not enough: the VALUE must arrive, for every field at once.

    Built exactly the way the CLI builds it -- the draft's JSON dump spread
    under the reference fields -- so this exercises the real projection rather
    than a re-implementation of it.
    """
    draft = _fully_populated_draft()
    dumped = json.loads(draft.model_dump_json())
    payload = {
        "bucket_id": "bucket-1",
        "evidence_id": "ev-1",
        "attachment_id": None,
        **dumped,
    }

    result = EvidenceExtractResult.model_validate_json(json.dumps(payload))
    emitted = result.model_dump(mode="json")

    dropped = [name for name, value in dumped.items() if emitted.get(name) != value]
    assert not dropped, f"these draft values did not survive the projection: {sorted(dropped)}"


def test_the_provenance_envelopes_arrive_whole() -> None:
    """Per-field provenance reaches the operator at casilla-grounding parity.

    Not merely that a ``provenance`` list exists, but that each envelope keeps
    its origin, grounding outcome, anchor and ambiguity candidates -- a list of
    field names with the grounding stripped would satisfy a shallower check
    while losing exactly the content that makes an exactly-read value
    distinguishable from a model-read one.
    """
    draft = _fully_populated_draft()
    dumped = json.loads(draft.model_dump_json())
    payload = {"bucket_id": "bucket-1", "evidence_id": "ev-1", "attachment_id": None, **dumped}

    result = EvidenceExtractResult.model_validate_json(json.dumps(payload))
    emitted = result.model_dump(mode="json")["provenance"]

    assert emitted == dumped["provenance"]
    assert {envelope["field"] for envelope in emitted} == {e.field for e in draft.provenance}
    ambiguous = next(e for e in emitted if e["grounding"] == "ambiguous")
    assert len(ambiguous["candidates"]) == 2


# -- the same property, one level down, on every nested model pair ----------


def nested_parity_defects(draft_model: type[BaseModel], payload_model: type[BaseModel]) -> list[str]:
    """Return the field-set divergences between a draft sub-model and its payload.

    Both directions, for the same reasons the top-level pair checks both: a
    field missing from the payload is a value the operator never sees, and a
    payload field with no draft origin is a claim nothing produces.
    """
    draft_fields = set(draft_model.model_fields)
    payload_fields = set(payload_model.model_fields)
    defects = []
    if missing := sorted(draft_fields - payload_fields):
        defects.append(f"payload lacks {missing}")
    if extra := sorted(payload_fields - draft_fields):
        defects.append(f"payload invents {extra}")
    return defects


def test_every_nested_draft_model_is_mirrored_by_its_payload() -> None:
    """A field added to a sub-model without its counterpart refuses a valid command.

    The top-level gate does not reach here, and the payload models forbid
    extras, so the omission does not degrade quietly: the operator's confirm
    verb returns a refusal on a command that is correct. Gating the pair turns
    a hand-kept mirror into a checked one.
    """
    defects = [
        f"{label}: {'; '.join(divergences)}"
        for label, draft_model, payload_model in _NESTED_PAIRS
        if (divergences := nested_parity_defects(draft_model, payload_model))
    ]
    assert not defects, "these nested draft models and their payload counterparts have diverged: " + "; ".join(defects)


def test_the_nested_pair_table_still_covers_the_sub_models() -> None:
    """A pair quietly dropped from the table would make the check above shrink.

    Floored as a bound rather than pinned, so adding a sixth pair does not
    demand a constant update while removing one is still visible.
    """
    assert len(_NESTED_PAIRS) >= 5, f"the nested pair table has shrunk to {len(_NESTED_PAIRS)}"
    for label, draft_model, payload_model in _NESTED_PAIRS:
        assert draft_model.model_fields, f"{label}: the draft model reports no fields"
        assert payload_model.model_fields, f"{label}: the payload model reports no fields"


def test_the_nested_check_catches_a_field_with_no_payload_counterpart() -> None:
    """Mutation proof, driven against a constructed sub-model.

    Built rather than applied to the tree, so no production model is made
    wrong to prove the gate: a subclass gaining one field is exactly the shape
    of the regression -- a draft envelope grows a member and the payload that
    forbids extras is not told.
    """

    class _EnvelopeWithANewField(FieldProvenance):
        territory_hint: str | None = None

    defects = nested_parity_defects(_EnvelopeWithANewField, EvidenceFieldProvenancePayload)
    assert defects == ["payload lacks ['territory_hint']"], f"the nested check did not fire: {defects}"


def test_the_nested_check_catches_a_payload_field_with_no_draft_origin() -> None:
    """The other direction, which a one-way check would pass."""

    class _PayloadWithAnInventedField(EvidenceFieldProvenancePayload):
        confidence: float = 0.0

    defects = nested_parity_defects(FieldProvenance, _PayloadWithAnInventedField)
    assert defects == ["payload invents ['confidence']"], f"the nested check did not fire: {defects}"


def test_the_nested_check_clears_a_pair_that_agrees() -> None:
    """The precision half: a check that flagged either way would prove nothing."""
    assert not nested_parity_defects(FieldProvenance, EvidenceFieldProvenancePayload)
