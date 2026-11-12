"""The Records screen shows what the page read serves of the selected stored document."""

from __future__ import annotations

from typing import Final
from uuid import UUID

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static

from .....application.ledger.evidence_page_contracts import (
    EVIDENCE_STRUCTURED_FACT_KEYS,
    EVIDENCE_STRUCTURED_LINE_KEYS,
    EVIDENCE_STRUCTURED_TITLE_KEYS,
    EvidencePageMediaType,
    EvidenceStructuredFactV1,
    EvidenceStructuredInvoiceV1,
    EvidenceStructuredLineV1,
    LedgerEvidencePageProjection,
)
from .....application.ledger.evidence_page_errors import LedgerEvidencePageNotFoundError
from .....application.operations.public_scalar import PublicDecimal
from .....core.config import override_settings
from .....core.document_shape import DocumentShape
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from ...components.host import ScreenHostApp
from ...tests.settling import settle, settle_until
from ..evidence import LedgerEvidenceScreen
from ..models import LedgerEvidenceRecordRowV1, LedgerEvidenceRecordStatus
from .test_ledger_ingestion_surfaces import EvidenceDoor, _evidence_screen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EVIDENCE_ID: Final = "8747cbf318cf0adb"
_PROFILE: Final = UUID("5aa00000-0000-4000-8000-0000000000aa")
_DIGEST: Final = "a" * 64
_FACT_KEYS: Final = dict(EVIDENCE_STRUCTURED_FACT_KEYS)
_LINE_KEYS: Final = dict(EVIDENCE_STRUCTURED_LINE_KEYS)
_TITLE_KEY: Final = EVIDENCE_STRUCTURED_TITLE_KEYS[DocumentShape.XML_FACTURAE]


def _record(file_name: str) -> LedgerEvidenceRecordRowV1:
    return LedgerEvidenceRecordRowV1(
        evidence_id=_EVIDENCE_ID,
        media_kind="pdf",
        file_name=file_name,
        supplier=None,
        invoice_number=None,
        created_at="2026-09-16",
        status=LedgerEvidenceRecordStatus.AWAITING,
    )


def _text(key: str, value: str) -> EvidenceStructuredFactV1:
    return EvidenceStructuredFactV1(label_key=key, text=value)


def _structured(
    facts: tuple[EvidenceStructuredFactV1, ...], lines: tuple[EvidenceStructuredLineV1, ...]
) -> LedgerEvidencePageProjection:
    return LedgerEvidencePageProjection(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=_DIGEST,
        media_type=EvidencePageMediaType.XML,
        page=1,
        page_count=1,
        source_sha256=_DIGEST,
        file_name="factura.xml",
        structured_invoice=EvidenceStructuredInvoiceV1(title_key=_TITLE_KEY, facts=facts, lines=lines),
    )


def _drawn() -> LedgerEvidencePageProjection:
    return LedgerEvidencePageProjection(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=_DIGEST,
        media_type=EvidencePageMediaType.PDF,
        page=1,
        page_count=3,
        width=64,
        height=90,
        source_sha256=_DIGEST,
        file_name="invoice_A-0003.pdf",
        image_data_url="data:image/png;base64,AAAA",
    )


async def _select_and_view(screen: LedgerEvidenceScreen, pilot: Pilot[None]) -> None:
    records = screen.query_one("#ledger-evidence-records", DataTable)
    await settle_until(pilot, lambda: bool(records.ordered_rows), "the evidence rows")
    assert screen.query_one("#ledger-evidence-view", Button).disabled
    records.focus()
    records.move_cursor(row=0)
    await pilot.press("enter")
    await settle(pilot)
    assert not screen.query_one("#ledger-evidence-view", Button).disabled
    screen.query_one("#ledger-evidence-view", Button).press()
    await settle(pilot)


def _door(page: LedgerEvidencePageProjection | None = None, error: Exception | None = None) -> EvidenceDoor:
    door = EvidenceDoor()
    door.records.append(_record("factura.xml"))
    door.page_result = page
    door.page_error = error
    return door


@pytest.mark.asyncio
async def test_a_structured_invoice_shows_its_served_facts_and_lines_under_the_served_labels() -> None:
    page = _structured(
        (
            _text(_FACT_KEYS["supplier_name"], "Proveedor Example SL"),
            EvidenceStructuredFactV1(label_key=_FACT_KEYS["grand_total"], number=PublicDecimal(decimal="121.00")),
        ),
        (
            EvidenceStructuredLineV1(
                facts=(
                    _text(_LINE_KEYS["description"], "Monitor display"),
                    EvidenceStructuredFactV1(label_key=_LINE_KEYS["quantity"], number=PublicDecimal(decimal="2")),
                )
            ),
        ),
    )
    door = _door(page)
    screen = _evidence_screen(door, [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            await _select_and_view(screen, pilot)
            shown = str(screen.query_one("#ledger-evidence-page", Static).render())
            refusal = str(screen.query_one("#ledger-refusal", Static).render())
    assert door.paged == [_EVIDENCE_ID]
    lines = shown.splitlines()
    assert lines[0] == tr(_TITLE_KEY, locale="en")
    assert f"{tr(_FACT_KEYS['supplier_name'], locale='en')}: Proveedor Example SL" in lines
    assert f"{tr(_FACT_KEYS['grand_total'], locale='en')}: 121.00" in lines
    line = next(item for item in lines if "Monitor display" in item)
    assert tr(_LINE_KEYS["description"], locale="en") in line
    assert f"{tr(_LINE_KEYS['quantity'], locale='en')}: 2" in line
    assert not refusal


@pytest.mark.asyncio
async def test_a_page_document_shows_the_page_it_was_drawn_from_and_that_it_is_not_drawn_here() -> None:
    door = _door(_drawn())
    screen = _evidence_screen(door, [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            await _select_and_view(screen, pilot)
            shown = str(screen.query_one("#ledger-evidence-page", Static).render())
    assert "invoice_A-0003.pdf" in shown
    assert "application/pdf" in shown
    assert "3" in shown
    assert "base64" not in shown
    assert len(shown.splitlines()) == 2


@pytest.mark.asyncio
async def test_a_refused_read_is_said_in_the_served_refusal_words_and_shows_no_page() -> None:
    refusal = LedgerEvidencePageNotFoundError()
    door = _door(error=refusal)
    screen = _evidence_screen(door, [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            await _select_and_view(screen, pilot)
            said = str(screen.query_one("#ledger-refusal", Static).render())
            shown = str(screen.query_one("#ledger-evidence-page", Static).render())
            expected = resolve_error_message(refusal)
            assert not screen.reading
    assert said == expected
    assert shown == ""


@pytest.mark.asyncio
async def test_a_structured_invoice_that_states_nothing_is_said_to_be_empty() -> None:
    door = _door(_structured((), ()))
    screen = _evidence_screen(door, [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            await _select_and_view(screen, pilot)
            shown = str(screen.query_one("#ledger-evidence-page", Static).render())
    assert shown.splitlines() == [tr(_TITLE_KEY, locale="en"), tr("tui.ledger.evidence.page.empty", locale="en")]
