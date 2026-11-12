"""The counterparty tool states, shows and refuses a filing name through the registered operation's own models."""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Checkbox, Input, Select

from .....application.ledger.counterparty_operation import (
    CounterpartyFilingNameRendering,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
    served_kind_finding_words,
)
from .....core.config import override_settings
from .....core.i18n.render import tr
from ...refusal.panel import RefusalSlot
from ...tests.settling import settle
from ..categorisation_counterparties import LedgerCounterpartiesScreen
from .categorisation_fixtures import MemoryDoor
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import press, review_and_confirm, text, type_into
from .categorisation_register_fixtures import SYNTHETIC_ASSERTED_ON, SYNTHETIC_TAX_ID
from .workspace_fixtures import WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

type MemoryCounterpartyDoor = MemoryDoor[LedgerCounterpartyRequest, LedgerCounterpartyResult]

_PERSON_ID = "12345678Z"
_KIND = "#categorisation-filing-kind"


def _screen(profile: MemoryCategorisationProfile) -> tuple[LedgerCounterpartiesScreen, MemoryCounterpartyDoor]:
    door = profile.doors().counterparty
    return LedgerCounterpartiesScreen(categorisation_controller(selected=None), door=door), door


async def _choose_kind(pilot: Pilot[None], screen: LedgerCounterpartiesScreen, kind: str) -> None:
    cast("Select[str]", screen.query_one(_KIND, Select)).value = kind
    await settle(pilot)


@pytest.mark.asyncio
async def test_a_natural_person_name_with_a_shorter_rendering_is_stated_and_shown() -> None:
    profile = MemoryCategorisationProfile()
    screen, door = _screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-counterparty-identifier", _PERSON_ID)
            type_into(screen, "#categorisation-counterparty-asserted", "Operator")
            type_into(screen, "#categorisation-filing-primer", "Garcia")
            screen.query_one("#categorisation-filing-no-second", Checkbox).value = True
            type_into(screen, "#categorisation-filing-nombre", "Ana")
            type_into(screen, "#categorisation-filing-renderings", "20=Garcia A")
            await review_and_confirm(pilot, screen, "categorisation-counterparty-filing")

            sent = door.requests[-1]
            assert sent == LedgerCounterpartyRequest(
                profile_id=sent.profile_id,
                action="filing_name",
                tax_identifier=_PERSON_ID,
                party_kind="natural_person",
                primer_apellido="Garcia",
                no_second_surname=True,
                nombre="Ana",
                renderings=(CounterpartyFilingNameRendering(width=20, text="Garcia A"),),
                asserted_by="Operator",
            )
            outcome = text(screen, "#categorisation-outcome")
            assert tr("tui.ledger.categorisation.counterparty.filing_done", identifier=_PERSON_ID) in outcome
            assert (
                tr(
                    "tui.ledger.categorisation.counterparty.filing_stated_by",
                    name="Operator",
                    date=SYNTHETIC_ASSERTED_ON,
                )
                in outcome
            )
            assert tr("tui.ledger.categorisation.counterparty.filing_rendering", width=20, text="Garcia A") in outcome

            for field_id in ("primer", "nombre", "renderings"):
                type_into(screen, f"#categorisation-filing-{field_id}", "")
            screen.query_one("#categorisation-filing-no-second", Checkbox).value = False
            await press(pilot, screen, "categorisation-counterparty-view")
            shown = text(screen, "#categorisation-outcome")
            assert tr("tui.ledger.categorisation.counterparty.filing_primer") + ": Garcia" in shown
            assert tr("tui.ledger.categorisation.counterparty.filing_no_second") in shown
            assert screen.query_one("#categorisation-filing-primer", Input).value == "Garcia"
            assert screen.query_one("#categorisation-filing-renderings", Input).value == "20=Garcia A"
            assert screen.query_one("#categorisation-filing-no-second", Checkbox).value is True


@pytest.mark.asyncio
async def test_a_view_without_a_stated_name_says_so() -> None:
    profile = MemoryCategorisationProfile()
    screen, _ = _screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-counterparty-identifier", SYNTHETIC_TAX_ID)
            await press(pilot, screen, "categorisation-counterparty-view")
            assert tr("tui.ledger.categorisation.counterparty.filing_unstated", identifier=SYNTHETIC_TAX_ID) in text(
                screen, "#categorisation-outcome"
            )


@pytest.mark.asyncio
async def test_a_kind_that_contradicts_the_identifier_form_shows_the_operations_words() -> None:
    profile = MemoryCategorisationProfile()
    screen, _ = _screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-counterparty-identifier", SYNTHETIC_TAX_ID)
            type_into(screen, "#categorisation-counterparty-asserted", "Operator")
            await _choose_kind(pilot, screen, "natural_person")
            type_into(screen, "#categorisation-filing-primer", "Perez")
            type_into(screen, "#categorisation-filing-nombre", "Luis")
            type_into(screen, "#categorisation-filing-segundo", "Lopez")
            await review_and_confirm(pilot, screen, "categorisation-counterparty-filing")
            words, _language = served_kind_finding_words(declared_kind="natural_person", observed_form="entity")
            assert words in text(screen, "#categorisation-outcome")
            await press(pilot, screen, "categorisation-counterparty-view")
            assert words in text(screen, "#categorisation-outcome")


@pytest.mark.asyncio
async def test_parts_that_form_no_name_are_refused_with_the_operations_words_and_its_panel() -> None:
    profile = MemoryCategorisationProfile()
    screen, _ = _screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-counterparty-identifier", SYNTHETIC_TAX_ID)
            type_into(screen, "#categorisation-counterparty-asserted", "Operator")
            await _choose_kind(pilot, screen, "entity")
            await review_and_confirm(pilot, screen, "categorisation-counterparty-filing")
            refusal = text(screen, "#ledger-refusal")
            assert refusal
            assert "Entity" not in refusal
            assert screen.query_one("#ledger-refusal-panel", RefusalSlot).refusal is not None
            assert profile.counterparties.filing_names == {}


@pytest.mark.asyncio
async def test_a_malformed_rendering_is_refused_before_anything_is_staged() -> None:
    profile = MemoryCategorisationProfile()
    screen, _ = _screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 70)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-counterparty-identifier", SYNTHETIC_TAX_ID)
            type_into(screen, "#categorisation-counterparty-asserted", "Operator")
            await _choose_kind(pilot, screen, "entity")
            type_into(screen, "#categorisation-filing-razon", "Delta SL")
            type_into(screen, "#categorisation-filing-renderings", "wide Delta")
            await press(pilot, screen, "categorisation-counterparty-filing")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal") == tr(
                "tui.ledger.categorisation.counterparty.filing_renderings_malformed"
            )
