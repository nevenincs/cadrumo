"""Localized screen, comparison and layout tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Static

from .....application.aeat_sync.workspace import (
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncOverviewArea,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)
from .....application.live.notifications_read_operation import (
    NOTIFICATIONS_LIST_DEFINITION_ID,
)
from .....application.operations.models import OperationDefinitionId
from .....application.operations.registry import OperationPublicContractSetV1
from .....application.operator_actions.catalogue import (
    OPERATOR_ACTION_CATALOGUE,
)
from .....application.operator_actions.models import ActionReference
from .....core.config import override_settings
from .....core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from .....tests.aeat_literal_fixtures import (
    CENSO_SOURCE_URL_FIXTURE,
    OBLIGACIONES_SOURCE_URL_FIXTURE,
)
from ...components.host import ScreenHostApp
from ...navigation import TuiScreenContextV1
from ...operations.controller_port import OperationControllerPort
from ...tests.settling import settle
from ..census_screen import AeatSyncCensusScreen
from ..controller import AeatSyncWorkspaceController
from ..evidence_comparison_screen import AeatSyncEvidenceComparisonScreen
from ..filed_declarations_screen import AeatSyncFiledDeclarationsScreen
from ..models import (
    AeatSyncOperationRequestV1,
)
from ..notifications_screen import AeatSyncNotificationsScreen
from ..overview_screen import AeatSyncOverviewScreen
from ..reconciliation_screen import AeatSyncReconciliationScreen
from .aeat_sync_workspace_support import (
    BUCKET_ID,
    REPRESENTATIVE_KEYS,
    SCREEN_CASES,
    SUBJECT_KEY,
    T1,
    T2,
    ScreenFactory,
    aeat_sync_workspace_contracts,
    aeat_sync_workspace_controller,
    aeat_sync_workspace_projection,
    empty_projection,
    started_operation_controller,
    table_text,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_aeat_sync_status_keys_are_present_in_every_supported_locale() -> None:
    """Status/refusal copy must never fall back to a key in a shipped locale."""
    keys = (
        "tui.aeat_sync.operation.in_flight",
        "tui.aeat_sync.operation.already_handled",
        "tui.aeat_sync.notification.already_handled",
        "tui.aeat_sync.notification.document_handed_off",
        "tui.aeat_sync.refusal.notification_handoff",
        "tui.aeat_sync.refusal.unread_notification",
    )
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        for locale in ("en", "es", "ca", "hu"):
            for key in keys:
                rendered = tr(key, locale=locale)
                assert rendered != key
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
@pytest.mark.parametrize("screen_type, heading_key, headings, expected_keys", SCREEN_CASES)
async def test_every_aeat_sync_screen_is_localized_and_keeps_route_and_row_identities(
    locale: str,
    screen_type: ScreenFactory,
    heading_key: str,
    headings: dict[str, str],
    expected_keys: tuple[str, ...],
) -> None:
    """Mount all six routes in all four locales without identity drift."""
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            screen = screen_type(aeat_sync_workspace_controller())
            async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
                await settle(pilot)
                rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
                assert headings[locale] in rendered
                assert headings[locale] == tr(heading_key, locale=locale)
                if locale != "en":
                    assert headings[locale] != headings["en"]
                table = screen.query_one("#aeat-sync-rows", DataTable)
                navigation = screen.query_one("#aeat-sync-navigation", DataTable)
                visible = "\n".join((rendered, table_text(navigation), table_text(table)))
                assert tr("tui.aeat_sync.column.area", locale=locale) in visible
                assert tr("tui.aeat_sync.availability.available", locale=locale) in visible
                for key in REPRESENTATIVE_KEYS[screen_type]:
                    translated = tr(key, locale=locale)
                    assert translated != key
                    assert translated in visible
                assert "tui.aeat_sync." not in visible
                assert "AeatSync" not in visible
                for raw_token in ("filed_declarations", "evidence_comparison", "never_captured"):
                    assert raw_token not in visible
                keys = tuple(str(item.key.value) for item in table.ordered_rows)
                if screen_type is AeatSyncNotificationsScreen:
                    assert keys == (str(screen.controller.projection.notifications[0].selection_key),)
                else:
                    assert keys == expected_keys
                assert screen.id == f"aeat-sync-{screen.zone.value.replace('_', '-')}-screen"
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locale", "failure_copy", "refusal_copy"),
    (
        (
            "en",
            "Operation could not be started.",
            "AEAT operations can't be started from this session.",
        ),
        (
            "es",
            "No se pudo iniciar la operación.",
            "Las operaciones con la AEAT no se pueden iniciar desde esta sesión.",
        ),
        (
            "ca",
            "No s'ha pogut iniciar l'operació.",
            "Les operacions amb l'AEAT no es poden iniciar des d'aquesta sessió.",
        ),
        (
            "hu",
            "A műveletet nem sikerült elindítani.",
            "AEAT-műveletek ebből a munkamenetből nem indíthatók.",
        ),
    ),
)
async def test_operation_failure_and_refusal_copy_is_localized(
    locale: str,
    failure_copy: str,
    refusal_copy: str,
) -> None:
    """Host failure and absent-door refusal are both translated operator states."""

    async def fail(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        raise RuntimeError("sentinel host failure C:\\protected\\taxpayer.txt 12345678Z")

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            failed = AeatSyncOverviewScreen(aeat_sync_workspace_controller(operation_handoff=fail))
            async with ScreenHostApp[None](failed).run_test(size=(100, 30)) as pilot:
                await settle(pilot)
                await pilot.click("#aeat-sync-operation-0")
                await settle(pilot)
                rendered = str(failed.query_one("#aeat-sync-status", Static).render())
                assert failure_copy in rendered
                assert "protected" not in rendered
                assert "12345678Z" not in rendered

            refused = AeatSyncOverviewScreen(aeat_sync_workspace_controller())
            async with ScreenHostApp[None](refused).run_test(size=(100, 30)) as pilot:
                await settle(pilot)
                assert not refused.query("#aeat-sync-operation-0")
                assert refusal_copy in str(refused.query_one("#aeat-sync-status", Static).render())
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("availability", tuple(AeatSyncWorkspaceAvailability))
async def test_every_zone_renders_truthful_empty_or_unobservable_source_state(
    availability: AeatSyncWorkspaceAvailability,
) -> None:
    """Known-empty and unknown source states remain visibly distinct in all zones."""
    projection = empty_projection(availability)
    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_contracts=aeat_sync_workspace_contracts(),
    )
    expected_count = (
        0 if availability in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE} else None
    )
    for screen_factory, _heading, _translations, _keys in SCREEN_CASES:
        screen = screen_factory(controller)
        async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            state = controller.state_for(screen.zone)
            assert state.item_count == expected_count
            assert screen.query_one("#aeat-sync-rows", DataTable).row_count == 0
            rendered_status = str(screen.query_one("#aeat-sync-status", Static).render())
            assert tr(f"tui.aeat_sync.availability.{availability.value}") in rendered_status
            if expected_count == 0:
                assert "0" in rendered_status
            else:
                assert tr("tui.aeat_sync.value.none") in rendered_status


@pytest.mark.asyncio
@pytest.mark.parametrize("width", (80, 100, 120))
async def test_all_routes_have_one_scroll_owner_no_horizontal_overflow_and_reachable_actions(width: int) -> None:
    """The supported widths expose every action through keyboard focus."""
    for screen_factory, _heading, _translations, _keys in SCREEN_CASES:
        screen = screen_factory(aeat_sync_workspace_controller())
        async with ScreenHostApp[None](screen).run_test(size=(width, 24)) as pilot:
            await settle(pilot)
            overflowing = tuple(
                (table.id, table.max_scroll_x, table.virtual_size, table.container_size)
                for table in screen.query(DataTable)
                if table.max_scroll_x
            )
            assert not overflowing, (screen_factory, width, overflowing)
            owners = tuple(screen.query(VerticalScroll))
            assert len(owners) == 1
            assert owners[0].id == "aeat-sync-page"
            assert not any(table.show_vertical_scrollbar for table in screen.query(DataTable))
            buttons = tuple(screen.query(Button))
            for button in buttons:
                reached = False
                for _ in range(8):
                    await pilot.press("tab")
                    await settle(pilot)
                    if screen.app.focused is button:
                        reached = True
                        break
                assert reached
            nav_text = table_text(screen.query_one("#aeat-sync-navigation", DataTable))
            assert tr("tui.aeat_sync.availability.available") in nav_text


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
async def test_census_adoption_is_local_wording_and_no_remote_push_control(locale: str) -> None:
    """Census comparison is local review state, never an invented remote push UI."""
    with override_settings(cadrumo_output_language=locale):
        projection = aeat_sync_workspace_projection(census_status=AeatSyncCensusStatus.ADOPTED)
        controller = AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            projection,
            operation_contracts=aeat_sync_workspace_contracts(),
        )
        census = AeatSyncCensusScreen(controller)
        async with ScreenHostApp[None](census).run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            visible = table_text(census.query_one("#aeat-sync-rows", DataTable))
            assert tr("tui.aeat_sync.census_status.adopted", locale=locale) in visible
            assert not tuple(census.query(Button))


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
async def test_filed_pull_all_uses_action_specific_copy_and_exact_one_shot_handoff(
    locale: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filed history pull comes from the overview declaration, never a filed DTO."""
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        return started_operation_controller()

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            controller = aeat_sync_workspace_controller(
                operation_handoff=handoff,
                overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
                action_id="operator.live.filed.pull_all",
                operation_id="live.filed-history.pull",
            )
            for screen in (AeatSyncOverviewScreen(controller), AeatSyncFiledDeclarationsScreen(controller)):
                monkeypatch.setattr(screen, "_show_operation_modal", lambda _controller: None)
                async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
                    await settle(pilot)
                    button = screen.query_one("#aeat-sync-operation-0", Button)
                    expected = tr("tui.aeat_sync.action.pull_filed_all", locale=locale)
                    assert expected != "tui.aeat_sync.action.pull_filed_all"
                    assert str(button.label) == expected
                    await pilot.click("#aeat-sync-operation-0")
                    await settle(pilot)
                    assert button.disabled
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    expected_request = AeatSyncOperationRequestV1(
        action=ActionReference(action_id="operator.live.filed.pull_all"),
        operation="live.filed-history.pull",
    )
    assert calls == [expected_request, expected_request]


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
async def test_overview_actions_use_distinct_localized_census_and_notification_copy(locale: str) -> None:
    """Census review and notification listing retain their own action copy."""

    async def handoff(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        return started_operation_controller()

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            census = AeatSyncOverviewScreen(aeat_sync_workspace_controller(operation_handoff=handoff))
            async with ScreenHostApp[None](census).run_test(size=(80, 24)) as pilot:
                await settle(pilot)
                label = str(census.query_one("#aeat-sync-operation-0", Button).label)
                assert label == tr("tui.aeat_sync.action.review_census", locale=locale)
                assert label != tr("tui.aeat_sync.action.pull_filed_all", locale=locale)

            notifications = AeatSyncOverviewScreen(
                aeat_sync_workspace_controller(
                    operation_handoff=handoff,
                    overview_area=AeatSyncOverviewArea.NOTIFICATIONS,
                    action_id="operator.live.notifications.list",
                    operation_id=NOTIFICATIONS_LIST_DEFINITION_ID,
                )
            )
            async with ScreenHostApp[None](notifications).run_test(size=(80, 24)) as pilot:
                await settle(pilot)
                label = str(notifications.query_one("#aeat-sync-operation-0", Button).label)
                assert label == tr("tui.search.action.list_notifications", locale=locale)
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("first_fails", (False, True))
async def test_completing_one_overview_operation_keeps_the_other_action_reachable(
    first_fails: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global in-flight guard must not become a global consumed-state guard."""
    rows = (
        AeatSyncWorkspaceOverviewRowV1(
            area=AeatSyncOverviewArea.CENSUS,
            local_state=AeatSyncSourceState.PRESENT,
            aeat_state=AeatSyncSourceState.PRESENT,
            local_observed_at=T1,
            aeat_observed_at=T2,
            discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
            supported_actions=(ActionReference(action_id="operator.profile.edit"),),
            supported_operations=("user-profile.censo-review",),
        ),
        AeatSyncWorkspaceOverviewRowV1(
            area=AeatSyncOverviewArea.FILED_DECLARATIONS,
            local_state=AeatSyncSourceState.PRESENT,
            aeat_state=AeatSyncSourceState.PRESENT,
            local_observed_at=T1,
            aeat_observed_at=T2,
            discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
            supported_actions=(ActionReference(action_id="operator.live.filed.pull_all"),),
            supported_operations=("live.filed-history.pull",),
        ),
    )
    observations = tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            sources=tuple(
                AeatSyncWorkspaceSourceObservationV1(
                    source=source,
                    availability=AeatSyncWorkspaceAvailability.AVAILABLE,
                    observed_at=T2,
                    item_count=2 if zone is AeatSyncWorkspaceZone.OVERVIEW else 0,
                )
                for source in aeat_sync_workspace_sources(zone)
            ),
        )
        for zone in AeatSyncWorkspaceZone
    )
    contracts = OperationPublicContractSetV1.build(
        (
            *aeat_sync_workspace_contracts().definitions,
            *aeat_sync_workspace_contracts("operator.live.filed.pull_all", "live.filed-history.pull").definitions,
        )
    )
    projection = project_aeat_sync_workspace(
        bucket_id=BUCKET_ID,
        subject_key=SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=contracts,
        overview=tuple(AeatSyncWorkspaceFactV1(BUCKET_ID, SUBJECT_KEY, row) for row in rows),
    )
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        if first_fails and request.action.action_id == "operator.profile.edit":
            raise RuntimeError("C:\\protected\\taxpayer.txt 12345678Z")
        return started_operation_controller()

    screen = AeatSyncOverviewScreen(
        AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            projection,
            operation_contracts=contracts,
            operation_handoff=handoff,
        )
    )
    mounted_controllers: list[OperationControllerPort] = []
    # Each handoff returns a controller; this test isolates the in-flight and
    # one-shot controls from the modal's independent polling lifecycle.
    monkeypatch.setattr(screen, "_show_operation_modal", mounted_controllers.append)
    async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        first = screen.query_one("#aeat-sync-operation-0", Button)
        second = screen.query_one("#aeat-sync-operation-1", Button)
        # Scrolled into view before clicking, because `pilot.click` targets
        # SCREEN COORDINATES: a control below the fold is clicked at whatever
        # happens to be painted there instead, the handler never runs, and the
        # failure reads as a broken in-flight guard rather than a missed click.
        # At the 80x24 floor these operation buttons start below the fold --
        # measured at y=16 of 24 once scrolled, and off-screen before that --
        # so this is what an operator does to reach them, not a workaround.
        first.scroll_visible(animate=False)
        await settle(pilot)
        await pilot.click(first)
        # A click POSTS a message; the handler that disables the button runs on
        # the next pump. Asserting straight after the click races that handler,
        # which is why this passed only when earlier tests had shifted the
        # timing and failed whenever it ran alone.
        await settle(pilot)
        assert first.disabled
        assert not second.disabled
        if first_fails:
            status = str(screen.query_one("#aeat-sync-status", Static).render())
            assert status == tr("tui.aeat_sync.operation.failed")
            assert "protected" not in status
            assert "12345678Z" not in status
        second.scroll_visible(animate=False)
        await settle(pilot)
        await pilot.click(second)
        await settle(pilot)
    assert tuple(call.action.action_id for call in calls) == (
        "operator.profile.edit",
        "operator.live.filed.pull_all",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120, 200])
async def test_the_census_comparison_shows_both_values_or_neither(width: int) -> None:
    """Half a comparison is worse than none, and the verdict outranks both.

    A lone "Local value" column beside nothing to compare it against reads as a
    value AEAT does not hold, rather than a column the terminal had no room
    for. So the pair is taken whole or dropped whole.

    100 columns is the width that makes this testable, and it was added after
    the first version passed with the pair-splitting defect in place: at 80
    neither value fits and at 120 both do, so neither width can tell an atomic
    pair from a greedy one. Only a width where exactly ONE would fit
    distinguishes them.

    The status column is asserted at EVERY width because it is the verdict: an
    operator who cannot see whether a field is adopted or in conflict has lost
    the thing that tells them to act, and an earlier ordering that ranked the
    raw values above it failed exactly this way.
    """
    controller = aeat_sync_workspace_controller()
    screen = AeatSyncCensusScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(width, 40)) as pilot:
        await settle(pilot)
        table = cast("DataTable[str]", screen.query_one("#aeat-sync-rows", DataTable))
        keys = {str(column.key.value) for column in table.columns.values()}
        app.exit(None)

    assert "status" in keys, f"the census verdict is missing at {width} columns"
    assert ("local_value" in keys) == ("aeat_value" in keys), (
        f"at {width} columns the census shows half a comparison: {sorted(keys)}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120, 200])
@pytest.mark.parametrize(
    "screen_type",
    [AeatSyncCensusScreen, AeatSyncEvidenceComparisonScreen, AeatSyncReconciliationScreen],
)
async def test_every_comparison_surface_shows_both_values_or_neither(screen_type: ScreenFactory, width: int) -> None:
    """One rule, asserted on all three surfaces that compare two sides.

    The column fitter is shared precisely so the rule cannot drift between
    them, and this is what proves the sharing held: a screen that grew its own
    copy and split the pair fails here without touching the others.
    """
    controller = aeat_sync_workspace_controller()
    screen = screen_type(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(width, 40)) as pilot:
        await settle(pilot)
        table = cast("DataTable[str]", screen.query_one("#aeat-sync-rows", DataTable))
        keys = {str(column.key.value) for column in table.columns.values()}
        app.exit(None)

    assert ("local_value" in keys) == ("aeat_value" in keys), (
        f"{type(screen).__name__} at {width} columns shows half a comparison: {sorted(keys)}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 120])
async def test_complete_census_evidence_survives_reopen_and_selected_value_is_readable(width: int) -> None:
    """Operate the real evidence table after serialized workspace readback."""
    from .....application.user_profile.censal_observation import (
        CensalCell,
        CensalConsultation,
        CensalObservation,
        CensalObservationAddress,
        CensalObservationIdentity,
        CensalRow,
        CensalSection,
    )

    long_value = "Valor censal completo " * 20
    observation = CensalObservation(
        identity=CensalObservationIdentity(nif="00001005Q", apellidos_y_nombre="Persona Sintética"),
        domicilio_fiscal=CensalObservationAddress(codigo_postal="28001"),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=T2,
        source_url=CENSO_SOURCE_URL_FIXTURE,
        consultations=(
            CensalConsultation(
                kind="obligaciones",
                source_url=OBLIGACIONES_SOURCE_URL_FIXTURE,
                sections=(
                    CensalSection(
                        title="Mis Obligaciones",
                        rows=(
                            CensalRow(
                                label="Obligación sintética",
                                cells=(CensalCell(role="value", column="Nueva columna AEAT", text=long_value),),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    serialized = (
        aeat_sync_workspace_projection().model_copy(update={"census_observation": observation}).model_dump_json()
    )
    for _ in range(2):
        restored = AeatSyncWorkspaceProjectionV1.model_validate_json(serialized)
        screen = AeatSyncCensusScreen(
            AeatSyncWorkspaceController(
                TuiScreenContextV1(destination="workbench.aeat_sync"),
                restored,
            )
        )
        async with ScreenHostApp[None](screen).run_test(size=(width, 30)) as pilot:
            await settle(pilot)
            table = screen.query_one("#aeat-sync-census-evidence", DataTable)
            assert table.row_count > 1
            table.focus()
            table.move_cursor(row=table.row_count - 1)
            await pilot.press("enter")
            await settle(pilot)
            detail = str(screen.query_one("#aeat-sync-census-value", Static).render())
            assert long_value in detail
            assert "Nueva columna AEAT" in detail
            assert "Mis Obligaciones" in detail
            assert table.max_scroll_x == 0
            assert restored.census_observation == observation


def test_controller_pairs_the_single_operation_with_its_contract_joined_action() -> None:
    """A row's catalogue-only actions do not hide the operation its contract joins."""
    controller = aeat_sync_workspace_controller(
        overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
        action_id="operator.live.filed.pull_all",
        operation_id="live.filed-history.pull",
    )
    pull = ActionReference(action_id="operator.live.filed.pull_all")
    listing = ActionReference(action_id="operator.modelo.filing_record.list")
    operation: OperationDefinitionId = "live.filed-history.pull"

    assert controller.admitted_operation((listing, pull), (operation,)) == AeatSyncOperationRequestV1(
        action=pull, operation=operation
    )
    assert controller.admitted_operation((listing,), (operation,)) is None
    assert controller.admitted_operation((listing, pull), (operation, "user-profile.censo-review")) is None


@pytest.mark.asyncio
async def test_reader_projected_filed_history_door_renders_and_hands_off_before_any_local_filing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real overview row pairs the pull with the local filing-record listing.

    A first-run profile holds no local filing, yet both the overview and the
    filed-declarations zone must offer one filed-history door, hand off its
    exact request, and state no refusal beside it.
    """
    from .....application.aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

    contracts = OperationPublicContractSetV1.build(
        (
            *aeat_sync_workspace_contracts().definitions,
            *aeat_sync_workspace_contracts("operator.live.filed.pull_all", "live.filed-history.pull").definitions,
        )
    )
    projection = read_local_aeat_sync_workspace_projection(
        bucket_id=BUCKET_ID,
        subject_key=SUBJECT_KEY,
        observed_at=T2,
        filings=(),
        operation_contracts=contracts,
        censo_values={},
    )
    filed_row = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.FILED_DECLARATIONS)
    assert {str(action.action_id) for action in filed_row.supported_actions} == {
        "operator.live.filed.pull_all",
        "operator.modelo.filing_record.list",
    }
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        return started_operation_controller()

    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_handoff=handoff,
        operation_contracts=contracts,
    )
    pull_label = tr("tui.aeat_sync.action.pull_filed_all")
    for screen in (AeatSyncOverviewScreen(controller), AeatSyncFiledDeclarationsScreen(controller)):
        monkeypatch.setattr(screen, "_show_operation_modal", lambda _controller: None)
        async with ScreenHostApp[None](screen).run_test(size=(100, 40)) as pilot:
            await settle(pilot)
            doors = [button for button in screen.query(Button) if str(button.label) == pull_label]
            assert len(doors) == 1
            status = str(screen.query_one("#aeat-sync-status", Static).render())
            assert tr("tui.aeat_sync.refusal.operation_handoff") not in status
            doors[0].scroll_visible(animate=False)
            await settle(pilot)
            await pilot.click(doors[0])
            await settle(pilot)
            assert doors[0].disabled

    expected = AeatSyncOperationRequestV1(
        action=ActionReference(action_id="operator.live.filed.pull_all"),
        operation="live.filed-history.pull",
    )
    assert calls == [expected, expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("width", (80, 120))
async def test_persisted_drift_renders_each_diff_values_and_grounding_without_overflow(width: int) -> None:
    from .....application.aeat_sync.tests.reconciliation_fixtures import (
        reconciliation_projection as persisted_projection,
    )
    from .....application.aeat_sync.tests.reconciliation_fixtures import reconciliation_record
    from .....application.modelo.reconciliation_records import ModeloReconciliationDiff, ModeloReconciliationDiffKind

    diff = ModeloReconciliationDiff(
        field_name="iva.resultado",
        work_unit_value="0.00",
        evidence_value="125.50",
        kind="value_mismatch",
        diff_kind=ModeloReconciliationDiffKind.CASILLA,
        legal_refs=("ley-37-1992:art-99",),
        source_refs=("aeat-test",),
    )
    record = reconciliation_record().model_copy(update={"diffs": (reconciliation_record().diffs[0], diff)})
    projection = AeatSyncWorkspaceProjectionV1.model_validate_json(persisted_projection((record,)).model_dump_json())
    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_contracts=aeat_sync_workspace_contracts(),
    )
    screen = AeatSyncReconciliationScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(width, 35)) as pilot:
            await settle(pilot)
            table = screen.query_one("#aeat-sync-rows", DataTable)
            assert table.row_count == 2
            table.move_cursor(row=1)
            await settle(pilot)
            detail = str(screen.query_one("#aeat-sync-reconciliation-detail", Static).render())
            assert all(
                value in detail
                for value in (
                    "0.00",
                    "125.50",
                    "iva.resultado",
                    "ley-37-1992:art-99",
                    "aeat-test",
                    "casilla",
                    "1 advisories",
                )
            )
            assert not any(table.max_scroll_x for table in screen.query(DataTable))


@pytest.mark.asyncio
async def test_stored_match_with_advisories_shows_incomplete_comparison() -> None:
    from .....application.aeat_sync.tests.reconciliation_fixtures import (
        reconciliation_projection as persisted_projection,
    )
    from .....application.aeat_sync.tests.reconciliation_fixtures import reconciliation_record

    projection = persisted_projection((reconciliation_record(mismatches=False),))
    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_contracts=aeat_sync_workspace_contracts(),
    )
    screen = AeatSyncReconciliationScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 35)) as pilot:
            await settle(pilot)
            table = screen.query_one("#aeat-sync-rows", DataTable)
            assert "Not fully compared" in table.get_row_at(0)
            detail = str(screen.query_one("#aeat-sync-reconciliation-detail", Static).render())
            assert "Not fully compared" in detail
            assert "1 advisories" in detail
            assert "No differences in compared fields" not in detail


@pytest.mark.asyncio
async def test_distinct_comparisons_at_same_address_have_unique_rows_and_historical_identity() -> None:
    from .....application.aeat_sync.tests.reconciliation_fixtures import (
        reconciliation_projection as persisted_projection,
    )
    from .....application.aeat_sync.tests.reconciliation_fixtures import reconciliation_record
    from .....application.modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind

    first = reconciliation_record().model_copy(
        update={
            "source_kind": ModeloReconciliationEvidenceKind.DECLARATION,
            "calculation_revision_id": "d" * 64,
        }
    )
    second = reconciliation_record(mismatches=False).model_copy(update={"bucket_event_id": "c" * 64})
    projection = persisted_projection((first, second))
    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_contracts=aeat_sync_workspace_contracts(),
    )
    screen = AeatSyncReconciliationScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 35)) as pilot:
            await settle(pilot)
            table = screen.query_one("#aeat-sync-rows", DataTable)
            assert table.row_count == 2
            assert len(set(table.rows)) == 2
            for index in range(2):
                table.move_cursor(row=index)
                await settle(pilot)
                detail = str(screen.query_one("#aeat-sync-reconciliation-detail", Static).render())
                assert "Stored comparison; current calculation has not been rechecked." in detail
                assert first.work_unit_id in detail
                row_key = str(table.ordered_rows[index].key.value)
                if first.bucket_event_id in row_key:
                    assert "Compared calculation:" in detail
                    assert first.calculation_revision_id is not None
                    assert first.calculation_revision_id in detail
                else:
                    assert "Compared calculation revision was not recorded." in detail
