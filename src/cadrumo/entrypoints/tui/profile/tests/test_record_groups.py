"""The record-group screen draws the stream the real record-group resolver builds, page by page.

The profile rows and ledger rows are synthetic; the stream, the page model, its
digests and the refusal words are the backend's own, so the screen is checked
against what the read actually serves. Only the runtime transport is replaced.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from textual.app import App
from textual.widgets import Button, Static

from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....application.user_profile.record_group_contracts import (
    ProfileRecordGroupItem,
    ProfileRecordGroupKind,
    ProfileRecordGroupsRefusalCode,
    ProfileRecordGroupsResult,
    ProfileRecordGroupStreamItem,
    ProfileRecordLedgerRowItem,
)
from .....application.user_profile.record_group_words import refusal_words
from .....application.user_profile.record_groups import ledger_rows_digest, record_group_items
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.models import Transaction
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...tests.settling import settle, settle_until
from ..overview import ProfileManagerScreen
from ..record_groups import MalformedRecordGroupPageError, RecordGroupsPin, RecordGroupStream
from ..record_groups_panel import RecordGroupsScreen, block_lines, ledger_row_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PROFILE = uuid4()
_DIGEST = "a" * 64


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Resolve the stream under one pinned authority generation, as the read does."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _path_values() -> dict[str, str]:
    """A principal property, an accessory let with it, a lease of each, all synthetic."""
    return {
        f"{INMUEBLE_SECTION}.0.direccion": "Calle Sintetica 1",
        f"{INMUEBLE_SECTION}.1.direccion": "Calle Sintetica 1, trastero",
        f"{INMUEBLE_SECTION}.1.inmueble_principal": "0",
        f"{ARRENDAMIENTO_SECTION}.0.inmueble": "0",
        f"{ARRENDAMIENTO_SECTION}.0.fecha_inicio": f"{_YEAR}-01-01",
        f"{ARRENDAMIENTO_SECTION}.1.inmueble": "1",
        f"{ARRENDAMIENTO_SECTION}.1.fecha_inicio": f"{_YEAR}-02-01",
        f"{ARRENDAMIENTO_SECTION}.1.fecha_fin": f"{_YEAR}-11-30",
    }


def _ledger_row(provider_id: str, day: int, *, links: dict[str, str]) -> Transaction:
    booked = date(_YEAR, 3, day)
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=booked,
                value_date=booked,
                amount=Decimal("120.00"),
                currency="EUR",
                counterparty="Synthetic counterparty",
                description=f"Synthetic row {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=day,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(_YEAR, 4, 1, 9, 30, tzinfo=UTC),
                    provider_name="Synthetic provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            **links,
        },
    )


def _stream(operation: PinnedAuthorityOperation) -> tuple[ProfileRecordGroupStreamItem, ...]:
    return record_group_items(
        _path_values(),
        schema=operation.profile_decode_context().schema,
        kind=ProfileRecordGroupKind.RENTAL_PROPERTY,
        ledger_rows=(
            _ledger_row("row-a", 3, links={"inmueble_ref": "0", "gasto_capital_inmobiliario": "comunidad"}),
            _ledger_row("row-b", 5, links={"arrendamiento_ref": "1"}),
        ),
        language=OutputLanguage.EN,
    )


def _page(stream: tuple[ProfileRecordGroupStreamItem, ...], cursor: int, size: int) -> ProfileRecordGroupsResult:
    """The page the read serves at ``cursor``, built through the read's own page model and digest."""
    end = min(cursor + size, len(stream))
    return ProfileRecordGroupsResult.model_validate(
        {
            "profile_id": _PROFILE,
            "group_kind": ProfileRecordGroupKind.RENTAL_PROPERTY,
            "outcome": "page",
            "record_revision": 3,
            "content_digest": _DIGEST,
            "ledger_digest": ledger_rows_digest(stream),
            "cursor": cursor,
            "total_items": len(stream),
            "items": stream[cursor:end],
            "next_cursor": end if end < len(stream) else None,
        }
    )


def _empty(kind: ProfileRecordGroupKind) -> ProfileRecordGroupsResult:
    return ProfileRecordGroupsResult.model_validate(
        {
            "profile_id": _PROFILE,
            "group_kind": kind,
            "outcome": "page",
            "record_revision": 3,
            "content_digest": _DIGEST,
            "ledger_digest": ledger_rows_digest(()),
            "cursor": 0,
            "total_items": 0,
        }
    )


