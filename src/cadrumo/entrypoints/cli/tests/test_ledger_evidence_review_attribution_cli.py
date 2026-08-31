"""Real-CLI proof that an unattributed draft reaches the operator carrying the advisory.

The load-bearing assertion of the whole attribution stamp. A field on a
provenance envelope that nothing surfaces is the same shape as evidence no
resolver consumes -- the artefact carries a value nobody reads, and the gap
reads as closed while it is open. So this drives the real Typer tree against a
real encrypted bucket and asserts the notice arrives on the envelope.

The seeded draft is put through
:func:`~application.ledger.grounded_reading.ground_draft_against_transcription`, the entry point
the reading router uses, rather than hand-stamped: a stamp asserted on a
constructed envelope would prove the field exists and not the point.

Assertions are on CODES and STRUCTURE -- the notice code, the envelope status,
the context keys and their territory tokens -- never on prose, which is
localised.

See Also:
    :func:`~application.ledger.party_attribution.party_attribution_advisory`
        The domain advisory the notice projects.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ....application.ledger.extraction_draft_store import write_extraction_draft
from ....application.ledger.grounded_reading import ground_draft_against_transcription
from ....application.ledger.invoice_draft_records import FieldProvenance, InvoiceDraft
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.config import load_settings
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REFERENCE: Final = "ev-attribution-001"
_NOTICE_CODE: Final = "ledger.evidence.review.party_attribution_unverified"

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


def _grounded_draft() -> InvoiceDraft:
    """Return the draft the reading path produces for the page above."""
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


@pytest.fixture
def seeded_draft(tmp_path: Path) -> Iterator[None]:
    """A live bucket session carrying one pending draft of unverified attribution."""
    with _open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_REFERENCE,
            draft=_grounded_draft(),
            extractor="text_layer",
            settings=load_settings(),
        )
        yield


def _envelope() -> dict[str, object]:
    result = _invoke(["--format", "json", "app", "ledger", "evidence", "review", "view", _REFERENCE])
    assert result.exit_code == 0, result.output
    return STR_KEYED_MAPPING_ADAPTER.validate_json(result.output)


def _attribution_notice(envelope: dict[str, object]) -> dict[str, object]:
    notices = envelope.get("notices")
    assert isinstance(notices, list)
    matching = [notice for notice in notices if isinstance(notice, dict) and notice.get("code") == _NOTICE_CODE]
    assert len(matching) == 1, notices
    return STR_KEYED_MAPPING_ADAPTER.validate_python(matching[0])


@pytest.mark.usefixtures("seeded_draft")
def test_the_advisory_reaches_the_operator_on_the_review_envelope() -> None:
    """`review view` carries the attribution advisory as a typed warning notice."""
    envelope = _envelope()

    notice = _attribution_notice(envelope)
    assert notice["severity"] == "warning"
    assert envelope["status"] == "warning"
    assert isinstance(notice["message"], str)
    assert notice["message"].strip()


@pytest.mark.usefixtures("seeded_draft")
def test_the_advisory_names_the_territory_each_party_would_be_placed_in() -> None:
    """The operator is handed the contestable claim, per party, from the domain."""
    context = _attribution_notice(_envelope())["context"]

    assert isinstance(context, dict)
    assert context["supplier_territory_if_attributed"] == "es_mainland"
    assert context["customer_territory_if_attributed"] == "es_canarias"


@pytest.mark.usefixtures("seeded_draft")
def test_the_advisory_names_the_fields_whose_attribution_is_unchecked() -> None:
    """Per-field, so an operator knows which values to check rather than 'the address'."""
    context = _attribution_notice(_envelope())["context"]

    assert isinstance(context, dict)
    assert set(str(context["fields"]).split(",")) == {
        "supplier_postal_code",
        "supplier_country",
        "customer_postal_code",
        "customer_country",
    }
    assert set(str(context["supplier_fields"]).split(",")) == {
        "supplier_postal_code",
        "supplier_country",
    }


@pytest.mark.usefixtures("seeded_draft")
def test_the_text_surface_carries_the_same_advisory_as_the_json_one() -> None:
    """A terminal operator is told what a JSON consumer is told."""
    result = _invoke(["app", "ledger", "evidence", "review", "view", _REFERENCE])

    assert result.exit_code == 0, result.output
    assert _NOTICE_CODE in result.output
    assert "attribution_unverified\tsupplier" in result.output
    assert "es_canarias" in result.output


@pytest.mark.usefixtures("seeded_draft")
def test_the_review_payload_still_never_carries_a_territory() -> None:
    """The advisory did not smuggle the regulatory boundary onto the review surface.

    The review payload deliberately prints each party's postal code and country
    verbatim and never the territory read off them. Routing the advisory through
    the notice channel is what preserves that; this asserts it stayed preserved.
    """
    body = _envelope()["result"]

    assert isinstance(body, dict)
    assert "territory" not in json.dumps(body)
    assert "es_canarias" not in json.dumps(body)
