"""Contract, interaction, locale, geometry, and security tests."""

from __future__ import annotations

import ast
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Static

from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue

from .....application.modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from .....application.modelo.declaration_targets import DeclarationTarget, declaration_targets
from .....application.modelo.declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)
from .....application.modelo.work_form_models import ModeloFormResult, ModeloFormResultDirection
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.casilla_id import validated_casilla_id
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...components.host import ScreenHostApp
from ...modelo.lifecycle import ModeloLifecycleActionUnavailableError
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ...tests.frame import geometry_band
from ..controller import DeclarationsWorkspaceController
from ..filing_history import DeclarationsFilingHistoryScreen
from ..models import (
    DeclarationsWorkspaceWiringV1,
    FilingHandoffV1,
    ModeloWorkCreateHandoffV1,
    ModeloWorkCreateResultV1,
    ModeloWorkspaceScreenFactoryV1,
    RevisionHandoffV1,
)
from ..overview import DeclarationsOverviewScreen
from ..picker import NewDeclarationPicker
from ..revisions import DeclarationsRevisionsScreen
from ..routes import (
    DECLARATIONS_ROUTES,
    DeclarationsUnavailableScreen,
    declarations_screen_factory,
    resolve_declarations_screen,
)
from .portfolio_fixtures import portfolio_projection

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_BUCKET = "11111111-1111-4111-8111-111111111111"
_CASILLA = validated_casilla_id("01")
_EXPECTED = {
    OutputLanguage.ES: (
        "Tus declaraciones",
        "Cálculos anteriores",
        "Historial de presentaciones",
        "El estado local de presentación, la confirmación de la AEAT y el estado observado en la AEAT son hechos distintos.",
        "Presentación registrada",
    ),
    OutputLanguage.EN: (
        "Your declarations",
        "Earlier calculations",
        "Filing history",
        "Local filing status, AEAT confirmation and externally observed AEAT status are separate facts.",
        "Filing recorded",
    ),
    OutputLanguage.CA: (
        "Les teves declaracions",
        "Càlculs anteriors",
        "Historial de presentacions",
        "L'estat local de presentació, la confirmació de l'AEAT i l'estat observat a l'AEAT són fets separats.",
        "Presentació registrada",
    ),
    OutputLanguage.HU: (
        "A bevallásaid",
        "Korábbi számítások",
        "Benyújtási előzmények",
        "A helyi benyújtási állapot, az AEAT-megerősítés és a megfigyelt AEAT-állapot külön tények.",
        "Benyújtás rögzítve",
    ),
}


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Keep one indexed authority generation live for each TUI projection test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _projection(
    operation: PinnedAuthorityOperation, *, unavailable: DeclarationsWorkspaceZone | None = None, empty: bool = False
) -> DeclarationsWorkspaceProjectionV1:
    registry_snapshot_ref = operation.snapshot("130", filing_year=2026, period="1T").snapshot_ref
    observations = tuple(
        DeclarationsWorkspaceZoneObservationV1(
            zone=zone,
            availability=(
                DeclarationsWorkspaceAvailability.NEVER_CAPTURED
                if zone is unavailable
                else DeclarationsWorkspaceAvailability.AVAILABLE
            ),
            observed_at=None if zone is unavailable else _NOW,
            reason_code="declarations.source.missing" if zone is unavailable else None,
        )
        for zone in DeclarationsWorkspaceZone
    )
    if empty:
        return project_declarations_workspace(
            operation=operation,
            bucket_id=_BUCKET,
            work_units=WorkUnitCatalogue(),
            calculation_revisions=CalculationRevisionCatalogue(),
            filing_records=ModeloRecordCatalogue(),
            lifecycle_facts=(),
            zone_observations=observations,
        )
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        revision_id=registry_snapshot_ref.revision_id,
    )
    filed_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_CASILLA: "10.00"},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    draft_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_CASILLA: "20.00"},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    later_draft_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_CASILLA: "30.00"},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=filed_revision_id,
        filed_by="operator",
        member_nif="12345678Z",
    )
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        revision_id=registry_snapshot_ref.revision_id,
        name="private label",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=filed_revision_id,
        filed_calculation_revision_id=filed_revision_id,
        current_filing_record_id=filing_record_id,
    )
    filed_revision = CalculationRevision(
        calculation_revision_id=filed_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id={_CASILLA: "10.00"},
        casilla_values={},
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filed_at=_NOW,
        filed_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    draft_revision = CalculationRevision(
        calculation_revision_id=draft_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_CASILLA: "20.00"},
        casilla_values={},
        created_at=_NOW.replace(hour=9, minute=15),
        updated_at=_NOW.replace(hour=9, minute=15),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    later_draft_revision = CalculationRevision(
        calculation_revision_id=later_draft_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_CASILLA: "30.00"},
        casilla_values={},
        created_at=_NOW.replace(hour=9, minute=45),
        updated_at=_NOW.replace(hour=9, minute=45),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    filing = ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=filed_revision_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        member_nif="12345678Z",
        filed_at=_NOW,
        filed_by="operator",
        notes="private notes",
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="private-reference",
            imported_at=_NOW,
        ),
    )
    lifecycle = (
        DeclarationsSanitizedLifecycleFactV1(
            fact_id="event-created",
            work_unit_id=work_unit_id,
            occurred_at=_NOW.replace(day=1),
            kind=DeclarationsLifecycleKind.CREATED,
        ),
        DeclarationsSanitizedLifecycleFactV1(
            fact_id="event-filed",
            work_unit_id=work_unit_id,
            occurred_at=_NOW,
            kind=DeclarationsLifecycleKind.FILED,
        ),
    )
    return project_declarations_workspace(
        operation=operation,
        bucket_id=_BUCKET,
        work_units=build_work_unit_catalogue((unit,)),
        calculation_revisions=CalculationRevisionCatalogue(
            revisions={
                filed_revision_id: filed_revision,
                draft_revision_id: draft_revision,
                later_draft_revision_id: later_draft_revision,
            }
        ),
        filing_records=ModeloRecordCatalogue(records={filing_record_id: filing}),
        lifecycle_facts=lifecycle,
        zone_observations=observations,
    )


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=lookup_action(action_id).action_id)


