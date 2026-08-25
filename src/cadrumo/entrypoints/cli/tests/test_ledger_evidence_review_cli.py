"""Real-CLI regression for the human review gate over pending extraction drafts.

Drives the real Typer tree against a real encrypted bucket session. The pending
draft is seeded through the sanctioned store rather than by running an
extraction, deliberately: the review surface is what is under test, and routing
through a reader would make every assertion here depend on a model being
reachable.

Every assertion is on CODES and STRUCTURE -- envelope command, blocker reason
tokens, field names, exit codes -- never on prose, which is localised.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_review_cli.register_evidence_review_commands`
        The registration under test.
    :func:`~application.ledger.confirmation_gate.confirmation_blockers`
        The gate the surface projects.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ....application.ledger.evidence_draft import DraftDiscrepancyFinding, FieldAmbiguityCandidate, FieldProvenance, InvoiceDraft
from ....application.ledger.grounded_reading import verified_provenance
from ....application.ledger.extraction_draft_store import write_extraction_draft
from ....core import LOCAL_TRANSPORT_LABEL, DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.config import load_settings
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLEAN_REFERENCE = "ev-clean-001"
_BLOCKED_REFERENCE = "ev-blocked-001"
_GROUNDED_REFERENCE = "ev-grounded-001"


def _clean_draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        supplier_name="Acme Suministros SL",
        invoice_number="2026-0142",
        invoice_date="2026-03-10",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="100,00",
            ),
        ),
    )


def _blocked_draft() -> InvoiceDraft:
    return _clean_draft().model_copy(
        update={
            "discrepancies": (
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                    detail="nothing on the page distinguishes issuer from recipient",
                ),
            ),
            "provenance": (
                FieldProvenance(
                    field="supplier_tax_id",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=(
                        FieldAmbiguityCandidate(value="ESB12345674", note="header block"),
                        FieldAmbiguityCandidate(value="ESX1234567L", note="footer block"),
                    ),
                ),
            ),
        },
    )


@pytest.fixture
def seeded_queue(tmp_path: Path) -> Iterator[None]:
    """A live bucket session carrying one clean and one blocked pending draft."""
    with _open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        settings = load_settings()
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_CLEAN_REFERENCE,
            draft=_clean_draft(),
            extractor="exact_structured",
            settings=settings,
        )
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_BLOCKED_REFERENCE,
            draft=_blocked_draft(),
            extractor="text_layer",
            settings=settings,
        )
        yield


def _grounded_draft() -> InvoiceDraft:
    """Return a draft whose envelopes the REAL grounding stage produced.

    Hand-set envelopes would carry whatever this file wrote into them, proving
    the row builder passes a field through and nothing about whether the
    producer ever emits it. One field offers a printed form the transcription
    does not carry; the other offers nothing. Both come out with a blank anchor,
    which is precisely why the row needs a second axis to tell them apart.
    """
    draft = InvoiceDraft(
        grand_total=Decimal("4528.32"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="grand_total",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.UNANCHORED,
                anchor="4.528,32",
            ),
            FieldProvenance(
                field="currency",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.UNANCHORED,
            ),
        ),
    )
    transcription = DocumentTranscription(
        text="FACTURA 2026-0142\nTOTAL 121,00 EUR\n",
        page_count=1,
        source_content_sha256="d" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="test-text-layer",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )
    return draft.model_copy(
        update={"provenance": verified_provenance(draft=draft, transcription=transcription)},
    )


@pytest.fixture
def grounded_queue(tmp_path: Path) -> Iterator[None]:
    """A live bucket session carrying one pending draft with grounded provenance.

    Separate from the queue above rather than a third member of it, so the
    listing assertions there keep naming an exact pair.
    """
    with _open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_GROUNDED_REFERENCE,
            draft=_grounded_draft(),
            extractor="text_layer",
            settings=load_settings(),
        )
        yield


def _json_result(args: list[str]) -> dict[str, object]:
    result = _invoke(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict), result.output
    body = payload.get("result", payload)
    assert isinstance(body, dict), result.output
    return {str(key): value for key, value in body.items()}


def _objects(payload: Mapping[str, object], key: str) -> list[dict[str, object]]:
    """Return a decoded payload's list-of-objects member, asserting its shape.

    A JSON envelope decodes to ``dict[str, object]``, so every member reads as
    ``object`` and the comprehensions below iterated values nothing had
    established were iterable. Narrowed once here, and a payload that stops
    carrying a list says so by name rather than failing mid-comprehension.
    """
    value = payload[key]
    assert isinstance(value, list), f"{key} decoded to {type(value).__name__}, not a list"
    rows: list[dict[str, object]] = []
    for entry in value:
        assert isinstance(entry, dict), f"a {key} member decoded to {type(entry).__name__}, not an object"
        rows.append(entry)
    return rows


def test_review_list_reports_both_pending_drafts_with_their_blocking_reasons(seeded_queue: None) -> None:
    """The queue names what is pending and, per row, why it cannot be confirmed."""
    body = _json_result(["app", "ledger", "evidence", "review", "list"])

    rows = {row["evidence_reference"]: row for row in _objects(body, "rows")}
    assert set(rows) == {_CLEAN_REFERENCE, _BLOCKED_REFERENCE}
    assert rows[_CLEAN_REFERENCE]["blocking_count"] == 0
    assert rows[_CLEAN_REFERENCE]["reasons"] == []
    blocked_reasons = rows[_BLOCKED_REFERENCE]["reasons"]
    assert isinstance(blocked_reasons, list)
    assert set(blocked_reasons) == {"unresolved_direction", "ambiguous_identity"}


def test_review_list_filters_narrow_the_queue(seeded_queue: None) -> None:
    """Each filter narrows to the intended row, and the clean row is the control.

    Without the clean row present, a filter that returned everything would look
    identical to one that filtered correctly.
    """
    blocking = _json_result(["app", "ledger", "evidence", "review", "list", "--blocking"])
    assert [row["evidence_reference"] for row in _objects(blocking, "rows")] == [_BLOCKED_REFERENCE]

    by_reason = _json_result(
        ["app", "ledger", "evidence", "review", "list", "--reason", "ambiguous_identity"],
    )
    assert [row["evidence_reference"] for row in _objects(by_reason, "rows")] == [_BLOCKED_REFERENCE]

    by_finding = _json_result(
        ["app", "ledger", "evidence", "review", "list", "--finding", "role_unresolved"],
    )
    assert [row["evidence_reference"] for row in _objects(by_finding, "rows")] == [_BLOCKED_REFERENCE]

    unmatched = _json_result(
        ["app", "ledger", "evidence", "review", "list", "--finding", "arithmetic_closure"],
    )
    assert unmatched["rows"] == []


def test_review_show_carries_value_origin_anchor_grounding_and_candidates(seeded_queue: None) -> None:
    """Every axis the review gate requires reaches the operator, per field.

    A surface showing only values would make an exactly-parsed structured figure
    and an ambiguous text-layer reading look identical at exactly the moment a
    person decides whether to accept them.
    """
    body = _json_result(["app", "ledger", "evidence", "review", "show", _BLOCKED_REFERENCE])

    fields = {row["field"]: row for row in _objects(body, "fields")}
    identity = fields["supplier_tax_id"]
    assert identity["origin"] == "text_layer"
    assert identity["grounding"] == "ambiguous"
    # A candidate value is a tax identity, so it reaches the operator as a
    # digest and not as itself. What must survive is the ability to ADJUDICATE:
    # the two readings have to stay distinguishable, and once both values are
    # hashed the note describing where each was printed is what distinguishes
    # them. Asserting the raw identifiers here would be asserting a leak.
    candidates = _objects(identity, "candidates")
    values = [candidate["value"] for candidate in candidates]
    assert all(str(value).startswith("sha256:") for value in values), values
    assert len(set(values)) == len(values), f"two distinct bearers collapsed onto one digest: {values}"
    assert [candidate["note"] for candidate in candidates] == ["header block", "footer block"]
    # A field with no envelope is still surfaced, with its axes null rather than
    # dropped: an absent reading is the field an operator most needs to see.
    assert "grand_total" in fields
    assert fields["grand_total"]["origin"] is None

    assert [finding["kind"] for finding in _objects(body, "discrepancies")] == ["role_unresolved"]
    reasons = {blocker["reason"] for blocker in _objects(body, "blockers")}
    assert reasons == {"unresolved_direction", "ambiguous_identity"}
    assert all(len(str(blocker["blocker_id"])) == 16 for blocker in _objects(body, "blockers"))


def test_review_show_of_a_clean_draft_reports_no_blockers(seeded_queue: None) -> None:
    """Positive control: the surface does not manufacture a blocker for every draft."""
    body = _json_result(["app", "ledger", "evidence", "review", "show", _CLEAN_REFERENCE])

    assert body["blockers"] == []
    assert body["discrepancies"] == []


def test_review_show_of_an_unknown_reference_refuses(seeded_queue: None) -> None:
    """A reference with no pending draft refuses rather than showing an empty document."""
    result = _invoke(["app", "ledger", "evidence", "review", "show", "ev-does-not-exist"])

    assert result.exit_code != 0, result.output


def test_review_show_tells_a_refused_anchor_from_one_never_offered(grounded_queue: None) -> None:
    """The distinction the envelope records must survive to the row that shows it.

    Both fields reach this surface with a blank ``anchor``, because the grounding
    stage clears a form it could not locate. What separates them is whether the
    reader offered anything at all -- a reader limitation against a possible
    misread or the wrong document -- and this row is where an operator reads a
    field's grounding, so the two arriving identical here is the whole defect.

    Driven through the real CLI over a draft the REAL grounding stage produced.
    A row built by hand would carry whatever the test put in it and would pass
    while the row builder still dropped the field, which is exactly the gap this
    campaign keeps falling into.
    """
    body = _json_result(["app", "ledger", "evidence", "review", "show", _GROUNDED_REFERENCE])

    fields = {row["field"]: row for row in _objects(body, "fields")}
    # Positive control: the surface really emitted both rows, so neither
    # assertion below can pass over an absent field.
    assert {"grand_total", "currency"} <= set(fields), (
        f"rows reached the operator: {sorted(str(field) for field in fields)}"
    )

    refused = fields["grand_total"]
    assert refused["anchor"] is None, "a form the document does not carry must not read as evidence"
    assert refused["refused_anchor"] == "4.528,32"

    absent = fields["currency"]
    assert absent["anchor"] is None
    assert absent["refused_anchor"] is None, "nothing was offered, so nothing was refused"

    assert refused["refused_anchor"] != absent["refused_anchor"]


def test_the_confirm_verb_offers_no_bulk_resolution_flag() -> None:
    """No ``--confirm-all``, ``--force`` or ``--accept-all`` on the confirm surface.

    Asserted against the rendered option set rather than against module source
    text: the operator's escape hatch would be a CLI OPTION, and a source scan
    would also match a comment or a docstring that merely mentions one.
    """
    result = _invoke(["app", "ledger", "evidence", "confirm", "--help"])

    assert result.exit_code == 0, result.output
    rendered = result.output.replace("\n", " ")
    for forbidden in ("--confirm-all", "--force", "--accept-all", "--resolve-all", "--yes"):
        assert forbidden not in rendered, f"{forbidden} re-creates the rubber stamp the gate removes"
    assert "--resolve" in rendered
