"""Real canonical-record and Textual-pilot proof for modelo work review."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import cast, get_args

import pytest
import yaml
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    DataTable,
    Input,
    OptionList,
    RadioSet,
    Select,
    SelectionList,
    Static,
)

from ......application.modelo.work_review_projection import ModeloWorkOriginAnomaly
from ......core import EstadoCasillaOficial, ModeloWorkProgressState, OperatorActionAxis
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ......domain.calculations.registry import InputKind, RelationConsumptionChannel
from ......domain.filing import ModeloValueKind
from ......domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ......tests.locales_root_fixture import locales_root_scope
from ......tests.modelo_work_review import build_real_modelo_work_review
from ....components.theme import (
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT_THEME_NAME,
)
from ....components.widgets import ContentScroll
from ..work_review import (
    ModeloWorkReviewApp,
    ModeloWorkReviewScreen,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_modelo_view_namespace_is_inert_and_review_types_have_one_defining_module() -> None:
    """The view package cannot become a second public screen home."""
    namespace = importlib.import_module("cadrumo.entrypoints.tui.modelo.view")

    assert namespace.__all__ == ()
    assert "ModeloWorkReviewApp" not in vars(namespace)
    assert "ModeloWorkReviewScreen" not in vars(namespace)
    assert ModeloWorkReviewApp.__module__ == "cadrumo.entrypoints.tui.modelo.view.work_review"
    assert ModeloWorkReviewScreen.__module__ == "cadrumo.entrypoints.tui.modelo.view.work_review"


def _cells(table: DataTable[str]) -> tuple[str, ...]:
    return tuple(str(cell) for row_index in range(table.row_count) for cell in table.get_row_at(row_index))


def _row_keys(table: DataTable[str]) -> tuple[str, ...]:
    """Read the canonical row identities in their current presentation order."""
    return tuple(key.value for key in table.rows if key.value is not None)


def _visible_in(widget: Widget, container: Widget) -> bool:
    """Whether the compositor places any part of a widget inside its host."""
    return (
        widget.region.right > container.region.x
        and widget.region.x < container.region.right
        and widget.region.bottom > container.region.y
        and widget.region.y < container.region.bottom
    )


def _option_prompts(chooser: Select[object]) -> tuple[str, ...]:
    """Return every prompt currently offered by one visible filter chooser."""
    option_list = chooser.query_one(OptionList)
    return tuple(str(option_list.get_option_at_index(index).prompt) for index in range(option_list.option_count))


def _enum_option_index(enum_type: type, member: object) -> int:
    """Return an enum member's visible index after the universal ``All`` option."""
    return list(enum_type).index(member) + 1


async def _choose_option(pilot, chooser: Select[object], option_index: int) -> None:
    """Choose a rendered option by its public closed-axis ordering."""
    chooser.action_show_overlay()
    await pilot.pause()
    prompts = _option_prompts(chooser)
    assert 0 < option_index < len(prompts), f"option index {option_index} is outside {prompts}"
    chooser.query_one(OptionList).highlighted = option_index
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_blocked_review_renders_all_canonical_grains_without_mutation_controls(tmp_path: Path) -> None:
    review = build_real_modelo_work_review(tmp_path, modelo="130", filing_year=2026, period_code="1T", blocked=True)
    app = ModeloWorkReviewApp(review)
    locale_root = tmp_path / "review-locales"
    locale_root.mkdir()
    localized_message = "INCIDENCIA LOCALIZADA EN CASILLA {casilla_id}"
    payload = yaml.safe_dump(
        {"application": {"modelo": {"findings": {"blocking_rule": localized_message}}}},
        allow_unicode=True,
    )
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (locale_root / f"{language}.yml").write_text(payload, encoding="utf-8")

    with locales_root_scope(locale_root), override_settings(cadrumo_output_language="es"):
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            screen = app.screen
            summary = str(screen.query_one("#modelo-review-summary-lines", Static).content)
            casillas = screen.query_one("#modelo-review-casillas-table", DataTable)
            findings = screen.query_one("#modelo-review-findings-table", DataTable)
            blockers = screen.query_one("#modelo-review-blockers-table", DataTable)

            assert review.progress.state is ModeloWorkProgressState.BLOCKED
            assert review.progress.denominator is not None
            assert str(review.progress.denominator.source_ref) in summary
            assert str(review.progress.denominator.registry_revision_id) in summary
            assert casillas.row_count == len(review.casillas)
            assert findings.row_count == len(review.findings) == 1
            assert blockers.row_count == len(review.blockers) == 1
            finding_cells = _cells(findings)
            assert review.findings[0].kind.value in finding_cells
            assert review.findings[0].expectation_id in finding_cells
            assert (
                tr(
                    review.findings[0].message_locale_key,
                    **review.findings[0].message_facts,
                )
                in finding_cells
            )
            assert review.findings[0].message_locale_key not in finding_cells
            assert review.blockers[0].axis is OperatorActionAxis.SUPPLY_MANUAL_INPUT
            assert review.blockers[0].axis.value in _cells(blockers)
            affected = next(row for row in review.casillas if row.blocked_by)
            affected_cells = tuple(str(cell) for cell in casillas.get_row(str(affected.casilla_id)))
            assert affected.declared_input_kind.value in affected_cells
            assert affected.realised_kind.value in " ".join(affected_cells)
            assert affected.blocked_by[0].native_code in " ".join(affected_cells)
            excluded_controls = (Input, SelectionList, Checkbox, RadioSet)
            assert not tuple(widget for control in excluded_controls for widget in screen.query(control))
            assert len(screen.query("#modelo-review-filters Select")) == 16


