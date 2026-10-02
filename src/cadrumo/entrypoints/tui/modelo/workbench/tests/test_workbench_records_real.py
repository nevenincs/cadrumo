"""Saved Modelo 349 records reach the installed form and remain keyboard accessible.

The shared operator-work harness creates real encrypted storage and a work unit.
These TUI-owned tests calculate synthetic invoices through the production ports,
then exercise the installed reader and the actual terminal widget in every locale.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from textual.widgets import OptionList, Static

from ......adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......adapters.persistence.profile.tests.operator_scope_fakes import (
    build_inward_operator_scope_ports_for_active_route,
)
from ......adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ......application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.value_presentation import format_casilla_value
from ......application.modelo.verification_actions import verify_modelo_revision
from ......application.modelo.work_form_models import ModeloFormRepeatingBlock
from ......application.operations.composition import OperationComposedServices
from ......core.casilla_id import validated_casilla_id
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.deadlines.models import IVARegime, TaxpayerProfile
from ......domain.invoices.tests.catalogue_support import build_invoice_catalogue
from ......tests.env_scope import ready_clave_settings
from .....tests.modelo_349_invoice_facts import (
    M349_EXPECTED_IMPORTE,
    M349_EXPECTED_OPERADORES,
    M349_INVOICES,
    intra_community_invoice,
)
from .....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from .....tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from ....components.host import ScreenHostApp
from ....components.theme import install_cadrumo_themes
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..casilla_list import CasillaList, CasillaListEntry
from ..grid import CasillaListRecords
from ..installed import InstalledModeloWorkbench, WorkbenchRepositories
from ..issues import WorkbenchIssuesScreen, issue_lines
from ..page_items import page_of, workbench_pages
from ..screen import ModeloWorkbenchScreen
from ..wording import does_not_apply_text

pytestmark = [pytest.mark.hex_entrypoint]


@pytest.fixture
def m349_work(tmp_path: Path) -> Iterator[SeededOperatorWork]:
    with seeded_operator_work(tmp_path, modelo="349") as work:
        invoices = tuple(
            intra_community_invoice(
                bucket_id=work.work_unit.bucket_id,
                invoice_number=number,
                counterparty_country=country,
                counterparty_tax_id=tax_id,
                issued_at=issued_at,
                base_total=base_total,
            )
            for number, country, tax_id, issued_at, base_total in M349_INVOICES
        )
        work.ports.invoice_repository.save(build_invoice_catalogue(invoices))
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, clock=SEEDED_AT
        )
        assert isinstance(result, BucketAggregationCalculationResult)
        assert result.revision.casilla_values[validated_casilla_id("decl.importe-operaciones")] == M349_EXPECTED_IMPORTE
        assert (
            result.revision.casilla_values[validated_casilla_id("decl.numero-operadores")] == M349_EXPECTED_OPERADORES
        )
        assert len(result.revision.detail_rows) == 3
        yield work


def _installed(work: SeededOperatorWork) -> InstalledModeloWorkbench:
    unit = work.work_unit

    def door(calculation_revision_id: str | None, verification_report_id: str | None) -> ModeloWorkspaceLifecycleDoor:
        # Read-only acceptance never submits an operation. The production door
        # and installed reader still perform their normal admission/load paths.
        return ModeloWorkspaceLifecycleDoor(
            services=cast(OperationComposedServices, object()),
            work_unit_id=unit.work_unit_id,
            calculation_revision_id=calculation_revision_id,
            verification_report_id=verification_report_id,
        )

    return InstalledModeloWorkbench(
        bucket_id=unit.bucket_id,
        declaration=DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=unit.work_unit_id,
            modelo=unit.modelo,
            filing_year=unit.filing_year,
            period=unit.period,
            state=unit.state,
            has_current_calculation=True,
            has_current_filing=False,
        ),
        operation=work.operation,
        repositories=WorkbenchRepositories(
            work_units=work.ports.work_unit_repository,
            calculations=work.ports.calculation_repository,
            verifications=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
        ),
        door=door,
    )


@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.unit
def test_real_encrypted_calculation_rows_reach_the_installed_form(
    m349_work: SeededOperatorWork,
    language: OutputLanguage,
) -> None:
    unit, calculated = m349_work.work_unit, m349_work.require_head()
    stored = (
        CalculationRevisionCatalogueRepository(bucket_id=unit.bucket_id).load().get(calculated.calculation_revision_id)
    )
    assert stored is not None and stored.detail_rows == calculated.detail_rows
    assert "detail_rows" in stored.model_fields_set
    form = _installed(m349_work).load(language).form
    block = next(
        block
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock) and block.id == "modelo-349-operador"
    )
    assert block.rows_known and tuple(row.index for row in block.rows) == (1, 2, 3)
    amounts = [dict(zip(block.column_casilla_ids, row.values, strict=True))["op.base-imponible"] for row in block.rows]
    assert amounts == [item[-1] for item in M349_INVOICES]
    assert sum(value for value in amounts if isinstance(value, Decimal)) == M349_EXPECTED_IMPORTE
    assert form.calculation_revision_id == calculated.calculation_revision_id


@pytest.mark.unit
def test_explicit_empty_and_omitted_legacy_detail_channels_survive_real_encrypted_reload(
    m349_work: SeededOperatorWork,
) -> None:
    unit = m349_work.work_unit
    m349_work.ports.invoice_repository.save(build_invoice_catalogue(()))
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        unit.work_unit_id,
        ports=m349_work.ports,
        clock=SEEDED_AT,
    )
    assert result.revision.detail_rows == ()
    repository = CalculationRevisionCatalogueRepository(bucket_id=unit.bucket_id)
    catalogue = repository.load()
    head = catalogue.get(result.revision.calculation_revision_id)
    assert head is not None and "detail_rows" in head.model_fields_set
    before = _installed(m349_work).load(OutputLanguage.EN).form
    blocks = [
        block
        for page in before.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
    ]
    assert blocks and all(block.rows_known and not block.rows for block in blocks)

    write = repository.to_secure_object_write(catalogue)
    payload = json.loads(write.payload)
    del payload["payload"]["revisions"][head.calculation_revision_id]["detail_rows"]
    secure_object_repository_for_bucket(unit.bucket_id).save_many(
        (write.model_copy(update={"payload": json.dumps(payload).encode("utf-8")}),)
    )
    legacy = repository.load().get(head.calculation_revision_id)
    assert legacy is not None and "detail_rows" not in legacy.model_fields_set
    assert legacy.calculation_revision_id == head.calculation_revision_id
    after = _installed(m349_work).load(OutputLanguage.EN).form
    blocks = [
        block
        for page in after.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
    ]
    assert blocks and all(not block.rows_known and not block.rows for block in blocks)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
@pytest.mark.parametrize("appearance", ("dark", "light"))
async def test_installed_saved_records_are_read_only_visible_content_in_each_terminal_layout(
    m349_work: SeededOperatorWork,
    language: OutputLanguage,
    size: tuple[int, int],
    appearance: str,
) -> None:
    unit, calculated = m349_work.work_unit, m349_work.require_head()
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(_installed(m349_work))
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            install_cadrumo_themes(app, appearance=appearance)
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.press("]")
            await pilot.pause()
            listing = screen.query_one(CasillaList)
            records = [item for item in listing.items if isinstance(item, CasillaListRecords)]
            assert len(records) == 1 and len(records[0].rows) == 3
            assert not any(isinstance(item, CasillaListEntry) for item in listing.items)
            assert listing.highlighted is None
            visible = {key for key, active in screen.active_bindings.items() if active.binding.show}
            assert {"enter", "s"}.isdisjoint(visible)
            assert {"up", "question_mark", "escape"} <= visible
            next_line = str(screen.query_one("#wb-next", Static).render())
            named = next_line.rpartition("[")[2].removesuffix("]").lower()
            assert named and named in visible
            assert screen._empty_listing_note() is None
            heading = str(screen.query_one("#wb-page", Static).render())
            help_text = str(screen.query_one("#wb-help", Static).render())
            assert tr("tui.modelo.workbench.filter.empty") not in heading
            assert tr("tui.modelo.workbench.filter.empty_next", page="") not in heading
            assert does_not_apply_text(unit.period) not in heading
            assert tr("tui.modelo.workbench.help.empty") not in help_text
            assert tr("tui.modelo.workbench.grid.records_read_only") in help_text
            assert all(
                widget.region.right <= size[0] and widget.region.bottom <= size[1]
                for widget in (listing, screen.query_one("#wb-page", Static))
            )
            assert listing.scrollable_content_region.width <= listing.region.width
            assert not listing.show_horizontal_scrollbar
            assert app.focused is listing
            await pilot.press("home", "down")
            await pilot.pause()
            assert listing.scroll_y == min(1, listing.max_scroll_y)
            await pilot.press("up")
            await pilot.pause()
            assert listing.scroll_y == 0
            drawn: dict[int, str] = {}
            for _ in range(listing.virtual_size.height + 1):
                for y in range(listing.size.height):
                    drawn[int(listing.scroll_y) + y] = listing.render_line(y).text
                if listing.scroll_y == listing.max_scroll_y:
                    break
                before_scroll = listing.scroll_y
                await pilot.press("pagedown")
                await pilot.pause()
                assert listing.scroll_y > before_scroll
            assert listing.scroll_y == listing.max_scroll_y
            rendered_rows = "\n".join(line for _, line in sorted(drawn.items()))
            assert "EU Customer GmbH" in " ".join(rendered_rows.split())
            for identifier in ("123456789", "12345678901"):
                assert identifier in rendered_rows
            for column_heading in records[0].headings:
                assert " ".join(column_heading.split()) in " ".join(rendered_rows.split())
            for *_, amount in M349_INVOICES:
                shown = format_casilla_value(amount, data_type="money", language=language)
                assert " ".join(shown.split()) in " ".join(rendered_rows.split())
            end_scroll = listing.scroll_y
            await pilot.press("pageup")
            await pilot.pause()
            assert listing.scroll_y == max(end_scroll - max(listing.scrollable_content_region.height - 2, 1), 0)
            await pilot.press("home")
            await pilot.pause()
            assert listing.scroll_y == 0
            assert listing.focus_address(("casilla", "op.base-imponible"))
            assert listing.highlighted is None
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is screen
            await pilot.press("end")
            await pilot.pause()
            assert listing.scroll_y == listing.max_scroll_y
            assert screen.form is not None and screen.form.calculation_revision_id == calculated.calculation_revision_id


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
@pytest.mark.parametrize("appearance", ("dark", "light"))
async def test_installed_known_empty_records_keep_source_guidance_and_column_finding_navigation(
    m349_work: SeededOperatorWork,
    language: OutputLanguage,
    size: tuple[int, int],
    appearance: str,
) -> None:
    unit = m349_work.work_unit
    m349_work.ports.invoice_repository.save(build_invoice_catalogue(()))
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        unit.work_unit_id, ports=m349_work.ports, clock=SEEDED_AT
    )
    assert not result.revision.detail_rows and "detail_rows" in result.revision.model_fields_set
    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator:test",
        workflow_profile=TaxpayerProfile(
            tax_id="12345678Z", iva_regime=IVARegime("GENERAL"), does_intracomunitario=True
        ),
        settings=ready_clave_settings("12345678Z"),
        operator_scope_ports=build_inward_operator_scope_ports_for_active_route(),
        operation=m349_work.operation,
        clock=SEEDED_AT,
    )
    column = "op.codigo-pais"
    key = ("casilla", column)
    assert any(finding.casilla_id == column for finding in report.findings)
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(_installed(m349_work))
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            install_cadrumo_themes(app, appearance=appearance)
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.form is not None
            pages = workbench_pages(screen.form)
            target = page_of(pages, key)
            assert target is not None
            for _ in range((target - screen._page_index) % len(pages)):
                await pilot.press("]")
            await pilot.pause()
            listing = screen.query_one(CasillaList)
            records = [item for item in listing.items if isinstance(item, CasillaListRecords)]
            assert len(records) == 1 and not records[0].rows and column in records[0].column_casilla_ids
            assert not any(isinstance(item, CasillaListEntry) for item in listing.items)
            assert listing.highlighted is None
            visible = {key for key, active in screen.active_bindings.items() if active.binding.show}
            assert {"enter", "s"}.isdisjoint(visible)
            assert {"up", "question_mark", "escape"} <= visible
            next_line = str(screen.query_one("#wb-next", Static).render())
            named = next_line.rpartition("[")[2].removesuffix("]").lower()
            assert named and named in visible
            count_text = tr("tui.modelo.workbench.repeating", count=0)
            body = "\n".join(listing.render_line(y).text for y in range(listing.size.height))
            assert count_text in body
            for selector in ("#wb-page", "#wb-crumb"):
                heading = str(screen.query_one(selector, Static).render())
                assert tr("tui.modelo.workbench.filter.empty") not in heading
                assert tr("tui.modelo.workbench.filter.empty_next", page="") not in heading
                assert does_not_apply_text(unit.period) not in heading
            help_text = str(screen.query_one("#wb-help", Static).render())
            assert tr("tui.modelo.workbench.grid.records_read_only") in help_text
            assert tr("tui.modelo.workbench.help.empty") not in help_text
            assert tr("tui.modelo.workbench.grid.records_unknown") not in help_text
            assert app.focused is listing
            assert listing.focus_address(key) and listing.highlighted is None
            assert not listing.show_horizontal_scrollbar
            assert listing.region.right <= size[0] and listing.region.bottom <= size[1]
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is screen

            # A real persisted check's column finding must return here from a different page.
            lines = issue_lines(screen.form)
            line_index = next(index for index, line in enumerate(lines) if line.in_records and line.key == key)
            await pilot.press("]", "i")
            await pilot.pause()
            assert isinstance(app.screen, WorkbenchIssuesScreen)
            options = app.screen.query_one(OptionList)
            option_index = options.get_option_index(f"issue-{line_index}")
            await pilot.press("home")
            for _ in range(options.option_count):
                if options.highlighted == option_index:
                    break
                await pilot.press("down")
            assert options.highlighted == option_index
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is screen and app.focused is listing
            assert screen._page_index == target and listing.highlighted is None
            assert listing.focus_address(key)
            body = "\n".join(listing.render_line(y).text for y in range(listing.size.height))
            assert count_text in body
            assert screen.form.calculation_revision_id == result.revision.calculation_revision_id
