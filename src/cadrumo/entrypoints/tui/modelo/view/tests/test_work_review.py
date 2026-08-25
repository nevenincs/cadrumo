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

from ......application.modelo import ModeloWorkOriginAnomaly
from ......application.modelo.tests._work_review_integration_fixture import build_real_modelo_work_review
from ......core import BindingSourceKind, EstadoCasillaOficial, ModeloWorkProgressState, OperatorActionAxis
from ......core.config import override_settings
from ......core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ......domain.calculations.registry import InputKind, RelationConsumptionChannel
from ......domain.filing import ModeloValueKind
from ......domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ......tests.locales_root_fixture import locales_root_scope
from ....components.theme import (
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT_THEME_NAME,
)
from ....components.widgets import ContentScroll
from ..work_review import (
    _ABSENT,
    _PRESENT,
    ModeloWorkReviewApp,
    ModeloWorkReviewScreen,
    _enum_options,
    _presence_options,
    _relation_channel_options,
    _resolved_options,
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


def test_facet_option_sets_are_exactly_the_canonical_closed_axes() -> None:
    for enum_type, axis in (
        (InputKind, "input_kind"),
        (BindingSourceKind, "binding_source"),
        (ModeloValueKind, "realised_kind"),
        (ModeloWorkOriginAnomaly, "origin_anomaly"),
        (EstadoCasillaOficial, "estado_casilla_oficial"),
        (OperatorActionAxis, "operator_action"),
        (ModeloVerificationFindingKind, "finding_kind"),
        (ModeloVerificationFindingSeverity, "finding_severity"),
    ):
        assert tuple(value for _, value in _enum_options(enum_type, axis=axis)) == tuple(
            member.value for member in enum_type
        )
    assert tuple(value for _, value in _relation_channel_options()) == get_args(RelationConsumptionChannel)
    assert tuple(value for _, value in _presence_options()) == (_PRESENT, _ABSENT)
    assert tuple(value for _, value in _resolved_options()) == (True, False)


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
                InputKind.COMPUTED.value,
                tuple(str(row.casilla_id) for row in review.casillas if row.declared_input_kind is InputKind.COMPUTED),
            ),
            (
                "#modelo-review-filter-binding-source",
                BindingSourceKind.PROFILE.value,
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if any(binding.source is BindingSourceKind.PROFILE for binding in row.concrete_bindings)
                ),
            ),
            (
                "#modelo-review-filter-binding-presence",
                _PRESENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.concrete_bindings),
            ),
            (
                "#modelo-review-filter-binding-presence",
                _ABSENT,
                tuple(str(row.casilla_id) for row in review.casillas if not row.concrete_bindings),
            ),
            (
                "#modelo-review-filter-formula-presence",
                _PRESENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.concrete_formula is not None),
            ),
            (
                "#modelo-review-filter-formula-presence",
                _ABSENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.concrete_formula is None),
            ),
            (
                "#modelo-review-filter-relation-presence",
                _PRESENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.relation_consumption),
            ),
            (
                "#modelo-review-filter-relation-presence",
                _ABSENT,
                tuple(str(row.casilla_id) for row in review.casillas if not row.relation_consumption),
            ),
            (
                "#modelo-review-filter-relation-channel",
                "primary_binding",
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if any("primary_binding" in relation.channels for relation in row.relation_consumption)
                ),
            ),
            (
                "#modelo-review-filter-origin-anomaly",
                ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN.value,
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if row.origin_anomaly is ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN
                ),
            ),
            (
                "#modelo-review-filter-origin-anomaly-presence",
                _ABSENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.origin_anomaly is None),
            ),
            (
                "#modelo-review-filter-estado-casilla-oficial",
                EstadoCasillaOficial.ADDRESSED.value,
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if row.estado_casilla_oficial is EstadoCasillaOficial.ADDRESSED
                ),
            ),
        )
        for selector, value, expected_rows in checks:
            chooser = cast("Select[str]", screen.query_one(selector, Select))
            chooser.value = value
            await pilot.pause()
            assert expected_rows
            assert len(expected_rows) < len(original_rows)
            assert _row_keys(table) == expected_rows
            chooser.clear()
            await pilot.pause()
            assert _row_keys(table) == original_rows

        resolved = cast(
            "Select[bool]",
            screen.query_one("#modelo-review-filter-binding-resolved", Select),
        )
        resolved.value = False
        await pilot.pause()
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

        input_kind = cast("Select[str]", screen.query_one("#modelo-review-filter-input-kind", Select))
        estado_casilla_oficial = cast(
            "Select[str]",
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

        input_kind.value = InputKind.MANUAL.value
        await pilot.pause()
        assert len(_row_keys(table)) == len(expected_manual)
        assert _row_keys(table) == expected_manual

        estado_casilla_oficial.value = EstadoCasillaOficial.ADDRESSED.value
        await pilot.pause()
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
                ModeloValueKind.LITERAL.value,
                tuple(str(row.casilla_id) for row in review.casillas if row.realised_kind is ModeloValueKind.LITERAL),
            ),
            (
                "#modelo-review-filter-origin-anomaly",
                ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE.value,
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if row.origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
                ),
            ),
            (
                "#modelo-review-filter-origin-anomaly-presence",
                _PRESENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.origin_anomaly is not None),
            ),
            (
                "#modelo-review-filter-casilla-blocker",
                OperatorActionAxis.SUPPLY_MANUAL_INPUT.value,
                tuple(
                    str(row.casilla_id)
                    for row in review.casillas
                    if any(blocker.axis is OperatorActionAxis.SUPPLY_MANUAL_INPUT for blocker in row.blocked_by)
                ),
            ),
            (
                "#modelo-review-filter-casilla-blocker-presence",
                _PRESENT,
                tuple(str(row.casilla_id) for row in review.casillas if row.blocked_by),
            ),
        )
        for selector, value, expected_rows in casilla_checks:
            chooser = cast("Select[str]", screen.query_one(selector, Select))
            chooser.value = value
            await pilot.pause()
            assert expected_rows
            assert len(expected_rows) < len(original_casillas)
            assert _row_keys(casillas) == expected_rows
            chooser.clear()
            await pilot.pause()

        resolved = cast(
            "Select[bool]",
            screen.query_one("#modelo-review-filter-binding-resolved", Select),
        )
        resolved.value = True
        await pilot.pause()
        expected_resolved = tuple(
            str(row.casilla_id) for row in review.casillas if any(binding.resolved for binding in row.concrete_bindings)
        )
        assert expected_resolved
        assert _row_keys(casillas) == expected_resolved
        resolved.clear()

        finding_kind = cast(
            "Select[str]",
            screen.query_one("#modelo-review-filter-finding-kind", Select),
        )
        finding_kind.value = ModeloVerificationFindingKind.BLOCKING_RULE.value
        await pilot.pause()
        assert findings.row_count == 1 < len(original_findings)
        assert review.findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
        finding_kind.clear()

        finding_severity = cast(
            "Select[str]",
            screen.query_one("#modelo-review-filter-finding-severity", Select),
        )
        finding_severity.value = ModeloVerificationFindingSeverity.WARNING.value
        await pilot.pause()
        assert findings.row_count == 1 < len(original_findings)
        assert review.findings[1].severity is ModeloVerificationFindingSeverity.WARNING
        finding_severity.clear()

        record_blocker = cast(
            "Select[str]",
            screen.query_one("#modelo-review-filter-record-blocker", Select),
        )
        record_blocker.value = OperatorActionAxis.SUPPLY_MANUAL_INPUT.value
        await pilot.pause()
        assert _row_keys(blockers) == original_blockers

        cast(
            "Select[str]", screen.query_one("#modelo-review-filter-realised-kind", Select)
        ).value = ModeloValueKind.DEFAULT.value
        cast(
            "Select[str]", screen.query_one("#modelo-review-filter-finding-kind", Select)
        ).value = ModeloVerificationFindingKind.ADVISORY.value
        cast(
            "Select[str]", screen.query_one("#modelo-review-filter-record-blocker", Select)
        ).value = OperatorActionAxis.RE_VERIFY.value
        await pilot.pause()
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
                    "Select[str]",
                    screen.query_one("#modelo-review-filter-binding-source", Select),
                )
                binding_source.value = BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION.value
                await pilot.pause()
                expected_option = tr(
                    "flows.modelo_review.filter.option.binding_source."
                    "ledger_renta_gastos_estimacion_directa_aggregation",
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