@pytest.mark.asyncio
async def test_facet_option_sets_render_every_canonical_closed_axis(tmp_path: Path) -> None:
    """Each filter offers the complete closed axis in operator-facing words."""
    review = build_real_modelo_work_review(tmp_path, modelo="130", filing_year=2026, period_code="1T", blocked=True)
    app = ModeloWorkReviewApp(review)

    enum_filters = (
        ("#modelo-review-filter-input-kind", InputKind, "input_kind"),
        ("#modelo-review-filter-binding-source", BindingSourceKind, "binding_source"),
        ("#modelo-review-filter-realised-kind", ModeloValueKind, "realised_kind"),
        ("#modelo-review-filter-origin-anomaly", ModeloWorkOriginAnomaly, "origin_anomaly"),
        ("#modelo-review-filter-estado-casilla-oficial", EstadoCasillaOficial, "estado_casilla_oficial"),
        ("#modelo-review-filter-casilla-blocker", OperatorActionAxis, "operator_action"),
        ("#modelo-review-filter-finding-kind", ModeloVerificationFindingKind, "finding_kind"),
        ("#modelo-review-filter-finding-severity", ModeloVerificationFindingSeverity, "finding_severity"),
        ("#modelo-review-filter-record-blocker", OperatorActionAxis, "operator_action"),
    )

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen = app.screen
        for selector, enum_type, axis in enum_filters:
            chooser = cast("Select[object]", screen.query_one(selector, Select))
            assert _option_prompts(chooser) == (
                tr("flows.modelo_review.filter.all"),
                *(tr(f"flows.modelo_review.filter.option.{axis}.{member.value}") for member in enum_type),
            )

        relation_chooser = cast("Select[object]", screen.query_one("#modelo-review-filter-relation-channel", Select))
        assert _option_prompts(relation_chooser) == (
            tr("flows.modelo_review.filter.all"),
            *(
                tr(f"flows.modelo_review.filter.option.relation_channel.{channel}")
                for channel in get_args(RelationConsumptionChannel)
            ),
        )

        for selector, expected_prompts in (
            (
                "#modelo-review-filter-binding-presence",
                (tr("flows.modelo_review.filter.present"), tr("flows.modelo_review.filter.absent")),
            ),
            (
                "#modelo-review-filter-formula-presence",
                (tr("flows.modelo_review.filter.present"), tr("flows.modelo_review.filter.absent")),
            ),
            (
                "#modelo-review-filter-relation-presence",
                (tr("flows.modelo_review.filter.present"), tr("flows.modelo_review.filter.absent")),
            ),
            (
                "#modelo-review-filter-origin-anomaly-presence",
                (tr("flows.modelo_review.filter.present"), tr("flows.modelo_review.filter.absent")),
            ),
            (
                "#modelo-review-filter-casilla-blocker-presence",
                (tr("flows.modelo_review.filter.present"), tr("flows.modelo_review.filter.absent")),
            ),
            (
                "#modelo-review-filter-binding-resolved",
                (tr("flows.modelo_review.filter.resolved"), tr("flows.modelo_review.filter.unresolved")),
            ),
        ):
            chooser = cast("Select[object]", screen.query_one(selector, Select))
            assert _option_prompts(chooser) == (tr("flows.modelo_review.filter.all"), *expected_prompts)


