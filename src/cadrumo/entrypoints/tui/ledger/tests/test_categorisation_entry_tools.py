"""The entry-scoped tools: IVA derivation, allocation, manual split and participation."""

from __future__ import annotations

import pytest
from textual.widgets import Button

from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.transactions.enums import BusinessClassification
from ..categorisation_allocate import LedgerAllocateScreen
from ..categorisation_iva import LedgerIvaDeriveScreen
from ..categorisation_participation import LedgerParticipationScreen
from ..categorisation_split import LedgerSplitScreen
from .categorisation_entry_fixtures import synthetic_participation
from .categorisation_fixtures import CATEGORISATION_REFUSAL_KEY
from .categorisation_memory_doors import LEDGER_TX_A, MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import keys, press, review_and_confirm, settle, text, type_into
from .test_ledger_selection_journey import _WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


@pytest.mark.asyncio
async def test_iva_derivation_reviews_the_category_then_shows_what_it_derived() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.operator_iva
    screen = LedgerIvaDeriveScreen(categorisation_controller(), door=doors.operator_iva)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-iva-category", "GENERAL")
            await press(pilot, screen, "categorisation-iva-review")
            assert door.requests == []
            assert text(screen, "#categorisation-staged") == tr(
                "tui.ledger.categorisation.iva.stage", category="GENERAL"
            )
            await press(pilot, screen, "categorisation-confirm")
            assert door.requests[0].transaction_id == LEDGER_TX_A
            assert profile.ledger.entries[LEDGER_TX_A].iva_category == "GENERAL"
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.iva.derived",
                category="GENERAL",
                rate="0.21",
                base="82.64",
                amount="17.36",
                note="derived from the gross amount",
            )
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.saved")


@pytest.mark.asyncio
async def test_iva_derivation_says_the_operations_refusal_and_writes_nothing() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    screen = LedgerIvaDeriveScreen(categorisation_controller(), door=doors.operator_iva)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await press(pilot, screen, "categorisation-iva-review")
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.iva.category_required")
            type_into(screen, "#categorisation-iva-category", "UNKNOWN")
            await review_and_confirm(pilot, screen, "categorisation-iva-review")
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.iva.refused", messages="IVA category is not declared by the pinned authority"
            )
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")
            assert profile.ledger.entries[LEDGER_TX_A].iva_category is None
            doors.operator_iva.refusing = True
            type_into(screen, "#categorisation-iva-category", "GENERAL")
            await review_and_confirm(pilot, screen, "categorisation-iva-review")
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)
            assert screen.staged is not None


@pytest.mark.asyncio
async def test_allocation_writes_the_reviewed_share_and_refuses_one_outside_the_unit_interval() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.allocate
    screen = LedgerAllocateScreen(categorisation_controller(), door=doors.allocate)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-allocate-pct", "1.5")
            await press(pilot, screen, "categorisation-allocate-review")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal")
            assert door.requests == []

            type_into(screen, "#categorisation-allocate-pct", "0.4")
            type_into(screen, "#categorisation-allocate-category", "vehiculo")
            await review_and_confirm(pilot, screen, "categorisation-allocate-review")
            assert door.requests[0].business_pct == "0.4"
            entry = profile.ledger.entries[LEDGER_TX_A]
            assert entry.business_classification == BusinessClassification.MIXED.value
            assert entry.business_pct == "0.4"
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.allocate.done",
                classification=tr("tui.ledger.categorisation.classification.mixed"),
                share="0.4",
                category="vehiculo",
            )


@pytest.mark.asyncio
async def test_a_split_whose_children_do_not_add_up_is_refused_before_anything_is_sent() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.split
    screen = LedgerSplitScreen(categorisation_controller(), split_door=doors.split, review_door=doors.split_review)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            for amount, description in (("1000", "Ordenador"), ("200", "Monitor")):
                type_into(screen, "#categorisation-split-amount", amount)
                type_into(screen, "#categorisation-split-description", description)
                await press(pilot, screen, "categorisation-split-add")
            assert keys(screen, "#categorisation-split-children") == ["child-1", "child-2"]
            await press(pilot, screen, "categorisation-split-review")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal") == tr(
                "tui.ledger.categorisation.split.unbalanced", children="1200", parent="1250.00", currency="EUR"
            )
            assert door.requests == []

            type_into(screen, "#categorisation-split-amount", "50")
            type_into(screen, "#categorisation-split-description", "Cables")
            await press(pilot, screen, "categorisation-split-add")
            await review_and_confirm(pilot, screen, "categorisation-split-review")
            sent = door.requests[0]
            assert [child.amount for child in sent.children] == ["1000", "200", "50"]
            assert profile.ledger.entries[LEDGER_TX_A].lifecycle_state == "SPLIT"
            assert keys(screen, "#categorisation-split-children") == []
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.split.done",
                count=3,
                parent=tr("tui.ledger.categorisation.classification.not_yet_processed"),
            )


@pytest.mark.asyncio
async def test_a_split_needs_two_children_and_positive_amounts() -> None:
    doors = MemoryCategorisationProfile().doors()
    screen = LedgerSplitScreen(categorisation_controller(), split_door=doors.split, review_door=doors.split_review)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-split-amount", "-5")
            type_into(screen, "#categorisation-split-description", "Negativo")
            await press(pilot, screen, "categorisation-split-add")
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.split.amount_invalid")
            type_into(screen, "#categorisation-split-amount", "1250")
            await press(pilot, screen, "categorisation-split-add")
            await press(pilot, screen, "categorisation-split-review")
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.split.too_few")
            await press(pilot, screen, "categorisation-split-remove")
            assert keys(screen, "#categorisation-split-children") == []


@pytest.mark.asyncio
async def test_participation_lists_declarations_and_a_cancelled_rebuild_writes_nothing() -> None:
    profile = MemoryCategorisationProfile()
    profile.ledger.participations = (synthetic_participation(1), synthetic_participation(2, modelo="130"))
    doors = profile.doors()
    rebuild = doors.participation_rebuild
    screen = LedgerParticipationScreen(
        categorisation_controller(), read_door=doors.participation, rebuild_door=doors.participation_rebuild
    )
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert keys(screen, "#categorisation-participations") == [f"{1:064x}", f"{2:064x}"]
            await press(pilot, screen, "categorisation-participation-rebuild")
            await press(pilot, screen, "categorisation-confirm")
            pilot.app.screen.query_one("#btn-confirm-cancel", Button).press()
            await settle(pilot)
            assert rebuild.requests == []
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")
            assert screen.staged is not None

            await press(pilot, screen, "categorisation-confirm")
            pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
            await settle(pilot)
            assert len(rebuild.requests) == 1
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.participation.rebuilt",
                transactions=2,
                participations=2,
                revisions=2,
                removed=0,
            )


@pytest.mark.asyncio
async def test_an_entry_in_no_declaration_and_a_refused_read_are_said() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    screen = LedgerParticipationScreen(
        categorisation_controller(), read_door=doors.participation, rebuild_door=doors.participation_rebuild
    )
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert keys(screen, "#categorisation-participations") == []
            assert text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.participation.empty")
    refused = MemoryCategorisationProfile()
    refused_doors = refused.doors()
    refused_doors.participation.refusing = True
    screen = LedgerParticipationScreen(
        categorisation_controller(),
        read_door=refused_doors.participation,
        rebuild_door=refused_doors.participation_rebuild,
    )
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)
