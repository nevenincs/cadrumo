"""Counterparty facts, usage ratios and classifier diagnostics over the operations' own models."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Input

from .....core.config import override_settings
from .....core.i18n.render import tr
from ...tests.settling import settle
from ..categorisation_counterparties import LedgerCounterpartiesScreen
from ..categorisation_diagnostics import LedgerDiagnosticsScreen
from ..categorisation_ratios import LedgerRatiosScreen
from .categorisation_fixtures import CATEGORISATION_REFUSAL_KEY, MemoryDoor
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import keys, press, review_and_confirm, text, type_into
from .categorisation_register_fixtures import SYNTHETIC_RATIO_CATEGORIES, SYNTHETIC_TAX_ID, diagnostics_report
from .workspace_fixtures import WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _ratios_screen(profile: MemoryCategorisationProfile) -> LedgerRatiosScreen:
    doors = profile.doors()
    return LedgerRatiosScreen(
        categorisation_controller(),
        list_door=doors.ratios_list,
        eligible_door=doors.ratios_eligible,
        validate_door=doors.ratios_validate,
        set_door=doors.ratios_set,
        unset_door=doors.ratios_unset,
    )


@pytest.mark.asyncio
async def test_counterparty_confirm_view_and_withdraw_after_a_cancelled_confirmation() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.counterparty
    screen = LedgerCounterpartiesScreen(categorisation_controller(selected=None), door=doors.counterparty)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await press(pilot, screen, "categorisation-counterparty-view")
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.counterparty.identifier_required")
            assert door.requests == []

            type_into(screen, "#categorisation-counterparty-identifier", SYNTHETIC_TAX_ID)
            type_into(screen, "#categorisation-counterparty-scope", "TAI")
            type_into(screen, "#categorisation-counterparty-asserted", "Operator")
            await review_and_confirm(pilot, screen, "categorisation-counterparty-confirm")
            assert door.requests[0].action == "confirm"
            assert profile.counterparties.facts[SYNTHETIC_TAX_ID].territorial_scope == "TAI"
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.counterparty.confirmed", identifier=SYNTHETIC_TAX_ID, scope="TAI", state="-"
            )

            await press(pilot, screen, "categorisation-counterparty-view")
            assert door.requests[-1].action == "view"
            assert text(screen, "#categorisation-outcome") == "\n".join(
                (
                    tr(
                        "tui.ledger.categorisation.counterparty.scope",
                        identifier=SYNTHETIC_TAX_ID,
                        scope="TAI",
                        source="operator_confirmed",
                    ),
                    tr("tui.ledger.categorisation.counterparty.state", state="-", source="operator_confirmed"),
                )
            )

            await press(pilot, screen, "categorisation-counterparty-withdraw")
            await press(pilot, screen, "categorisation-confirm")
            pilot.app.screen.query_one("#btn-confirm-cancel", Button).press()
            await settle(pilot)
            assert SYNTHETIC_TAX_ID in profile.counterparties.facts
            assert [request.action for request in door.requests] == ["confirm", "view"]

            await press(pilot, screen, "categorisation-confirm")
            pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
            await settle(pilot)
            assert SYNTHETIC_TAX_ID not in profile.counterparties.facts
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.counterparty.withdrawn", identifier=SYNTHETIC_TAX_ID
            )


@pytest.mark.asyncio
async def test_a_confirmation_without_an_answered_axis_is_refused_and_a_door_refusal_is_said() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.counterparty
    screen = LedgerCounterpartiesScreen(categorisation_controller(selected=None), door=doors.counterparty)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-counterparty-identifier", SYNTHETIC_TAX_ID)
            type_into(screen, "#categorisation-counterparty-asserted", "Operator")
            await press(pilot, screen, "categorisation-counterparty-confirm")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal")
            door.refusing = True
            await press(pilot, screen, "categorisation-counterparty-view")
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)


@pytest.mark.asyncio
async def test_usage_ratios_set_list_and_unset_round_trip() -> None:
    profile = MemoryCategorisationProfile()
    screen = _ratios_screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            year = int(screen.query_one("#categorisation-ratios-year", Input).value)
            assert keys(screen, "#categorisation-ratios-overrides") == []
            assert keys(screen, "#categorisation-ratios-eligible") == list(SYNTHETIC_RATIO_CATEGORIES)
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.ratios.no_overrides", year=year
            )

            eligible = screen.query_one("#categorisation-ratios-eligible", DataTable)
            eligible.focus()
            eligible.move_cursor(row=1)
            await pilot.press("enter")
            await settle(pilot)
            assert screen.query_one("#categorisation-ratios-category", Input).value == "vehiculo"
            type_into(screen, "#categorisation-ratios-ratio", "0.5")
            await review_and_confirm(pilot, screen, "categorisation-ratios-set")
            assert profile.ratios.overrides == {"vehiculo": "0.5"}
            assert keys(screen, "#categorisation-ratios-overrides") == ["vehiculo"]
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.ratios.set_done", category="vehiculo", ratio="0.5", prior="-"
            )

            await press(pilot, screen, "categorisation-ratios-validate")
            assert text(screen, "#categorisation-outcome") == "\n".join(
                (
                    tr("tui.ledger.categorisation.ratios.validation_counts", eligible=2, overrides=1),
                    tr("tui.ledger.categorisation.ratios.validation_missing", categories="suministros_vivienda"),
                )
            )

            await press(pilot, screen, "categorisation-ratios-unset")
            await press(pilot, screen, "categorisation-confirm")
            pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
            await settle(pilot)
            assert profile.ratios.overrides == {}
            assert keys(screen, "#categorisation-ratios-overrides") == []
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.ratios.unset_done", category="vehiculo", prior="0.5"
            )


@pytest.mark.asyncio
async def test_ratios_refuse_an_out_of_range_ratio_and_say_a_census_mismatch() -> None:
    profile = MemoryCategorisationProfile()
    profile.ratios.censo_mismatch = True
    screen = _ratios_screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            year = int(screen.query_one("#categorisation-ratios-year", Input).value)
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.ratios.censo_mismatch", year=year
            )
            type_into(screen, "#categorisation-ratios-category", "vehiculo")
            type_into(screen, "#categorisation-ratios-ratio", "1.4")
            await press(pilot, screen, "categorisation-ratios-set")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal")
            type_into(screen, "#categorisation-ratios-year", "20x6")
            await press(pilot, screen, "categorisation-ratios-read")
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.ratios.year_invalid")


@pytest.mark.asyncio
async def test_removing_a_ratio_that_is_not_set_writes_nothing() -> None:
    profile = MemoryCategorisationProfile()
    screen = _ratios_screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-ratios-category", "vehiculo")
            await press(pilot, screen, "categorisation-ratios-unset")
            await press(pilot, screen, "categorisation-confirm")
            pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
            await settle(pilot)
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.ratios.unset_nothing", category="vehiculo", prior="-"
            )
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")


@pytest.mark.asyncio
async def test_diagnostics_read_the_report_for_the_typed_range() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.llm_diagnostics
    screen = LedgerDiagnosticsScreen(categorisation_controller(selected=None), door=doors.llm_diagnostics)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert keys(screen, "#categorisation-diagnostics-usage") == ["lector-local"]
            assert keys(screen, "#categorisation-diagnostics-confidence") == ["lector-local"]
            type_into(screen, "#categorisation-diagnostics-since", "2026-01-01")
            type_into(screen, "#categorisation-diagnostics-until", "2026-03-31")
            await press(pilot, screen, "categorisation-diagnostics-read")
            request = door.requests[-1]
            assert str(request.since) == "2026-01-01"
            assert str(request.until) == "2026-03-31"
            assert text(screen, "#categorisation-diagnostics-totals").startswith(
                tr(
                    "tui.ledger.categorisation.diagnostics.usage_totals",
                    calls=42,
                    cache_hits=10,
                    input_tokens=12000,
                    output_tokens=3000,
                    cost="-",
                    unpriced=42,
                )
            )

            type_into(screen, "#categorisation-diagnostics-since", "2026-02-30")
            await press(pilot, screen, "categorisation-diagnostics-read")
            assert text(screen, "#ledger-refusal")
            assert len(door.requests) == 2


@pytest.mark.asyncio
async def test_diagnostics_say_an_empty_report_and_a_refusal() -> None:
    empty = MemoryDoor(lambda request: diagnostics_report(request, with_data=False))
    screen = LedgerDiagnosticsScreen(categorisation_controller(selected=None), door=empty)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.diagnostics.empty")
            empty.refusing = True
            await press(pilot, screen, "categorisation-diagnostics-read")
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)
