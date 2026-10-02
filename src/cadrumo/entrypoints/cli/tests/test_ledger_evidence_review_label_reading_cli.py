"""Real-CLI regression: reviewing a stored draft says why its label reading stood alone.

A draft whose label reading stood without the model fill it asked for keeps that
fact on its stored record, not in the draft payload, so the fields the fill was
to read are empty with nothing in the draft saying why. ``review view`` is the
one-document surface an operator reads before confirming; it must name the
reason in both output modes, and name none for a draft read in full or for one
stored before the fact was kept.

Drafts are seeded through the sanctioned store, as the sibling review tests do.
The earlier-shape draft is written through the real encrypted repository with
the key removed from its stored envelope.

Every assertion is on codes and context tokens, never on prose, which is
localised.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
from ....application.ledger.extraction_draft_store import (
    ExtractionDraftDocument,
    StoredExtractionDraft,
    load_extraction_drafts,
    write_extraction_draft,
)
from ....application.ledger.invoice_draft_records import InvoiceDraft, LabelReadingFallback, LabelReadingFallbackCause
from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.config import load_settings
from .ledger_ux_support import _invoke, open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REFERENCE = "ev-label-reading-001"
_LABEL_READING_CODES = {
    LabelReadingFallbackCause.READER_UNAVAILABLE: "ledger.evidence.label_reading.reader_unavailable",
    LabelReadingFallbackCause.LOAD_HEADROOM_REFUSED: "ledger.evidence.label_reading.headroom_refused",
    LabelReadingFallbackCause.INFERENCE_SLOT_BUSY: "ledger.evidence.label_reading.busy_refused",
}
_REVIEW_VIEW = ["app", "ledger", "evidence", "review", "view", _REFERENCE]

#: What the reader raised for each cause, and the precondition an admission
#: refusal names; an unreachable reader names none.
_REFUSALS: dict[LabelReadingFallbackCause, tuple[str, str | None]] = {
    LabelReadingFallbackCause.READER_UNAVAILABLE: ("InvoiceDraftReaderUnavailableError", None),
    LabelReadingFallbackCause.LOAD_HEADROOM_REFUSED: (
        "InvoiceDraftReaderHeadroomRefusedError",
        ProvisioningPreconditionCondition.LOAD_CAPACITY_AVAILABLE.value,
    ),
    LabelReadingFallbackCause.INFERENCE_SLOT_BUSY: (
        "InvoiceDraftReaderBusyRefusedError",
        "llm.local_inference.slot_available",
    ),
}


def _draft() -> InvoiceDraft:
    """A draft missing exactly the fields the fallbacks below name as unread."""
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        invoice_number="2026-0142",
        invoice_date="2026-03-10",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
    )


def _fallback(cause: LabelReadingFallbackCause) -> LabelReadingFallback:
    """The record the extraction keeps for ``cause``."""
    error_type, condition = _REFUSALS[cause]
    return LabelReadingFallback(
        cause=cause,
        unread_fields=("currency", "supplier_name"),
        reader_error_type=error_type,
        failed_condition_id=condition,
    )


@pytest.fixture
def session(tmp_path: Path) -> Iterator[str]:
    """A live bucket session with no pending draft yet; yields its bucket id."""
    with open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        yield bucket_id


def _store(bucket_id: str, draft: InvoiceDraft) -> None:
    write_extraction_draft(
        bucket_id=bucket_id,
        evidence_reference=_REFERENCE,
        draft=draft,
        extractor="extract_invoice_draft_from_evidence",
        settings=load_settings(),
    )


def _json_notices() -> list[dict[str, object]]:
    result = _invoke(["--format", "json", *_REVIEW_VIEW])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "ledger.evidence.review.show", result.output
    assert isinstance(envelope["notices"], list), result.output
    notices: list[dict[str, object]] = []
    for notice in envelope["notices"]:
        assert isinstance(notice, dict), result.output
        notices.append(notice)
    return notices


def _text_notice_codes() -> list[str]:
    result = _invoke(_REVIEW_VIEW)
    assert result.exit_code == 0, result.output
    return [line.split("\t")[1] for line in result.output.splitlines() if line.startswith("notice\t")]


def _label_reading_codes(codes: list[str]) -> list[str]:
    return [code for code in codes if code.startswith("ledger.evidence.label_reading.")]


@pytest.mark.parametrize("cause", tuple(LabelReadingFallbackCause))
def test_a_stored_degraded_draft_names_its_reason_in_review(session: str, cause: LabelReadingFallbackCause) -> None:
    """The stored record, not the draft, is what review must read, and it reaches both output modes."""
    _store(session, _draft().with_label_reading_fallback(_fallback(cause)))
    (stored,) = load_extraction_drafts(session, load_settings()).drafts
    # Positive control: the fact lives on the stored record and nowhere else,
    # so a review reading the draft alone would show nothing.
    assert stored.label_reading_fallback == _fallback(cause)
    assert stored.draft.label_reading_fallback is None

    notices = [notice for notice in _json_notices() if str(notice["code"]).startswith("ledger.evidence.label_reading.")]
    assert [notice["code"] for notice in notices] == [_LABEL_READING_CODES[cause]]
    (notice,) = notices
    assert notice["severity"] == "warning"
    context = notice["context"]
    assert isinstance(context, dict)
    assert context["reason"] == cause.value
    assert context["unread_fields"] == "currency, supplier_name"
    assert context["reader_error_type"] == _fallback(cause).reader_error_type
    assert context.get("failed_condition_id") == _fallback(cause).failed_condition_id

    assert _label_reading_codes(_text_notice_codes()) == [_LABEL_READING_CODES[cause]]


def test_a_draft_read_in_full_names_no_label_reading_reason_in_review(session: str) -> None:
    """The control: a draft whose fill ran or was not needed is not shown as degraded."""
    _store(session, _draft())

    assert _label_reading_codes([str(notice["code"]) for notice in _json_notices()]) == []
    assert _label_reading_codes(_text_notice_codes()) == []


def test_a_draft_stored_before_the_degradation_was_kept_names_none_in_review(session: str) -> None:
    """A stored row of the earlier shape reviews without inventing a degradation."""
    settings = load_settings()
    repository = ExtractionDraftRepository(bucket_id=session, settings=settings)
    current = ExtractionDraftDocument(
        bucket_id=session,
        drafts=(
            StoredExtractionDraft(
                evidence_reference=_REFERENCE,
                draft=_draft(),
                extractor="extract_invoice_draft_from_evidence",
                drafted_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
                label_reading_fallback=_fallback(LabelReadingFallbackCause.INFERENCE_SLOT_BUSY),
            ),
        ),
    )
    prepared = repository.to_secure_object_write(current)
    envelope = json.loads(prepared.payload)
    # Positive control: the key is really there to remove, so the review below
    # reads the earlier shape rather than an unchanged one.
    assert envelope["payload"]["drafts"][0].pop("label_reading_fallback") is not None
    repository.secure_object_repository.save(
        namespace=prepared.namespace,
        object_key=prepared.object_key,
        classification=prepared.classification,
        schema_version=prepared.schema_version,
        written_at=prepared.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    assert _label_reading_codes([str(notice["code"]) for notice in _json_notices()]) == []
    assert _label_reading_codes(_text_notice_codes()) == []