def _controller(
    projection: DeclarationsWorkspaceProjectionV1,
    context: TuiScreenContextV1 | None = None,
    *,
    modelo_workspace_factory: ModeloWorkspaceScreenFactoryV1 | None = None,
    revision_handoff: RevisionHandoffV1 | None = None,
    filing_handoff: FilingHandoffV1 | None = None,
    work_create_handoff: ModeloWorkCreateHandoffV1 | None = None,
    creation_targets: tuple[DeclarationTarget, ...] = (),
) -> DeclarationsWorkspaceController:
    return DeclarationsWorkspaceController(
        context or TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        DeclarationsWorkspaceWiringV1(
            work_action=_action("operator.modelo.work.list"),
            revisions_action=_action("operator.modelo.work.revisions"),
            filing_action=_action("operator.modelo.filing_record.list"),
            modelo_workspace_factory=modelo_workspace_factory,
            revision_handoff=revision_handoff,
            filing_handoff=filing_handoff,
            work_create_handoff=work_create_handoff,
            creation_targets=creation_targets,
        ),
    )


async def _select_creation(pilot: Pilot[None], modelo: str, period: Period) -> None:
    """Choose both registry-backed steps with explicit keyboard confirmation."""
    await pilot.press("plus")
    await pilot.pause()
    picker = pilot.app.screen
    assert isinstance(picker, NewDeclarationPicker)
    picker.query_one("#declaration-picker-all", Button).press()
    await pilot.pause()
    table = picker.query_one("#declaration-picker-table", DataTable)
    table.move_cursor(row=next(i for i, row in enumerate(table.ordered_rows) if row.key.value == modelo))
    table.focus()
    await pilot.press("enter")
    await pilot.pause()
    assert picker.modelo == modelo
    assert picker.query_one("#declaration-picker-create", Button).disabled
    table.move_cursor(row=next(i for i, target in enumerate(picker.visible_targets) if target.period == period))
    await pilot.press("enter")
    await pilot.pause()
    assert picker.selected == DeclarationTarget(modelo, period)
    assert pilot.app.focused is picker.query_one("#declaration-picker-create", Button)
    await pilot.press("enter")
    await pilot.pause()


