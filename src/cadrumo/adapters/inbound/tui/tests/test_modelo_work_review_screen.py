"""Real canonical-record and Textual-pilot proof for modelo work review."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from textual.widget import Widget
from textual.widgets import Button, Checkbox, DataTable, Input, RadioSet, Select, SelectionList, Static

from .....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from .....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from .....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from .....application.modelo import ModeloWorkReview, build_modelo_work_review
from .....core import ModeloWorkProgressState, OperatorActionAxis, Period
from .....core.config import override_settings
from .....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from .....domain.calculations.registry import bundled_authority
from .....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    WorkUnit,
    derive_calculation_revision_id,
    derive_verification_report_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_verification_report,
    upsert_work_unit,
)
from .....tests.locales_root_fixture import locales_root_scope
from .....tests.secure_sql import isolated_runtime_profile
from .. import ModeloWorkReviewApp
from .._theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME, ContentScroll

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


def _real_review(
    tmp_path: Path,
    *,
    modelo: str,
    filing_year: int,
    period_code: str,
    blocked: bool = False,
) -> ModeloWorkReview:
    """Build the public review record from genuine encrypted repositories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository
        work_repository = WorkUnitCatalogueRepository(objects=objects)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
        verification_repository = VerificationReportCatalogueRepository(objects=objects)
        modelo_code = ModeloCode(modelo)
        period = Period.from_year_and_code(filing_year, period_code)
        authority = bundled_authority()
        snapshot = authority.snapshot(modelo_code, filing_year=filing_year, period=period.registry_token)
        work_unit_id = derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        )
        calculation_revision_id = (
            derive_calculation_revision_id(
                work_unit_id=work_unit_id,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
            )
            if blocked
            else None
        )
        work_unit = WorkUnit(
            work_unit_id=work_unit_id,
            bucket_id=_BUCKET_ID,
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
            name=f"{modelo}-{filing_year}-{period_code}",
            current_calculation_revision_id=calculation_revision_id,
            created_at=_NOW,
            updated_at=_NOW,
        )
        work_repository.save(upsert_work_unit(work_repository.load(), work_unit))

        if calculation_revision_id is not None:
            calculation = CalculationRevision(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                state=CalculationRevisionState.BORRADOR,
                created_at=_NOW,
                updated_at=_NOW,
            )
            calculation_repository.save(
                upsert_calculation_revision(calculation_repository.load(), calculation),
            )
            affected = next(casilla for casilla in snapshot.revision.casillas if casilla.legal_refs)
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id=affected.id,
                expectation_id="review-screen-expectation",
                message_locale_key="application.modelo.findings.blocking_rule",
                message_facts={"casilla_id": str(affected.id)},
                legal_refs=tuple(affected.legal_refs),
                source_refs=tuple(affected.source_refs),
            )
            report = VerificationReport(
                verification_report_id=derive_verification_report_id(
                    calculation_revision_id=calculation_revision_id,
                    completeness_status=VerificationCompletenessStatus.BLOCKED,
                    findings=(finding,),
                    verified_by="modelo-review-tui-test",
                ),
                calculation_revision_id=calculation_revision_id,
                completeness_status=VerificationCompletenessStatus.BLOCKED,
                findings=(finding,),
                run_at=_NOW,
                verified_by="modelo-review-tui-test",
                granted_verificado_completo=False,
            )
            verification_repository.save(
                upsert_verification_report(verification_repository.load(), report),
            )

        return build_modelo_work_review(
            _BUCKET_ID,
            modelo_code,
            filing_year,
            period,
            authority=authority,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
        )


def _cells(table: DataTable[str]) -> tuple[str, ...]:
    return tuple(str(cell) for row_index in range(table.row_count) for cell in table.get_row_at(row_index))


def _visible_in(widget: Widget, container: Widget) -> bool:
    """Whether the compositor places any part of a widget inside its host."""
    return (
        widget.region.right > container.region.x
        and widget.region.x < container.region.right
        and widget.region.bottom > container.region.y
        and widget.region.y < container.region.bottom
    )


@pytest.mark.asyncio
async def test_blocked_review_renders_all_canonical_grains_without_filter_controls(tmp_path: Path) -> None:
    review = _real_review(tmp_path, modelo="130", filing_year=2026, period_code="1T", blocked=True)
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
            excluded_controls = (Input, Select, SelectionList, Checkbox, RadioSet, Button)
            assert not tuple(widget for control in excluded_controls for widget in screen.query(control))


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
    review = _real_review(
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
    review = _real_review(tmp_path, modelo="189", filing_year=2025, period_code="0A")
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
    review = _real_review(tmp_path, modelo="100", filing_year=2024, period_code="0A")

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
async def test_representative_outlier_localizes_at_narrow_and_wide_sizes_and_toggles_theme(tmp_path: Path) -> None:
    """M720 paints localized frame content and both appearances across the width boundary."""
    review = _real_review(tmp_path, modelo="720", filing_year=2024, period_code="0A")

    for index, language in enumerate(SUPPORTED_OUTPUT_LANGUAGES):
        size = (80, 24) if index % 2 == 0 else (160, 48)
        with override_settings(cadrumo_output_language=language):
            app = ModeloWorkReviewApp(review)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                screen = app.screen
                header = screen.query_one("#modelo-review-header", Static)
                body = screen.query_one("#modelo-review-body", ContentScroll)
                table = screen.query_one("#modelo-review-casillas-table", DataTable)
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
                assert app.focused is table

                app.theme = CADRUMO_DARK_THEME_NAME
                await pilot.pause()
                dark_style = screen.get_style_at(1, 0)
                await pilot.press("f3")
                await pilot.pause()
                light_style = screen.get_style_at(1, 0)
                assert app.theme == CADRUMO_LIGHT_THEME_NAME
                assert (dark_style.bgcolor, dark_style.color) != (light_style.bgcolor, light_style.color)