@pytest.mark.asyncio
async def test_m100_facets_project_exact_canonical_rows_and_reset_without_mutation(tmp_path: Path) -> None:
    review = build_real_modelo_work_review(tmp_path, modelo="100", filing_year=2024, period_code="0A")
    original_record = review.model_dump(mode="json")
    app = ModeloWorkReviewApp(review)

    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        screen = app.screen
        table = screen.query_one("#modelo-review-casillas-table", DataTable)
        original_rows = _row_keys(table)
        checks = (
            (
                "#modelo-review-filter-input-kind",
                _enum_option_index(InputKind, InputKind.COMPUTED),
                tuple(str(row.casilla_id) for row in review.casillas if row.declared_input_kind is InputKind.COMPUTED),
            ),
            (
                "#modelo-review-filter-binding-source",
                _enum_option_index(BindingSourceKind, BindingSourceKind.PROFILE),
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if any(binding.source is BindingSourceKind.PROFILE for binding in row.concrete_bindings)
                ),
            ),
            (
                "#modelo-review-filter-binding-presence",
                1,
                tuple(str(row.casilla_id) for row in review.casillas if row.concrete_bindings),
            ),
            (
                "#modelo-review-filter-binding-presence",
                2,
                tuple(str(row.casilla_id) for row in review.casillas if not row.concrete_bindings),
            ),
            (
                "#modelo-review-filter-formula-presence",
                1,
                tuple(str(row.casilla_id) for row in review.casillas if row.concrete_formula is not None),
            ),
            (
                "#modelo-review-filter-formula-presence",
                2,
                tuple(str(row.casilla_id) for row in review.casillas if row.concrete_formula is None),
            ),
            (
                "#modelo-review-filter-relation-presence",
                1,
                tuple(str(row.casilla_id) for row in review.casillas if row.relation_consumption),
            ),
            (
                "#modelo-review-filter-relation-presence",
                2,
                tuple(str(row.casilla_id) for row in review.casillas if not row.relation_consumption),
            ),
            (
                "#modelo-review-filter-relation-channel",
                get_args(RelationConsumptionChannel).index("primary_binding") + 1,
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if any("primary_binding" in relation.channels for relation in row.relation_consumption)
                ),
            ),
            (
                "#modelo-review-filter-origin-anomaly",
                _enum_option_index(ModeloWorkOriginAnomaly, ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN),
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if row.origin_anomaly is ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN
                ),
            ),
            (
                "#modelo-review-filter-origin-anomaly-presence",
                2,
                tuple(str(row.casilla_id) for row in review.casillas if row.origin_anomaly is None),
            ),
            (
                "#modelo-review-filter-estado-casilla-oficial",
                _enum_option_index(EstadoCasillaOficial, EstadoCasillaOficial.ADDRESSED),
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if row.estado_casilla_oficial is EstadoCasillaOficial.ADDRESSED
                ),
            ),
        )
        for selector, option_index, expected_rows in checks:
            chooser = cast("Select[object]", screen.query_one(selector, Select))
            await _choose_option(pilot, chooser, option_index)
            assert expected_rows
            assert len(expected_rows) < len(original_rows)
            assert _row_keys(table) == expected_rows
            chooser.clear()
            await pilot.pause()
            assert _row_keys(table) == original_rows

        resolved = cast("Select[object]", screen.query_one("#modelo-review-filter-binding-resolved", Select))
        await _choose_option(pilot, resolved, 2)
        expected_unresolved = tuple(
            str(row.casilla_id)
            for row in review.casillas
            if any(not binding.resolved for binding in row.concrete_bindings)
        )
        assert expected_unresolved
        assert _row_keys(table) == expected_unresolved
        resolved.clear()
        await pilot.pause()
        assert _row_keys(table) == original_rows

        input_kind = cast("Select[object]", screen.query_one("#modelo-review-filter-input-kind", Select))
        estado_casilla_oficial = cast(
            "Select[object]",
            screen.query_one("#modelo-review-filter-estado-casilla-oficial", Select),
        )
        expected_manual = tuple(
            str(row.casilla_id) for row in review.casillas if row.declared_input_kind is InputKind.MANUAL
        )
        expected_addressed = tuple(
            str(row.casilla_id)
            for row in review.casillas
            if row.estado_casilla_oficial is EstadoCasillaOficial.ADDRESSED
        )
        expected_intersection = tuple(
            str(row.casilla_id)
            for row in review.casillas
            if row.declared_input_kind is InputKind.MANUAL
            and row.estado_casilla_oficial is EstadoCasillaOficial.ADDRESSED
        )
        assert expected_manual
        assert expected_addressed
        assert expected_intersection
        assert set(expected_intersection) < set(expected_manual)
        assert set(expected_intersection) < set(expected_addressed)

        await _choose_option(pilot, input_kind, _enum_option_index(InputKind, InputKind.MANUAL))
        assert len(_row_keys(table)) == len(expected_manual)
        assert _row_keys(table) == expected_manual

        await _choose_option(
            pilot,
            estado_casilla_oficial,
            _enum_option_index(EstadoCasillaOficial, EstadoCasillaOficial.ADDRESSED),
        )
        assert len(_row_keys(table)) == len(expected_intersection)
        assert _row_keys(table) == expected_intersection

        input_kind.clear()
        await pilot.pause()
        assert len(_row_keys(table)) == len(expected_addressed)
        assert _row_keys(table) == expected_addressed

        screen.query_one("#modelo-review-filter-reset", Button).press()
        await pilot.pause()
        assert _row_keys(table) == original_rows
        assert all(chooser.selection is None for chooser in screen.query(Select))
        assert review.model_dump(mode="json") == original_record