def _select_declaration(table: DataTable[str], identity: str) -> None:
    """Select a semantic declaration row after the group headers."""
    table.move_cursor(row=next(i for i, row in enumerate(table.ordered_rows) if row.key.value == identity))
    table.focus()


@pytest.mark.asyncio
async def test_declarations_create_selects_only_supported_targets_and_reopens_exact_work(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    targets = declaration_targets(authority_operation)
    target = DeclarationTarget("111", Period.from_year_and_code(2025, "2T"))
    assert target in targets
    calls: list[tuple[str, int, Period]] = []

    def create(modelo: str, year: int, period: Period) -> ModeloWorkCreateResultV1:
        calls.append((modelo, year, period))
        return ModeloWorkCreateResultV1(reused=len(calls) > 1)

    screen = DeclarationsOverviewScreen(
        _controller(
            _projection(authority_operation),
            work_create_handoff=create,
            creation_targets=targets,
        )
    )
    async with ScreenHostApp(screen).run_test(size=(100, 42)) as pilot:
        await pilot.pause()
        await pilot.press("plus")
        await pilot.pause()
        picker = pilot.app.screen
        assert isinstance(picker, NewDeclarationPicker)
        assert tuple(row.key.value for row in picker.query_one(DataTable).ordered_rows) == ("130",)
        assert picker.query_one("#declaration-picker-create", Button).disabled
        assert not picker.query(Input)
        await pilot.press("escape")
        await pilot.pause()
        assert calls == []
        for _ in range(2):
            await _select_creation(pilot, target.modelo, target.period)
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
        assert calls == [("111", 2025, target.period)] * 2
        notice = str(screen.query_one("#declarations-work-create-notice", Static).render())
        assert "Modelo 111" in notice
        assert "2025" in notice
        assert tr("tui.declarations.work_create.reused", address="")[:10] in notice


@pytest.mark.asyncio
async def test_declarations_create_keeps_the_submitted_address_and_refuses_a_second_busy_write(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    release = threading.Event()
    calls: list[tuple[str, int, Period]] = []

    def create(modelo: str, year: int, period: Period) -> ModeloWorkCreateResultV1:
        calls.append((modelo, year, period))
        assert release.wait(timeout=10)
        return ModeloWorkCreateResultV1(reused=False)

    screen = DeclarationsOverviewScreen(
        _controller(
            _projection(authority_operation),
            work_create_handoff=create,
            creation_targets=declaration_targets(authority_operation),
        )
    )
    async with ScreenHostApp(screen).run_test(size=(100, 42)) as pilot:
        await pilot.pause()
        try:
            await _select_creation(pilot, "111", Period.from_year_and_code(2025, "2T"))
            assert len(calls) == 1
            await pilot.press("plus")
            screen.query_one("#declarations-new", Button).press()
            await pilot.pause()
            assert pilot.app.screen is screen
            assert len(calls) == 1
        finally:
            release.set()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        notice = str(screen.query_one("#declarations-work-create-notice", Static).render())
    assert calls == [("111", 2025, Period.from_year_and_code(2025, "2T"))]
    assert "Modelo 111" in notice
    assert "Modelo 115" not in notice


@pytest.mark.asyncio
async def test_declarations_create_shows_the_application_refusal_as_itself(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    def create(modelo: str, year: int, period: Period) -> ModeloWorkCreateResultV1:
        raise ModeloLifecycleActionUnavailableError(
            translated_message="tui.declarations.work_create.refusal.not_applicable",
            context={"modelo": modelo, "reason": "synthetic-reason"},
        )

    screen = DeclarationsOverviewScreen(
        _controller(
            _projection(authority_operation),
            work_create_handoff=create,
            creation_targets=declaration_targets(authority_operation),
        )
    )
    async with ScreenHostApp(screen).run_test(size=(100, 42)) as pilot:
        await pilot.pause()
        await _select_creation(pilot, "200", Period.from_year_and_code(2025, "0A"))
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        notice = str(screen.query_one("#declarations-work-create-notice", Static).render())
    assert notice == tr("tui.declarations.work_create.refusal.not_applicable", modelo="200", reason="synthetic-reason")
    assert "--allow-not-applicable" not in notice


def _copy(screen: Screen[None]) -> str:
    values = [str(widget.render()) for widget in screen.query(Static)]
    values.extend(
        str(cell)
        for table in screen.query(DataTable)
        for row in range(table.row_count)
        for cell in table.get_row_at(row)
    )
    return "\n".join(values)


def test_closed_routes_and_factory_require_exact_catalogue_actions(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    assert tuple(route.destination for route in DECLARATIONS_ROUTES) == (
        "declarations.overview",
        "declarations.revisions",
        "declarations.filing_history",
        "declarations.calendar",
        "declarations.modelo_workspace",
    )
    factory = declarations_screen_factory(
        _projection(authority_operation),
        DeclarationsWorkspaceWiringV1(
            work_action=_action("operator.modelo.work.list"),
            revisions_action=_action("operator.modelo.work.revisions"),
            filing_action=_action("operator.modelo.filing_record.list"),
        ),
    )
    assert isinstance(factory(TuiScreenContextV1(destination="workbench.declarations")), DeclarationsOverviewScreen)
    with pytest.raises(ValueError, match="another application door"):
        declarations_screen_factory(
            _projection(authority_operation),
            DeclarationsWorkspaceWiringV1(
                work_action=_action("operator.modelo.work.revisions"),
                revisions_action=_action("operator.modelo.work.revisions"),
                filing_action=_action("operator.modelo.filing_record.list"),
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "screen_type",
    (DeclarationsOverviewScreen, DeclarationsRevisionsScreen, DeclarationsFilingHistoryScreen),
)
async def test_each_screen_has_four_targets_one_outer_scroll_and_no_overflow(
    screen_type: type, authority_operation: PinnedAuthorityOperation
) -> None:
    screen = screen_type(_controller(_projection(authority_operation)))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        if isinstance(screen, DeclarationsOverviewScreen):
            assert {button.id for button in screen.query(Button)} == {
                "declarations-new",
                "declarations-revisions",
                "declarations-filings",
                "declarations-calendar",
            }
        else:
            assert screen.query_one("#declarations-navigation", DataTable).row_count == 5
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(widget for widget in screen.walk_children() if widget.display and widget.show_vertical_scrollbar)
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "declarations-page" for owner in owners)


@pytest.mark.asyncio
async def test_semantic_selection_uses_exact_projected_identity_and_typed_callbacks(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _projection(authority_operation)
    selected: list[object] = []
    screen = DeclarationsRevisionsScreen(_controller(projection, revision_handoff=selected.append))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-revisions", DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert len(selected) == 1
        assert selected[0] is screen.controller.projection.calculation_revisions[0]
        assert screen.selected_calculation_revision_id == projection.calculation_revisions[0].calculation_revision_id
        rendered = _copy(screen)
        assert all(row.work_unit_id not in rendered for row in projection.declarations)
        assert all(row.calculation_revision_id not in rendered for row in projection.calculation_revisions)
        assert all(row.filing_record_id not in rendered for row in projection.filings)
        assert "Modelo 130" in rendered


@pytest.mark.asyncio
async def test_focus_restores_by_calculation_revision_identity_not_registry_revision_or_position(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _projection(authority_operation)
    revision_id = projection.calculation_revisions[-1].calculation_revision_id
    context = TuiScreenContextV1(
        destination="workbench.declarations",
        focus=TuiFocusIdentityV1(
            destination="workbench.declarations",
            semantic_key="declarations.calculation_revision",
            restore_token=revision_id,
        ),
    )
    screen = DeclarationsRevisionsScreen(_controller(projection, context))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-revisions", DataTable)
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == revision_id


@pytest.mark.asyncio
async def test_unavailable_is_refusal_empty_is_measured_and_missing_handoff_refuses(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    controller = _controller(
        _projection(authority_operation, unavailable=DeclarationsWorkspaceZone.CALCULATION_REVISIONS)
    )
    unavailable = resolve_declarations_screen(controller, controller.target("declarations.revisions"))
    assert isinstance(unavailable, DeclarationsUnavailableScreen)
    empty = DeclarationsOverviewScreen(_controller(_projection(authority_operation, empty=True)))
    app = ScreenHostApp[None](empty)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert tr("tui.declarations.list.empty") in _copy(empty)
    screen = DeclarationsOverviewScreen(_controller(_projection(authority_operation)))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-list", DataTable)
        _select_declaration(table, screen.controller.projection.declarations[0].work_unit_id)
        await pilot.press("enter")
        assert tr("tui.declarations.refusal.handoff") in _copy(screen)


class _ModeloChild(Screen[None]):
    @override
    def compose(self) -> ComposeResult:
        """Render an identifiable injected child."""
        yield Static("modelo child", id="modelo-child")


@pytest.mark.asyncio
async def test_modelo_workspace_route_opens_exact_selected_factory_child_and_restores_focus(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _projection(authority_operation)
    calls: list[object] = []
    child = _ModeloChild()

    def factory(declaration: DeclarationsWorkspaceDeclarationRefV1) -> Screen[None]:
        calls.append(declaration)
        return child

    controller = _controller(projection, modelo_workspace_factory=factory)
    launcher = resolve_declarations_screen(controller, controller.target("declarations.modelo_workspace"))
    assert launcher.id == "declarations-modelo-workspace-launcher-screen"
    root = _Root()
    async with root.run_test(size=(80, 24)) as pilot:
        await root.push_screen(launcher)
        await pilot.pause()
        table = launcher.query_one("#declarations-list", DataTable)
        _select_declaration(table, projection.declarations[0].work_unit_id)
        await pilot.press("enter")
        await pilot.pause()
        assert calls == [projection.declarations[0]]
        assert root.screen is child
        child.dismiss(None)
        await pilot.pause()
        assert root.screen is launcher
        assert root.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == projection.declarations[0].work_unit_id


@pytest.mark.asyncio
async def test_history_renders_filing_and_sanitized_lifecycle_in_chronological_semantic_rows(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _projection(authority_operation)
    screen = DeclarationsFilingHistoryScreen(_controller(projection))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-filings", DataTable)
        history_state = next(
            state for state in projection.zones if state.zone is DeclarationsWorkspaceZone.FILING_HISTORY
        )
        assert history_state.item_count == table.row_count == 3
        assert table.row_count == len(projection.filings) + len(projection.lifecycle) == 3
        keys = tuple(str(row.key.value) for row in table.ordered_rows)
        assert set(keys[:2]) == {
            "lifecycle:event-filed",
            f"filing:{projection.filings[0].filing_record_id}",
        }
        assert keys[-1] == "lifecycle:event-created"
        assert f"filing:{projection.filings[0].filing_record_id}" in keys
        table.move_cursor(row=keys.index("lifecycle:event-filed"))
        table.focus()
        await pilot.press("enter")
        assert screen.selected_lifecycle_fact_id == "event-filed"
        rendered = _copy(screen)
        assert "event-filed" not in rendered
        assert "private" not in rendered.lower()


@pytest.mark.asyncio
async def test_revision_and_filing_rows_render_exact_chronology_and_independent_axes(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _projection(authority_operation)
    selected: list[object] = []
    revisions = DeclarationsRevisionsScreen(_controller(projection, revision_handoff=selected.append))
    revision_app = ScreenHostApp[None](revisions)
    async with revision_app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = revisions.query_one("#declarations-revisions", DataTable)
        assert table.row_count == 3
        rows = tuple(tuple(str(cell) for cell in table.get_row_at(index)) for index in range(3))
        assert len(set(rows)) == 3
        assert all("03/09/2026" in row[1] and "UTC" in row[1] for row in rows)
        assert {row[-2:] for row in rows} == {
            (tr("tui.declarations.value.yes"), tr("tui.declarations.value.yes")),
            (tr("tui.declarations.value.no"), tr("tui.declarations.value.no")),
        }
        drafts = tuple(row for row in projection.calculation_revisions if not row.is_current and not row.is_filed)
        assert len(drafts) == 2
        displayed_draft_times = tuple(str(table.get_row(row.calculation_revision_id)[1]) for row in drafts)
        assert displayed_draft_times == ("03/09/2026 09:15 UTC", "03/09/2026 09:45 UTC")
        selected_revision = drafts[-1]
        selected_index = next(
            index
            for index, table_row in enumerate(table.ordered_rows)
            if table_row.key.value == selected_revision.calculation_revision_id
        )
        table.move_cursor(row=selected_index)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert selected == [selected_revision]
        assert revisions.selected_calculation_revision_id == selected_revision.calculation_revision_id
    filings = DeclarationsFilingHistoryScreen(_controller(projection))
    filing_app = ScreenHostApp[None](filings)
    async with filing_app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = filings.query_one("#declarations-filings", DataTable)
        filing_key = f"filing:{projection.filings[0].filing_record_id}"
        row = tuple(str(cell) for cell in table.get_row(filing_key))
        assert row[1] == "03/09/2026 10:00 UTC"
        assert row[2] == tr("tui.declarations.filing_state.vigente")
        assert row[3] == tr("tui.declarations.confirmation.confirmada")
        assert row[4] == tr("tui.declarations.evidence.aeat_justificante_pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_real_locales_change_copy_without_changing_semantic_rows(
    locale: OutputLanguage, authority_operation: PinnedAuthorityOperation
) -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_output_language=locale.value):
        screens = (
            DeclarationsOverviewScreen(_controller(_projection(authority_operation))),
            DeclarationsRevisionsScreen(_controller(_projection(authority_operation))),
            DeclarationsFilingHistoryScreen(_controller(_projection(authority_operation))),
        )
        filing_copy = ""
        filing_keys: tuple[object, ...] = ()
        for screen, expected in zip(screens, _EXPECTED[locale][:3], strict=True):
            app = ScreenHostApp[None](screen)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rendered = _copy(screen)
                assert expected in rendered
                assert "tui.declarations." not in rendered
                assert "work_unit" not in rendered.lower()
                if not isinstance(screen, DeclarationsOverviewScreen):
                    assert tuple(
                        row.key.value for row in screen.query_one("#declarations-navigation", DataTable).ordered_rows
                    ) == tuple(route.destination for route in DECLARATIONS_ROUTES)
                else:
                    assert not screen.query("#declarations-navigation")
                if isinstance(screen, DeclarationsFilingHistoryScreen):
                    filing_copy = rendered
                    filing_keys = tuple(
                        row.key.value for row in screen.query_one("#declarations-filings", DataTable).ordered_rows
                    )
        assert _EXPECTED[locale][3] in filing_copy
        assert _EXPECTED[locale][4] in filing_copy
        assert "03/09/2026 10:00 UTC" in filing_copy
        assert filing_keys == (
            f"filing:{screens[-1].controller.projection.filings[0].filing_record_id}",
            "lifecycle:event-filed",
            "lifecycle:event-created",
        )


class _Root(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield Static("root", id="root")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
async def test_initial_grouped_controls_remain_visible_above_the_scrolling_attention_rows(
    locale: OutputLanguage, theme: str, size: tuple[int, int]
) -> None:
    from .....core.config import override_settings

    workspace, calendar = portfolio_projection()
    controller = _controller(workspace)
    controller.calendar_projection = calendar
    with override_settings(cadrumo_output_language=locale.value):
        screen = DeclarationsOverviewScreen(controller)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await pilot.pause()
            search = screen.query_one("#declarations-search", Input)
            context = screen.query_one("#declarations-list-context", Static)
            page = screen.query_one("#declarations-page", VerticalScroll)
            table = screen.query_one("#declarations-list", DataTable)
            assert app.focused is table
            assert table.ordered_rows[table.cursor_row].key.value == "group:attention"
            assert table.region.y >= page.region.y
            assert table.region.y + table.header_height < page.region.bottom
            for control in (search, context):
                assert control.visible and control.display
                assert screen.region.contains_region(control.region)
                assert control.region.y >= screen.query_one(".cadrumo-banner", Static).region.bottom
                assert control.region.bottom <= page.region.y
            initial_regions = (search.region, context.region)
            assert tr("tui.declarations.list.filter.all") in str(context.render())
            assert tr("tui.declarations.list.sort.deadline") in str(context.render())
            assert page.max_scroll_y > 0
            page.scroll_end(animate=False)
            await pilot.pause()
            assert page.scroll_y > 0
            assert (search.region, context.region) == initial_regions
            assert screen.region.contains_region(search.region)
            assert screen.region.contains_region(context.region)
            await pilot.press("/")
            await pilot.pause()
            assert app.focused is search
            assert (search.region, context.region) == initial_regions
            assert geometry_band(app, size[0]) == []
            owners = tuple(
                widget
                for widget in screen.walk_children()
                if isinstance(widget, Widget) and widget.display and widget.show_vertical_scrollbar
            )
            assert owners == (page,)


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_grouped_keyboard_filter_search_sort_and_fold_preserve_declaration_identities(
    locale: OutputLanguage, authority_operation: PinnedAuthorityOperation
) -> None:
    from .....core.config import override_settings

    original = _projection(authority_operation)
    base = original.declarations[0]
    declarations = tuple(
        base.model_copy(
            update={
                "work_unit_id": digit * 64,
                "modelo": modelo,
                "has_current_filing": False,
                "summary": DeclarationSummary(
                    state=DeclarationSummaryState.CALCULATED,
                    result=None
                    if value is None
                    else ModeloFormResult(
                        casilla_id=_CASILLA,
                        box="01",
                        value=Decimal(value),
                        direction=ModeloFormResultDirection.NIL if value == "0" else ModeloFormResultDirection.TO_PAY,
                    ),
                ),
            }
        )
        for digit, modelo, value in (("a", "303", "100"), ("b", "130", "0"), ("c", "111", None))
    )
    projection = original.model_copy(update={"declarations": declarations})
    with override_settings(cadrumo_output_language=locale.value):
        screen = DeclarationsOverviewScreen(_controller(projection))
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            table = screen.query_one("#declarations-list", DataTable)

            def local_keys() -> tuple[str, ...]:
                return tuple(
                    str(row.key.value) for row in table.ordered_rows if not str(row.key.value).startswith("group:")
                )

            assert local_keys() == ("c" * 64, "b" * 64, "a" * 64)
            await pilot.press("s", "s")
            assert local_keys() == ("b" * 64, "a" * 64, "c" * 64)
            assert "0,00" in _copy(screen) or "0.00" in _copy(screen)
            assert "100,00" in _copy(screen) or "100.00" in _copy(screen)
            assert not any(identity in _copy(screen) for identity in local_keys())
            _select_declaration(table, "group:in_progress")
            await pilot.press("enter")
            assert local_keys() == ()
            _select_declaration(table, "group:in_progress")
            await pilot.press("enter")
            assert local_keys() == ("b" * 64, "a" * 64, "c" * 64)
            await pilot.press("f")
            assert local_keys() == ()
            assert tr("tui.declarations.list.filter.attention") in _copy(screen)
            for _ in range(4):
                await pilot.press("f")
            assert local_keys() == ("b" * 64, "a" * 64, "c" * 64)
            await pilot.press("/")
            search = screen.query_one("#declarations-search", Input)
            assert app.focused is search
            await pilot.press("1", "3", "0")
            assert local_keys() == ("b" * 64,)
            name_term = {
                OutputLanguage.ES: "estimacion",
                OutputLanguage.EN: "direct",
                OutputLanguage.CA: "estimacio",
                OutputLanguage.HU: "kozvetlen",
            }[locale]
            await pilot.press("space", *tuple(name_term), "space", "2", "0", "2", "6")
            assert local_keys() == ("b" * 64,)
            await pilot.press("backspace", "5")
            assert local_keys() == ()
            await pilot.press("end", "ctrl+u")
            await pilot.pause()
            assert len(local_keys()) == 3
            table.focus()
            assert geometry_band(app, 80) == []
            assert table.max_scroll_x == 0
            assert "tui.declarations." not in _copy(screen)


@pytest.mark.asyncio
async def test_creation_result_opens_the_exact_new_declaration_and_refreshes_semantic_focus(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    original = _projection(authority_operation)
    created = original.declarations[0].model_copy(
        update={
            "work_unit_id": "e" * 64,
            "period": Period.from_year_and_code(2026, "2T"),
            "has_current_calculation": False,
            "has_current_filing": False,
            "summary": DeclarationSummary(state=DeclarationSummaryState.DRAFT),
        }
    )
    latest = original.model_copy(update={"declarations": (*original.declarations, created)})
    calls: list[object] = []
    child = _ModeloChild()
    created_now = False

    def create(modelo: str, year: int, period: Period) -> ModeloWorkCreateResultV1:
        nonlocal created_now
        assert (modelo, year, period) == ("130", 2026, created.period)
        created_now = True
        return ModeloWorkCreateResultV1(reused=False, declaration=created)

    def factory(declaration: DeclarationsWorkspaceDeclarationRefV1) -> Screen[None]:
        calls.append(declaration)
        return child

    controller = _controller(
        original,
        modelo_workspace_factory=factory,
        work_create_handoff=create,
        creation_targets=declaration_targets(authority_operation),
    )
    controller.refresh_data = lambda: (latest if created_now else original, None)
    screen = DeclarationsOverviewScreen(controller)
    root = _Root()
    async with root.run_test(size=(80, 24)) as pilot:
        await root.push_screen(screen)
        await pilot.pause()
        await _select_creation(pilot, "130", created.period)
        await root.workers.wait_for_complete()
        await pilot.pause()
        assert calls == [created]
        assert root.screen is child
        child.dismiss(None)
        await pilot.pause()
        table = screen.query_one("#declarations-list", DataTable)
        assert root.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == created.work_unit_id


@pytest.mark.asyncio
async def test_escape_dismisses_only_child_and_returns_to_generic_root(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    root = _Root()
    screen = DeclarationsOverviewScreen(_controller(_projection(authority_operation)))
    async with root.run_test(size=(80, 24)) as pilot:
        await root.push_screen(screen)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert root.is_running
        assert root.query_one("#root", Static).display


def test_declarations_tui_has_no_io_adapter_cli_reader_or_raw_payload_surface() -> None:
    package = Path(__file__).parents[1]
    production = tuple(path for path in package.glob("*.py") if path.name != "__init__.py")
    assert production, (
        f"the sweep of {package} matched no production module; a walk that reads nothing "
        "reports no forbidden adapter or CLI import because it reads no import at all"
    )
    trees = tuple(ast.parse(path.read_text(encoding="utf-8")) for path in production)
    imports = {node.module or "" for tree in trees for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for tree in trees for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("entrypoints.cli" in name or "adapters" in name or "repositories" in name for name in imports)
    assert not {"open", "read", "write", "read_text", "write_text", "print"} & calls
    for path in production:
        text = path.read_text(encoding="utf-8")
        assert "member_nif" not in text
        assert "source_transaction_ids" not in text
        assert "input_values_by_casilla_id" not in text
