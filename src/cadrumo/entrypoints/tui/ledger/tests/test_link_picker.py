"""The link pickers offer what the real entry-options read serves and yield the served value chosen.

The profile rows are synthetic; the options, their words and the request the
chosen values go into are the backend's own. Only the runtime transport is
replaced, by a door that returns the real read's projection.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import override
from uuid import uuid4

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Select, Static

from .....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from .....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from .....application.ledger.classify_requests import LedgerClassifyPatch
from .....application.ledger.entry_options_operation import LedgerEntryOptionsProjection, ledger_entry_options
from .....application.ledger.ledger_add_contracts import LedgerAddRequest
from .....application.ledger.manual_read import ledger_transaction_payload
from .....application.ledger.transaction_projection import LedgerTransactionProjection
from .....application.ledger.update_contracts import LedgerUpdatePatch, LedgerUpdatePatchField
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from .....domain.transactions.tests.rental_link_rows import rental_row
from ...components.host import ScreenHostApp
from ...tests.settling import settle
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController
from ..link_picker import (
    LINK_FAMILY_BY_FIELD,
    LedgerHeldLinksDoorV1,
    LedgerLinkPicker,
    LedgerLinkPickers,
    held_links,
    option_words,
)
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import ledger_focused_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PROFILE = uuid4()


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Read the options under one pinned authority generation, as the read does."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _options(operation: PinnedAuthorityOperation, *, rows: bool) -> LedgerEntryOptionsProjection:
    facts = (
        {
            f"{INMUEBLE_SECTION}.0.direccion": "Calle Sintetica 1",
            f"{ARRENDAMIENTO_SECTION}.0.inmueble": "0",
            f"{ARRENDAMIENTO_SECTION}.0.fecha_inicio": f"{_YEAR}-01-01",
        }
        if rows
        else None
    )
    return ledger_entry_options(_PROFILE, operation=operation, language=OutputLanguage.EN, profile_facts=facts)


class _Door:
    def __init__(self, options: LedgerEntryOptionsProjection | None) -> None:
        self._options = options

    async def __call__(self) -> LedgerEntryOptionsProjection:
        if self._options is None:
            raise ConnectionError("the read could not be completed")
        return self._options


class _Host(App[None]):
    def __init__(self, door: _Door, initial: dict[str, str] | None = None) -> None:
        super().__init__()
        self._door = door
        self._initial = initial

    @override
    def compose(self) -> ComposeResult:
        yield LedgerLinkPickers("fixture", self._door, initial=self._initial, id="links")


def _served(options: LedgerEntryOptionsProjection, field: str) -> list[tuple[str, str]]:
    family = next(family for family in options.families if family.family == LINK_FAMILY_BY_FIELD[field])
    return [(option_words(option), option.value) for option in family.options]


def _picker(app: App[None], field: str) -> LedgerLinkPicker:
    return next(picker for picker in app.query(LedgerLinkPicker) if picker.field == field)


@pytest.mark.asyncio
async def test_each_link_field_offers_its_served_family_in_served_words(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)
    app = _Host(_Door(options))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert [picker.field for picker in app.query(LedgerLinkPicker)] == list(LINK_FAMILY_BY_FIELD)
        for field in LINK_FAMILY_BY_FIELD:
            picker = _picker(app, field)
            served = _served(options, field)
            assert served
            for words, value in served:
                # A value the picker does not offer is refused by the select itself.
                picker.query_one(Select).value = value
                await settle(pilot)
                assert picker.chosen_words == words
            picker.query_one(Select).clear()
        rows = next(family for family in options.families if family.family == "rental_lease").options
        assert [option_words(option) for option in rows] == [option.label_words for option in rows]
        assert all(option.label_words != option.value for option in rows)
        links = app.query_one("#links", LedgerLinkPickers)
        assert links.chosen() == {}


@pytest.mark.asyncio
async def test_the_chosen_served_values_are_what_the_ledger_requests_take(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)
    app = _Host(_Door(options))
    async with app.run_test() as pilot:
        await settle(pilot)
        chosen: dict[str, str] = {}
        for field in ("arrendamiento_ref", "gasto_capital_inmobiliario"):
            _words, value = _served(options, field)[0]
            _picker(app, field).query_one(Select).value = value
            chosen[field] = value
        await settle(pilot)
        links = app.query_one("#links", LedgerLinkPickers)
        assert links.chosen() == chosen
        assert len(links.chosen_lines()) == 2
        assert all(line.split(": ", 1)[1] for line in links.chosen_lines())
        patch = LedgerClassifyPatch.model_validate(chosen)
        assert patch.arrendamiento_ref == chosen["arrendamiento_ref"]
        request = LedgerAddRequest.model_validate(
            {
                "profile_id": _PROFILE,
                "booked_date": f"{_YEAR}-03-01",
                "amount": "10.00",
                "direction": "OUTGOING",
                "description": "Synthetic row",
                **chosen,
            }
        )
        assert request.gasto_capital_inmobiliario == chosen["gasto_capital_inmobiliario"]


@pytest.mark.asyncio
async def test_a_profile_without_rental_rows_offers_no_row_and_says_so(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    app = _Host(_Door(_options(authority_operation, rows=False)))
    async with app.run_test() as pilot:
        await settle(pilot)
        for field in ("arrendamiento_ref", "inmueble_ref"):
            picker = _picker(app, field)
            assert picker.query_one(Select).disabled
            notes = [str(note.render()) for note in picker.query(".ledger-link-note").results(Static)]
            assert notes == [tr("tui.ledger.link_picker.none_served")]
        assert not _picker(app, "gasto_capital_inmobiliario").query_one(Select).disabled


@pytest.mark.asyncio
async def test_a_value_chosen_before_is_kept_only_while_it_is_offered(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)
    lease = _served(options, "arrendamiento_ref")[0][1]
    app = _Host(_Door(options), initial={"arrendamiento_ref": lease, "inmueble_ref": "not-offered"})
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.query_one("#links", LedgerLinkPickers).chosen() == {"arrendamiento_ref": lease}


@pytest.mark.asyncio
async def test_a_failed_read_offers_no_picker_and_says_so() -> None:
    app = _Host(_Door(None))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert not app.query(LedgerLinkPicker)
        notes = [str(note.render()) for note in app.query(".ledger-link-note").results(Static)]
        assert notes == [tr("tui.ledger.link_picker.unavailable")]


def _held_by(row_fields: dict[str, str]) -> dict[str, str]:
    """The links a real ledger row with ``row_fields`` serves, read the way the transaction door serves them."""
    projection = LedgerTransactionProjection.from_payload(ledger_transaction_payload(rental_row(**row_fields)))
    return held_links(projection)


class _HeldHost(App[None]):
    def __init__(self, door: _Door, held: LedgerHeldLinksDoorV1, initial: dict[str, str] | None = None) -> None:
        super().__init__()
        self._door = door
        self._held = held
        self._initial = initial

    @override
    def compose(self) -> ComposeResult:
        yield LedgerLinkPickers("fixture", self._door, initial=self._initial, held=self._held, id="links")


@pytest.mark.asyncio
async def test_a_picker_for_a_linked_row_starts_at_the_link_the_row_holds_in_its_served_words(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)
    prop = _served(options, "inmueble_ref")[0][1]
    concept = _served(options, "gasto_capital_inmobiliario")[0][1]
    held = _held_by({"inmueble_ref": prop, "gasto_capital_inmobiliario": concept})
    assert held == {"inmueble_ref": prop, "gasto_capital_inmobiliario": concept}

    async def read() -> dict[str, str]:
        return held

    app = _HeldHost(_Door(options), read)
    async with app.run_test() as pilot:
        await settle(pilot)
        links = app.query_one("#links", LedgerLinkPickers)
        assert links.chosen() == held
        for field, value in held.items():
            served_words = next(words for words, served_value in _served(options, field) if served_value == value)
            assert _picker(app, field).chosen_words == served_words
        assert _picker(app, "arrendamiento_ref").value is None


@pytest.mark.asyncio
async def test_what_the_operator_chose_before_wins_over_what_the_row_holds(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)
    concepts = _served(options, "gasto_capital_inmobiliario")
    held_value, chosen_value = concepts[0][1], concepts[1][1]

    async def read() -> dict[str, str]:
        return {"gasto_capital_inmobiliario": held_value}

    app = _HeldHost(_Door(options), read, initial={"gasto_capital_inmobiliario": chosen_value})
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.query_one("#links", LedgerLinkPickers).chosen() == {"gasto_capital_inmobiliario": chosen_value}


@pytest.mark.asyncio
async def test_a_failed_read_of_the_held_links_starts_every_picker_unchosen_and_says_so(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)

    async def read() -> dict[str, str]:
        raise ConnectionError("the read could not be completed")

    app = _HeldHost(_Door(options), read)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.query_one("#links", LedgerLinkPickers).chosen() == {}
        assert len(list(app.query(LedgerLinkPicker))) == len(LINK_FAMILY_BY_FIELD)
        notes = [str(note.render()) for note in app.query(".ledger-link-note").results(Static)]
        assert tr("tui.ledger.link_picker.held_unavailable") in notes


class _Records:
    """The runtime's transaction read replaced by the real projection of a real ledger row."""

    def __init__(self, projection: LedgerTransactionProjection) -> None:
        self._projection = projection
        self.asked: list[str] = []

    async def invoices(self) -> tuple[CatalogueInvoiceSnapshot, ...]:
        raise AssertionError("classification reads no invoice")

    async def invoice(self, invoice_id: str) -> CatalogueInvoiceSnapshot:
        raise AssertionError("classification reads no invoice")

    async def update_invoice(
        self, baseline: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch
    ) -> CatalogueInvoiceSnapshot:
        raise AssertionError("classification writes no invoice")

    async def remove_invoice(self, baseline: CatalogueInvoiceSnapshot) -> CatalogueInvoiceSnapshot:
        raise AssertionError("classification removes no invoice")

    async def transaction(self, transaction_id: str) -> LedgerTransactionProjection:
        self.asked.append(transaction_id)
        return self._projection

    async def update_transaction(
        self,
        baseline: LedgerTransactionProjection,
        patch: LedgerUpdatePatch,
        fields: tuple[LedgerUpdatePatchField, ...],
    ) -> LedgerTransactionProjection:
        raise AssertionError("opening the classification writes nothing")


@pytest.mark.asyncio
async def test_the_classification_pickers_start_at_the_links_the_selected_entry_holds(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = _options(authority_operation, rows=True)
    prop = _served(options, "inmueble_ref")[0][1]
    concept = _served(options, "gasto_capital_inmobiliario")[0][1]
    projection = LedgerTransactionProjection.from_payload(
        ledger_transaction_payload(rental_row(inmueble_ref=prop, gasto_capital_inmobiliario=concept))
    )
    records = _Records(projection)
    workspace = ledger_projection()
    target = workspace.entries[0].transaction_id
    controller = LedgerWorkspaceController(
        ledger_focused_context(target),
        workspace,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ActionReference(action_id=lookup_action("operator.ledger.classify").action_id),
            link_options_door=_Door(options),
            record_doors=records,
        ),
    )
    screen = LedgerClassificationScreen(controller)
    async with ScreenHostApp[None](screen).run_test(size=(120, 70)) as pilot:
        await settle(pilot)
        links = screen.query_one("#ledger-classification-links", LedgerLinkPickers)
        assert links.chosen() == {"inmueble_ref": prop, "gasto_capital_inmobiliario": concept}
        assert records.asked == [str(target)]