@pytest.mark.asyncio
async def test_m130_realised_anomaly_finding_and_blocker_facets_bite_and_empty_truthfully(tmp_path: Path) -> None:
    review = build_real_modelo_work_review(
        tmp_path,
        modelo="130",
        filing_year=2026,
        period_code="1T",
        blocked=True,
        materialised=True,
    )
    original_record = review.model_dump(mode="json")
    app = ModeloWorkReviewApp(review)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen = app.screen
        casillas = screen.query_one("#modelo-review-casillas-table", DataTable)
        findings = screen.query_one("#modelo-review-findings-table", DataTable)
        blockers = screen.query_one("#modelo-review-blockers-table", DataTable)
        original_casillas = _row_keys(casillas)
        original_findings = _row_keys(findings)
        original_blockers = _row_keys(blockers)

        casilla_checks = (
            (
                "#modelo-review-filter-realised-kind",
                _enum_option_index(ModeloValueKind, ModeloValueKind.LITERAL),
                tuple(str(row.casilla_id) for row in review.casillas if row.realised_kind is ModeloValueKind.LITERAL),
            ),
            (
                "#modelo-review-filter-origin-anomaly",
                _enum_option_index(ModeloWorkOriginAnomaly, ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE),
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if row.origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
                ),
            ),
            (
                "#modelo-review-filter-origin-anomaly-presence",
                1,
                tuple(str(row.casilla_id) for row in review.casillas if row.origin_anomaly is not None),
            ),
            (
                "#modelo-review-filter-casilla-blocker",
                _enum_option_index(OperatorActionAxis, OperatorActionAxis.SUPPLY_MANUAL_INPUT),
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if any(blocker.axis is OperatorActionAxis.SUPPLY_MANUAL_INPUT for blocker in row.blocked_by)
                ),
            ),
            (
                "#modelo-review-filter-casilla-blocker-presence",
                1,
                tuple(str(row.casilla_id) for row in review.casillas if row.blocked_by),
            ),
        )
        for selector, option_index, expected_rows in casilla_checks:
            chooser = cast("Select[object]", screen.query_one(selector, Select))
            await _choose_option(pilot, chooser, option_index)
            assert expected_rows
            assert len(expected_rows) < len(original_casillas)
            assert _row_keys(casillas) == expected_rows
            chooser.clear()
            await pilot.pause()

        resolved = cast("Select[object]", screen.query_one("#modelo-review-filter-binding-resolved", Select))
        await _choose_option(pilot, resolved, 1)
        expected_resolved = tuple(
            str(row.casilla_id) for row in review.casillas if any(binding.resolved for binding in row.concrete_bindings)
        )
        assert expected_resolved
        assert _row_keys(casillas) == expected_resolved
        resolved.clear()

        finding_kind = cast("Select[object]", screen.query_one("#modelo-review-filter-finding-kind", Select))
        await _choose_option(
            pilot,
            finding_kind,
            _enum_option_index(ModeloVerificationFindingKind, ModeloVerificationFindingKind.BLOCKING_RULE),
        )
        assert findings.row_count == 1 < len(original_findings)
        assert review.findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
        finding_kind.clear()

        finding_severity = cast("Select[object]", screen.query_one("#modelo-review-filter-finding-severity", Select))
        await _choose_option(
            pilot,
            finding_severity,
            _enum_option_index(ModeloVerificationFindingSeverity, ModeloVerificationFindingSeverity.WARNING),
        )
        assert findings.row_count == 1 < len(original_findings)
        assert review.findings[1].severity is ModeloVerificationFindingSeverity.WARNING
        finding_severity.clear()

        record_blocker = cast("Select[object]", screen.query_one("#modelo-review-filter-record-blocker", Select))
        await _choose_option(
            pilot,
            record_blocker,
            _enum_option_index(OperatorActionAxis, OperatorActionAxis.SUPPLY_MANUAL_INPUT),
        )
        assert _row_keys(blockers) == original_blockers

        await _choose_option(
            pilot,
            cast("Select[object]", screen.query_one("#modelo-review-filter-realised-kind", Select)),
            _enum_option_index(ModeloValueKind, ModeloValueKind.DEFAULT),
        )
        await _choose_option(
            pilot,
            cast("Select[object]", screen.query_one("#modelo-review-filter-finding-kind", Select)),
            _enum_option_index(ModeloVerificationFindingKind, ModeloVerificationFindingKind.ADVISORY),
        )
        await _choose_option(
            pilot,
            cast("Select[object]", screen.query_one("#modelo-review-filter-record-blocker", Select)),
            _enum_option_index(OperatorActionAxis, OperatorActionAxis.RE_VERIFY),
        )
        assert casillas.row_count == findings.row_count == blockers.row_count == 0
        assert screen.query_one("#modelo-review-casillas-empty", Static).display
        assert screen.query_one("#modelo-review-findings-empty", Static).display
        assert screen.query_one("#modelo-review-blockers-empty", Static).display

        screen.query_one("#modelo-review-filter-reset", Button).press()
        await pilot.pause()
        assert _row_keys(casillas) == original_casillas
        assert _row_keys(findings) == original_findings
        assert _row_keys(blockers) == original_blockers
        assert all(chooser.selection is None for chooser in screen.query(Select))
        assert review.model_dump(mode="json") == original_record


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period_code"),
    [
        pytest.param("720", 2024, "0A", id="m720"),
        pytest.param("200", 2024, "0A", id="m200-2024"),
        pytest.param("100", 2024, "0A", id="m100-2024"),
        pytest.param("100", 2025, "0A", id="m100-2025"),
        pytest.param("349", 2025, "1T", id="m349"),
    ],
)
@pytest.mark.asyncio
async def test_named_outlier_review_renders_every_registry_casilla(
    tmp_path: Path,
    modelo: str,
    filing_year: int,
    period_code: str,
) -> None:
    review = build_real_modelo_work_review(
        tmp_path,
        modelo=modelo,
        filing_year=filing_year,
        period_code=period_code,
    )
    app = ModeloWorkReviewApp(review)

    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        screen = app.screen
        table = screen.query_one("#modelo-review-casillas-table", DataTable)
        summary = str(screen.query_one("#modelo-review-summary-lines", Static).content)
        assert table.row_count == len(review.casillas)
        assert table.row_count > 0
        assert str(review.registry_revision_id) in summary
        assert not screen.query("#modelo-review-findings-table")
        assert not screen.query("#modelo-review-blockers-table")


