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

from ....entrypoints.cli._ledger_business_payloads import EvidenceExtractResult
from .._evidence_draft import InvoiceDraft
from .test_evidence_draft_provenance import _fully_populated_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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
