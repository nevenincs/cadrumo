"""Contract, interaction, locale, geometry, and security tests."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Static

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
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.casilla_id import validated_casilla_id
from .....core.external_constants import OutputLanguage
from .....core.period import Period
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...components.host import ScreenHostApp
from ...devtools.frame import geometry_band
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..controller import DeclarationsWorkspaceController, declarations_copy
from ..filing_history import DeclarationsFilingHistoryScreen
from ..models import FilingHandoffV1, ModeloWorkspaceScreenFactoryV1, RevisionHandoffV1
from ..overview import DeclarationsOverviewScreen
from ..revisions import DeclarationsRevisionsScreen
from ..routes import (
    DECLARATIONS_ROUTES,
    DeclarationsUnavailableScreen,
    declarations_screen_factory,
    resolve_declarations_screen,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_BUCKET = "11111111-1111-4111-8111-111111111111"
_CASILLA = validated_casilla_id("01")
_EXPECTED = {
    OutputLanguage.ES: (
        "Resumen de declaraciones",
        "Revisiones de cálculo",
        "Historial de presentaciones",
        "El estado local de presentación y la evidencia observada de la AEAT son hechos distintos.",
        "Presentación registrada localmente",
    ),
    OutputLanguage.EN: (
        "Declarations overview",
        "Calculation revisions",
        "Filing history",
        "Local filing status and externally observed AEAT evidence are separate facts.",
        "Filing recorded locally",
    ),
    OutputLanguage.CA: (
        "Resum de declaracions",
        "Revisions de càlcul",
        "Historial de presentacions",
        "L'estat local de presentació i l'evidència observada de l'AEAT són fets separats.",
        "Presentació registrada localment",
    ),
    OutputLanguage.HU: (
        "Bevallások áttekintése",
        "Számítási változatok",
        "Benyújtási előzmények",
        "A helyi benyújtási állapot és a megfigyelt AEAT-bizonyíték külön tény.",
        "Benyújtás helyben rögzítve",
    ),
}


def _projection(
    *, unavailable: DeclarationsWorkspaceZone | None = None, empty: bool = False
) -> DeclarationsWorkspaceProjectionV1:
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
        revision_id="2026",
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
        revision_id="2026",
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
        aeat_accepted=True,
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
        bucket_id=_BUCKET,
        work_units=WorkUnitCatalogue.from_work_units((unit,)),
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
) -> DeclarationsWorkspaceController:
    return DeclarationsWorkspaceController(
        context or TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        work_action=_action("operator.modelo.work.list"),
        revisions_action=_action("operator.modelo.work.revisions"),
        filing_action=_action("operator.modelo.filing_record.list"),
        modelo_workspace_factory=modelo_workspace_factory,
        revision_handoff=revision_handoff,
        filing_handoff=filing_handoff,
    )


def _copy(screen: Screen[None]) -> str:
    values = [str(widget.render()) for widget in screen.query(Static)]
    values.extend(
        str(cell)
        for table in screen.query(DataTable)
        for row in range(table.row_count)
        for cell in table.get_row_at(row)
    )
    return "\n".join(values)


def test_closed_routes_and_factory_require_exact_catalogue_actions() -> None:
    assert tuple(route.destination for route in DECLARATIONS_ROUTES) == (
        "declarations.overview",
        "declarations.revisions",
        "declarations.filing_history",
        "declarations.modelo_workspace",
    )
    factory = declarations_screen_factory(
        _projection(),
        work_action=_action("operator.modelo.work.list"),
        revisions_action=_action("operator.modelo.work.revisions"),
        filing_action=_action("operator.modelo.filing_record.list"),
    )
    assert isinstance(factory(TuiScreenContextV1(destination="workbench.declarations")), DeclarationsOverviewScreen)
    with pytest.raises(ValueError, match="another application door"):
        declarations_screen_factory(
            _projection(),
            work_action=_action("operator.modelo.work.revisions"),
            revisions_action=_action("operator.modelo.work.revisions"),
            filing_action=_action("operator.modelo.filing_record.list"),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "screen_type",
    (DeclarationsOverviewScreen, DeclarationsRevisionsScreen, DeclarationsFilingHistoryScreen),
)
async def test_each_screen_has_four_targets_one_outer_scroll_and_no_overflow(screen_type: type) -> None:
    screen = screen_type(_controller(_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert screen.query_one("#declarations-navigation", DataTable).row_count == 4
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(widget for widget in screen.walk_children() if widget.display and widget.show_vertical_scrollbar)
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "declarations-page" for owner in owners)


@pytest.mark.asyncio
async def test_semantic_selection_uses_exact_projected_identity_and_typed_callbacks() -> None:
    projection = _projection()
    selected: list[object] = []
    screen = DeclarationsRevisionsScreen(
        _controller(projection, revision_handoff=selected.append)
    )
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
async def test_focus_restores_by_calculation_revision_identity_not_registry_revision_or_position() -> None:
    projection = _projection()
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
async def test_unavailable_is_refusal_empty_is_measured_and_missing_handoff_refuses() -> None:
    controller = _controller(_projection(unavailable=DeclarationsWorkspaceZone.CALCULATION_REVISIONS))
    unavailable = resolve_declarations_screen(controller, controller.target("declarations.revisions"))
    assert isinstance(unavailable, DeclarationsUnavailableScreen)
    empty = DeclarationsOverviewScreen(_controller(_projection(empty=True)))
    app = ScreenHostApp[None](empty)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert declarations_copy("tui.declarations.empty") in _copy(empty)
    screen = DeclarationsOverviewScreen(_controller(_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-list", DataTable)
        table.focus()
        await pilot.press("enter")
        assert declarations_copy("tui.declarations.refusal.handoff") in _copy(screen)


class _ModeloChild(Screen[None]):
    @override
    def compose(self) -> ComposeResult:
        """Render an identifiable injected child."""
        yield Static("modelo child", id="modelo-child")


@pytest.mark.asyncio
async def test_modelo_workspace_route_opens_exact_selected_factory_child_and_restores_focus() -> None:
    projection = _projection()
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
        table.focus()
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
async def test_history_renders_filing_and_sanitized_lifecycle_in_chronological_semantic_rows() -> None:
    projection = _projection()
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
async def test_revision_and_filing_rows_render_exact_chronology_and_independent_axes() -> None:
    projection = _projection()
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
            (declarations_copy("tui.declarations.value.yes"), declarations_copy("tui.declarations.value.yes")),
            (declarations_copy("tui.declarations.value.no"), declarations_copy("tui.declarations.value.no")),
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
        assert row[2] == declarations_copy("tui.declarations.filing_state.vigente")
        assert row[3] == declarations_copy("tui.declarations.value.yes")
        assert row[4] == declarations_copy("tui.declarations.evidence.aeat_justificante_pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_real_locales_change_copy_without_changing_semantic_rows(locale: OutputLanguage) -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_output_language=locale.value):
        screens = (
            DeclarationsOverviewScreen(_controller(_projection())),
            DeclarationsRevisionsScreen(_controller(_projection())),
            DeclarationsFilingHistoryScreen(_controller(_projection())),
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
                assert tuple(row.key.value for row in screen.query_one("#declarations-navigation", DataTable).ordered_rows) == tuple(
                    route.destination for route in DECLARATIONS_ROUTES
                )
                if isinstance(screen, DeclarationsFilingHistoryScreen):
                    filing_copy = rendered
                    filing_keys = tuple(
                        row.key.value
                        for row in screen.query_one("#declarations-filings", DataTable).ordered_rows
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
async def test_escape_dismisses_only_child_and_returns_to_generic_root() -> None:
    root = _Root()
    screen = DeclarationsOverviewScreen(_controller(_projection()))
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
    trees = tuple(ast.parse(path.read_text(encoding="utf-8")) for path in production)
    imports = {
        node.module or ""
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
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