@pytest.mark.asyncio
async def test_undefined_progress_never_renders_a_manufactured_zero_denominator(tmp_path: Path) -> None:
    review = build_real_modelo_work_review(tmp_path, modelo="189", filing_year=2025, period_code="0A")
    app = ModeloWorkReviewApp(review)

    async with app.run_test(size=(120, 36)):
        summary = str(app.screen.query_one("#modelo-review-summary-lines", Static).content)
        progress_line = summary.splitlines()[-1]
        assert review.progress.state is ModeloWorkProgressState.UNDEFINED
        assert progress_line.endswith(ModeloWorkProgressState.UNDEFINED.value)
        assert "0/0" not in progress_line


@pytest.mark.asyncio
async def test_large_outlier_frame_scroll_focus_and_last_row_are_usable_at_three_sizes(tmp_path: Path) -> None:
    """The real M100 surface remains operable, not merely populated, at every target size."""
    review = build_real_modelo_work_review(tmp_path, modelo="100", filing_year=2024, period_code="0A")

    for size in ((80, 24), (120, 36), (160, 48)):
        app = ModeloWorkReviewApp(review)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            screen = app.screen
            header = screen.query_one("#modelo-review-header", Static)
            body = screen.query_one("#modelo-review-body", ContentScroll)
            table = screen.query_one("#modelo-review-casillas-table", DataTable)

            assert (screen.region.width, screen.region.height) == size
            assert header.region.x == 0 and header.region.y == 0
            assert header.region.width == size[0] and header.region.height == 1
            assert body.region.x == 0 and body.region.width == size[0]
            assert body.region.bottom <= screen.region.bottom
            assert _visible_in(table, body)
            assert screen.get_style_at(1, 0).bgcolor != screen.get_style_at(1, body.region.y + 1).bgcolor

            screen.set_focus(table)
            await pilot.pause()
            assert app.focused is table
            assert table.max_scroll_x > 0
            table.scroll_to(x=table.max_scroll_x, animate=False, immediate=True)
            await pilot.pause()
            assert table.scroll_x == table.max_scroll_x

            table.move_cursor(row=table.row_count - 1, column=len(table.columns) - 1, scroll=False)
            body.scroll_end(animate=False)
            await pilot.pause()
            assert table.cursor_row == table.row_count - 1
            assert table.cursor_column == len(table.columns) - 1
            assert body.scroll_y == body.max_scroll_y > 0
            assert _visible_in(table, body)
            assert table.region.bottom <= body.region.bottom
            final_row = tuple(str(cell) for cell in table.get_row_at(table.row_count - 1))
            assert str(review.casillas[-1].casilla_id) in final_row[0]