def _refused() -> ProfileRecordGroupsResult:
    return ProfileRecordGroupsResult.model_validate(
        {
            "profile_id": _PROFILE,
            "group_kind": ProfileRecordGroupKind.RENTAL_PROPERTY,
            "outcome": "refused",
            "refusal_code": ProfileRecordGroupsRefusalCode.STALE_REVISION,
            "refusal_words": refusal_words(ProfileRecordGroupsRefusalCode.STALE_REVISION),
            "refusal_words_language": OutputLanguage.EN,
            "record_revision": 4,
            "content_digest": _DIGEST,
            "ledger_digest": _DIGEST,
            "cursor": 3,
            "total_items": 0,
        }
    )


def test_pages_collect_into_groups_with_members_under_the_row_they_name(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    stream_items = _stream(authority_operation)
    stream = RecordGroupStream(ProfileRecordGroupKind.RENTAL_PROPERTY)
    cursor: int | None = 0
    while cursor is not None:
        stream.accept(_page(stream_items, cursor, 2))
        cursor = stream.next_cursor
    assert len(stream.blocks) == 1
    block = stream.blocks[0]
    assert block.group.group_key == f"{INMUEBLE_SECTION}.0"
    depths = {member.item.row_ref: member.depth for member in block.members}
    assert depths == {
        f"{INMUEBLE_SECTION}.1": 1,
        f"{ARRENDAMIENTO_SECTION}.0": 1,
        f"{ARRENDAMIENTO_SECTION}.1": 2,
    }
    assert [row.transaction_id for row in block.ledger_rows] == [
        item.transaction_id for item in stream_items if isinstance(item, ProfileRecordLedgerRowItem)
    ]
    assert stream.pin == RecordGroupsPin(3, _DIGEST, ledger_rows_digest(stream_items))


def test_a_page_that_skips_items_is_refused(authority_operation: PinnedAuthorityOperation) -> None:
    stream_items = _stream(authority_operation)
    stream = RecordGroupStream(ProfileRecordGroupKind.RENTAL_PROPERTY)
    stream.accept(_page(stream_items, 0, 2))
    with pytest.raises(MalformedRecordGroupPageError):
        stream.accept(_page(stream_items, 3, 2))


def test_a_group_is_drawn_in_served_words_only(authority_operation: PinnedAuthorityOperation) -> None:
    stream_items = _stream(authority_operation)
    stream = RecordGroupStream(ProfileRecordGroupKind.RENTAL_PROPERTY)
    stream.accept(_page(stream_items, 0, len(stream_items)))
    texts = [text for _css, text in block_lines(stream.blocks[0])]
    group = stream.blocks[0].group
    assert texts[0] == f"{group.kind_words} · {group.summary_words}"
    for member in stream.blocks[0].members:
        assert any(text.strip() == f"{member.item.kind_words} · {member.item.summary_words}" for text in texts)
        assert any(text.strip() == member.item.relation_words for text in texts)
    concept_row = next(row for row in stream.blocks[0].ledger_rows if row.concept is not None)
    assert concept_row.concept_words is not None
    assert ledger_row_text(concept_row).endswith(f" · {concept_row.concept_words}")


class _Port:
    """The runtime's read replaced by the pages the real resolver builds; every call is recorded."""

    def __init__(
        self, stream: tuple[ProfileRecordGroupStreamItem, ...], *, size: int, refuse_after: int | None
    ) -> None:
        self._stream = stream
        self._size = size
        self._refuse_after = refuse_after
        self.calls: list[tuple[ProfileRecordGroupKind, int, RecordGroupsPin | None]] = []

    async def read(
        self, group_kind: ProfileRecordGroupKind, *, cursor: int, pin: RecordGroupsPin | None
    ) -> ProfileRecordGroupsResult:
        self.calls.append((group_kind, cursor, pin))
        if group_kind is not ProfileRecordGroupKind.RENTAL_PROPERTY:
            return _empty(group_kind)
        if self._refuse_after is not None and cursor >= self._refuse_after:
            return _refused()
        return _page(self._stream, cursor, self._size)


class _Host(App[None]):
    def __init__(self, port: _Port) -> None:
        super().__init__()
        self.port = port

    def on_mount(self) -> None:
        self.push_screen(RecordGroupsScreen(self.port))


def _continues(more: Button) -> bool:
    """Whether the next-page control is offered; read afresh after each page."""
    return bool(more.display)


def _texts(app: App[None]) -> list[str]:
    return [str(widget.render()) for widget in app.screen.query(Static) if not isinstance(widget, Button)]


@pytest.mark.asyncio
async def test_the_screen_reads_every_kind_and_continues_at_the_first_page_pin(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    stream_items = _stream(authority_operation)
    port = _Port(stream_items, size=3, refuse_after=None)
    app = _Host(port)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert [kind for kind, _cursor, _pin in port.calls] == list(ProfileRecordGroupKind)
        assert all(pin is None for _kind, _cursor, pin in port.calls)
        more = app.screen.query_one("#record-groups-more", Button)
        summary = stream_items[0]
        assert isinstance(summary, ProfileRecordGroupItem)
        assert any(summary.summary_words in text for text in _texts(app))
        pages = 1
        while _continues(more):
            more.press()
            await settle(pilot)
            pages += 1
        assert pages > 1
        continuations = [call for call in port.calls if call[1] > 0]
        assert continuations
        assert all(
            pin == RecordGroupsPin(3, _DIGEST, ledger_rows_digest(stream_items)) for *_rest, pin in continuations
        )
        texts = _texts(app)
        for item in stream_items:
            if isinstance(item, ProfileRecordLedgerRowItem):
                assert any(text.strip() == ledger_row_text(item) for text in texts)


@pytest.mark.asyncio
async def test_a_refused_continuation_shows_the_served_words(authority_operation: PinnedAuthorityOperation) -> None:
    port = _Port(_stream(authority_operation), size=3, refuse_after=3)
    app = _Host(port)
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.click("#record-groups-more")
        await settle(pilot)
        status = str(app.screen.query_one("#record-groups-status", Static).render())
        assert status == refusal_words(ProfileRecordGroupsRefusalCode.STALE_REVISION)
        assert not app.screen.query_one("#record-groups-more", Button).display
        port.calls.clear()
        app.screen.query_one("#record-groups-read", Button).press()
        await settle(pilot)
        assert port.calls == [(kind, 0, None) for kind in ProfileRecordGroupKind]


@pytest.mark.asyncio
async def test_a_profile_without_groups_says_so() -> None:
    port = _Port((), size=3, refuse_after=None)
    app = _Host(port)
    async with app.run_test() as pilot:
        await settle(pilot)
        status = str(app.screen.query_one("#record-groups-status", Static).render())
        assert status == tr("tui.profile.record_groups.empty")
        assert not app.screen.query_one("#record-groups-more", Button).display


def _section(key: str, *, references: str | None) -> ProfileSectionView:
    return ProfileSectionView(
        key=key,
        title=f"Synthetic {key}",
        summary="",
        repeatable=False,
        fields=(
            ProfileFieldView(
                path=f"{key}.fact",
                label="Synthetic fact",
                value="",
                masked=False,
                required=False,
                references_section=references,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_the_profile_page_opens_the_groups_from_the_section_another_field_names(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    overview = ProfileOverview(
        profile_id=str(_PROFILE),
        record_revision=3,
        content_digest=_DIGEST,
        label="Synthetic profile",
        setup_state=ProfileSetupState.COMPLETE,
        sections=(
            _section("synthetic_head", references=None),
            _section("synthetic_member", references="synthetic_head"),
        ),
    )

    def unreachable(_path: str, _value: str, _revision: int, _digest: str) -> ProfileOverview:
        raise AssertionError("the groups are read only")

    port = _Port(_stream(authority_operation), size=3, refuse_after=None)
    manager = ProfileManagerScreen(overview, persist=unreachable, record_groups=port)
    async with ScreenHostApp(manager).run_test(size=(140, 50)) as pilot:
        await settle(pilot)
        assert not manager.query("#manager-record-groups-synthetic_member")
        manager.query_one("#manager-record-groups-synthetic_head", Button).press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, RecordGroupsScreen), "the groups opened")
        await settle_until(pilot, lambda: bool(port.calls), "the groups read")
