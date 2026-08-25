"""Real-CLI proof that a non-blocking advisory is visible from the QUEUE.

Both advisories over a pending draft were reachable only from ``review show``.
An operator who never opens a document never meets one, and these are precisely
the conditions that let a document through --- so "reachable from the detail
view" and "unreachable" are the same thing for any draft nobody had a reason to
open. The queue is where that changes.

The ruling is a count and a filter rather than a row per advisory: the prose
lives on the one-document surface, and repeating it once per affected draft is
how a channel earns the reflex to skip it. So what is asserted here is that the
queue REPORTS the kinds, that the filter SELECTS on them, and that the operator
is told once that some documents carry them.

Every case drives the real Typer tree against a real encrypted bucket and a real
stored draft. Assertions are on codes, counts and structure --- never on prose,
which is localised.

The negative half is the load-bearing one: a filter that returned every row would
pass a test asserting only that the advised row is present. Each case therefore
pins both the row that must appear and the row that must not.

See Also:
    :func:`~application.ledger.review_advisory_kinds`
        The one projection the queue and the notices both read.
    :class:`~core.ReviewAdvisoryKind`
        The closed axis the filter accepts.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ....application.ledger import (
    DocumentTranscription,
    FieldProvenance,
    InvoiceDraft,
    TranscriberIdentity,
    deterministic_findings,
    ground_draft_against_transcription,
    write_extraction_draft,
)
from ....core import LOCAL_TRANSPORT_LABEL, FieldGroundingOutcome, FieldOrigin, ReviewAdvisoryKind
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.config import load_settings
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ATTRIBUTION_REFERENCE: Final = "ev-queue-attribution-001"
_COUNTRY_REFERENCE: Final = "ev-queue-country-001"
_CLEAN_REFERENCE: Final = "ev-queue-clean-001"
_ADVISED_NOTICE: Final = "ledger.evidence.review.advised_pending"

_PAGE: Final = (
    "FACTURA 2026-0142\n"
    "Emisor: Acme Suministros SL\n"
    "NIF B12345674\n"
    "Calle Mayor 3, 28001 Madrid\n"
    "Espana\n"
    "Cliente: Islas Comercial SL\n"
    "NIF B44444444\n"
    "Avenida del Puerto 9, 35001 Las Palmas\n"
    "Espana\n"
    "Base imponible 100,00\n"
)


def _reader_envelope(field: str, anchor: str) -> FieldProvenance:
    return FieldProvenance(
        field=field,
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor=anchor,
    )


def _attribution_draft() -> InvoiceDraft:
    """Return a draft whose address values carry unverified attribution.

    Put through :func:`~application.ledger.ground_draft_against_transcription`,
    the entry point the reading router uses, rather than hand-stamped: a stamp
    asserted on a constructed envelope would prove the field exists and not that
    the reading path produces it.
    """
    draft = InvoiceDraft(
        supplier_tax_id="B12345674",
        supplier_name="Acme Suministros SL",
        supplier_postal_code="28001",
        supplier_country="Espana",
        customer_tax_id="B44444444",
        customer_name="Islas Comercial SL",
        customer_postal_code="35001",
        customer_country="Espana",
        taxable_base=Decimal("100.00"),
        provenance=(
            _reader_envelope("supplier_postal_code", "28001"),
            _reader_envelope("supplier_country", "Espana"),
            _reader_envelope("customer_postal_code", "35001"),
            _reader_envelope("customer_country", "Espana"),
            _reader_envelope("taxable_base", "100,00"),
        ),
    )
    return ground_draft_against_transcription(
        draft=draft,
        transcription=DocumentTranscription(
            text=_PAGE,
            page_count=1,
            source_content_sha256="c" * 64,
            transcriber=TranscriberIdentity(
                origin=FieldOrigin.TEXT_LAYER,
                name="pdf-text-layer-extractor",
                transport=LOCAL_TRANSPORT_LABEL,
                revision="1",
            ),
        ),
    )


def _country_draft() -> InvoiceDraft:
    """Return a draft whose billed party states a code no country holds.

    ``XX`` is one ISO 3166-1 permanently reserves against allocation, so the
    document states a string rather than a country. Stated on both the verbatim
    and the resolved field because the advisory reads the party's country
    evidence, and a fixture pinned to one spelling would stop exercising the
    advisory the moment the reader's field split moved underneath it.
    """
    read = InvoiceDraft(
        supplier_tax_id="B12345674",
        customer_country_code="XX",
        customer_stated_country_code="XX",
        taxable_base=Decimal("100.00"),
    )
    # Stamped through the real check list exactly as a reading path hands a draft
    # on: seeding an empty tuple would make the no-blocker assertion true of the
    # fixture rather than of the product.
    return read.model_copy(update={"discrepancies": deterministic_findings(read)})


def _clean_draft() -> InvoiceDraft:
    """Return a draft carrying nothing advisory: the control every filter needs."""
    read = InvoiceDraft(
        supplier_tax_id="B12345674",
        supplier_name="Acme Suministros SL",
        taxable_base=Decimal("100.00"),
    )
    return read.model_copy(update={"discrepancies": deterministic_findings(read)})


@pytest.fixture
def seeded_queue(tmp_path: Path) -> Iterator[None]:
    """A live bucket carrying one draft per advisory kind plus one carrying none."""
    with _open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        settings = load_settings()
        for reference, draft in (
            (_ATTRIBUTION_REFERENCE, _attribution_draft()),
            (_COUNTRY_REFERENCE, _country_draft()),
            (_CLEAN_REFERENCE, _clean_draft()),
        ):
            write_extraction_draft(
                bucket_id=bucket_id,
                evidence_reference=reference,
                draft=draft,
                extractor="text_layer",
                settings=settings,
            )
        yield


def _listed(*args: str) -> dict[str, object]:
    result = _invoke(["--format", "json", "app", "ledger", "evidence", "review", "list", *args])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    return {str(key): value for key, value in payload.items()}


def _rows(envelope: dict[str, object]) -> dict[str, dict[str, object]]:
    body = envelope["result"]
    assert isinstance(body, dict)
    rows = body["rows"]
    assert isinstance(rows, list)
    return {str(row["evidence_reference"]): row for row in rows if isinstance(row, dict)}


@pytest.mark.usefixtures("seeded_queue")
def test_the_queue_reports_each_row_s_advisory_kinds() -> None:
    """The deliverable: a queue row says what its document carries, not only what stops it."""
    rows = _rows(_listed())

    assert rows[_ATTRIBUTION_REFERENCE]["advisories"] == [ReviewAdvisoryKind.PARTY_ATTRIBUTION.value]
    assert rows[_ATTRIBUTION_REFERENCE]["advisory_count"] == 1
    assert rows[_COUNTRY_REFERENCE]["advisories"] == [ReviewAdvisoryKind.COUNTRY_CODE_UNASSIGNED.value]
    # The control: an unadvised draft reports zero rather than being omitted,
    # so an operator can tell "checked and clean" from "not on the queue".
    assert rows[_CLEAN_REFERENCE]["advisory_count"] == 0
    assert rows[_CLEAN_REFERENCE]["advisories"] == []


@pytest.mark.usefixtures("seeded_queue")
def test_an_advised_document_blocks_nothing_and_is_still_counted() -> None:
    """Advisory and blocking are separate columns, and this is why both exist.

    Read off the queue's own blocking count rather than recomputed, so the case
    cannot pass against a surface that started treating an advisory as a blocker
    to make it visible --- which would be the wrong fix for the same gap.
    """
    rows = _rows(_listed())

    assert rows[_COUNTRY_REFERENCE]["blocking_count"] == 0
    assert rows[_COUNTRY_REFERENCE]["advisory_count"] == 1


@pytest.mark.usefixtures("seeded_queue")
def test_the_advisory_filter_selects_only_the_matching_kind() -> None:
    """A filter that returned everything would pass a presence-only assertion."""
    attribution = _rows(_listed("--advisory", ReviewAdvisoryKind.PARTY_ATTRIBUTION.value))
    country = _rows(_listed("--advisory", ReviewAdvisoryKind.COUNTRY_CODE_UNASSIGNED.value))
    uncatalogued = _rows(_listed("--advisory", ReviewAdvisoryKind.COUNTRY_CODE_UNCATALOGUED.value))

    assert set(attribution) == {_ATTRIBUTION_REFERENCE}
    assert set(country) == {_COUNTRY_REFERENCE}
    # A kind no seeded draft carries narrows to an honest empty queue rather than
    # falling back to every row.
    assert uncatalogued == {}


@pytest.mark.usefixtures("seeded_queue")
def test_the_filter_is_recorded_on_the_payload_so_an_empty_queue_is_legible() -> None:
    """Narrowing to zero must not read as a claim that nothing is pending."""
    body = _listed("--advisory", ReviewAdvisoryKind.COUNTRY_CODE_UNCATALOGUED.value)["result"]

    assert isinstance(body, dict)
    assert body["filters"] == [f"advisory={ReviewAdvisoryKind.COUNTRY_CODE_UNCATALOGUED.value}"]


@pytest.mark.usefixtures("seeded_queue")
def test_the_operator_is_told_once_that_some_documents_carry_advisories() -> None:
    """One notice naming the count and the kinds, not one per affected draft."""
    envelope = _listed()

    notices = envelope["notices"]
    assert isinstance(notices, list)
    matching = [n for n in notices if isinstance(n, dict) and n.get("code") == _ADVISED_NOTICE]
    assert len(matching) == 1, notices
    context = matching[0]["context"]
    assert isinstance(context, dict)
    assert context["advised"] == "2"
    assert context["kinds"] == ",".join(
        sorted({ReviewAdvisoryKind.PARTY_ATTRIBUTION.value, ReviewAdvisoryKind.COUNTRY_CODE_UNASSIGNED.value}),
    )


@pytest.mark.usefixtures("seeded_queue")
def test_the_notice_is_absent_when_the_narrowed_queue_carries_none() -> None:
    """The count is of the rows shown, so a filter that excludes them clears it.

    The negative control for the case above: a notice emitted unconditionally
    would satisfy that assertion just as well.
    """
    envelope = _listed("--advisory", ReviewAdvisoryKind.COUNTRY_CODE_UNCATALOGUED.value)

    notices = envelope["notices"]
    assert isinstance(notices, list)
    assert [n for n in notices if isinstance(n, dict) and n.get("code") == _ADVISED_NOTICE] == []


@pytest.mark.usefixtures("seeded_queue")
def test_the_text_queue_carries_the_same_counts_as_the_json_one() -> None:
    """A terminal operator is told what a JSON consumer is told."""
    result = _invoke(["app", "ledger", "evidence", "review", "list"])

    assert result.exit_code == 0, result.output
    lines = {line.split("\t")[0]: line for line in result.output.splitlines()}
    assert lines[_ATTRIBUTION_REFERENCE].endswith(f"\t1\t{ReviewAdvisoryKind.PARTY_ATTRIBUTION.value}")
    assert lines[_CLEAN_REFERENCE].endswith("\t0\t-")


@pytest.mark.usefixtures("seeded_queue")
def test_no_bespoke_advisory_field_appears_at_the_top_of_the_payload() -> None:
    """The notice channel stayed the only diagnostic channel.

    The per-row kinds are queue data --- what each document carries --- while the
    operator's instruction about them rides `notices`. A top-level advisory bag
    would be the forked contract this checks against.
    """
    body = _listed()["result"]

    assert isinstance(body, dict)
    assert not [key for key in body if "advisor" in key or key in {"next", "suggestion"}]