@pytest.mark.asyncio
async def test_representative_outlier_localizes_opened_filters_at_narrow_width_and_toggles_theme(
    tmp_path: Path,
) -> None:
    """M720 keeps the opened localized facet disclosure usable at narrow width."""
    review = build_real_modelo_work_review(tmp_path, modelo="720", filing_year=2024, period_code="0A")

    for language in SUPPORTED_OUTPUT_LANGUAGES:
        size = (80, 24)
        with override_settings(cadrumo_output_language=language):
            app = ModeloWorkReviewApp(review)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                screen = app.screen
                header = screen.query_one("#modelo-review-header", Static)
                body = screen.query_one("#modelo-review-body", ContentScroll)
                table = screen.query_one("#modelo-review-casillas-table", DataTable)
                disclosure = screen.query_one("#modelo-review-filter-disclosure", Collapsible)
                expected_title = tr(
                    "flows.modelo_review.title",
                    modelo=review.modelo,
                    filing_year=review.filing_year,
                    period=review.period.registry_token,
                )

                assert str(header.content) == expected_title
                assert _visible_in(header, screen)
                assert _visible_in(table, body)
                assert table.row_count == len(review.casillas)
                assert disclosure.collapsed

                disclosure.collapsed = False
                await pilot.pause()
                assert not disclosure.collapsed
                assert disclosure.region.x >= body.region.x
                assert disclosure.region.right <= body.region.right

                binding_source = cast(
                    "Select[object]",
                    screen.query_one("#modelo-review-filter-binding-source", Select),
                )
                expected_option = tr(
                    "flows.modelo_review.filter.option.binding_source."
                    "ledger_renta_gastos_estimacion_directa_aggregation",
                )
                await _choose_option(
                    pilot,
                    binding_source,
                    _enum_option_index(
                        BindingSourceKind,
                        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                    ),
                )
                option_list = binding_source.query_one(OptionList)
                option_index = (
                    list(BindingSourceKind).index(BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION)
                    + 1
                )
                mounted_prompt = str(option_list.get_option_at_index(option_index).prompt)
                assert expected_option in mounted_prompt
                assert BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION.value not in mounted_prompt

                first = screen.query_one("#modelo-review-filter-input-kind", Select)
                reset = screen.query_one("#modelo-review-filter-reset", Button)
                assert reset in screen.focus_chain
                screen.set_focus(first)
                for _ in range(64):
                    if app.focused is reset:
                        break
                    screen.focus_next()
                    await pilot.pause()
                await pilot.pause()
                assert app.focused is reset
                assert _visible_in(reset, body)

                disclosure.collapsed = True
                body.scroll_end(animate=False)
                await pilot.pause()
                assert disclosure.collapsed
                assert _visible_in(table, body)
                screen.set_focus(table)
                assert app.focused is table

                app.theme = CADRUMO_DARK_THEME_NAME
                await pilot.pause()
                dark_style = screen.get_style_at(1, 0)
                await pilot.press("f3")
                await pilot.pause()
                light_style = screen.get_style_at(1, 0)
                assert app.theme == CADRUMO_LIGHT_THEME_NAME
                assert (dark_style.bgcolor, dark_style.color) != (light_style.bgcolor, light_style.color)
