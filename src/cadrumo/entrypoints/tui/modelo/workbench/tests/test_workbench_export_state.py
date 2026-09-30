"""The workbench says whether a file for the AEAT exists and still matches, and records the filing only after one that does.

Driven through the real workbench over the synthetic declaration, verified and
with nothing withholding it, in each of the three states the read model can
state. With no file, the next step is creating it, which F8 does. With a file
made from the current calculation, the header says when it was created and
the next step is recording the filing, which F8 asks to confirm and then
submits. With a file made from an earlier calculation, the header warns that
it is out of date, the next step is creating it again, and F8 refuses to
record the filing, naming the file's day.

Through the installed composition, over real encrypted storage, a file
exported with the real export service reaches the screen's header.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from textual.color import Color
from textual.pilot import Pilot
from textual.widgets import Static

from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from ......adapters.persistence.profile.tests.modelo_export_support import (
    export_taxpayer_profile,
    isolated_backend,
    seed_profile,
    seed_revision,
)
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.export import ModeloExportCommand, export_modelo_revision
from ......application.modelo.work_form_models import ModeloFormExport, ModeloWorkForm
from ......core.casilla_id import validated_casilla_id
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.calculations.registry.authority import bundled_indexed_authority
from ......domain.calculations.registry.ids import BindingId
from ......domain.modelos.calculation_revision import CalculationRevisionState
from ......domain.modelos.repository import upsert_work_unit
from ......domain.modelos.work_unit import WorkUnitCatalogue
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..export import WorkbenchExportScreen
from ..installed import InstalledModeloWorkbench, WorkbenchRepositories
from ..screen import ModeloWorkbenchScreen
from ..wording import day_text
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

__all__ = ["isolated_backend"]

_EXPORTED_AT = datetime(2026, 4, 2, 9, 30, tzinfo=UTC)
_EN = OutputLanguage.EN


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _exported(*, current: bool) -> ModeloWorkForm:
    form = synthetic_form(needs_input=False)
    revision = form.calculation_revision_id
    assert revision is not None
    export = ModeloFormExport(
        exported_at=_EXPORTED_AT, calculation_revision_id=revision if current else "c" * 64, current=current
    )
    return form.model_copy(update={"last_export": export})


def _text(screen: ModeloWorkbenchScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


@pytest.mark.unit
@pytest.mark.hex_entrypoint
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["no-file", "current-file", "older-file"])
async def test_each_file_state_reads_in_the_header_and_leads_f8_to_its_one_step(state: str) -> None:
    form = synthetic_form(needs_input=False) if state == "no-file" else _exported(current=state == "current-file")
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        day = day_text(_EXPORTED_AT, _EN)
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 40)) as pilot:
            await _settle(pilot)
            file_widget = screen.query_one("#wb-file", Static)
            shown = file_widget.display
            file_text = _text(screen, "#wb-file")
            warned = file_widget.has_class("-out-of-date")
            file_colour = file_widget.styles.color
            warning = Color.parse(app.theme_variables["warning"])
            next_line = _text(screen, "#wb-next")
            await pilot.press("f8")
            await _settle(pilot)
            after_f8 = app.screen
            if isinstance(after_f8, ConfirmScreen):
                await pilot.click("#btn-confirm-accept")
                await _settle(pilot, 6)
            notice = _text(screen, "#wb-notice")
            app.exit(None)

        def next_words(key: str, action: str, **values: object) -> str:
            return tr(
                "tui.modelo.workbench.next_line", action=tr(f"tui.modelo.workbench.next.{action}", **values), key=key
            )

        if state == "no-file":
            assert not shown
            assert next_line == next_words("e", "export")
            assert isinstance(after_f8, WorkbenchExportScreen), "F8 creates the file"
            assert actions.requested == []
        elif state == "current-file":
            assert shown and not warned
            assert file_text == tr("tui.modelo.workbench.header.file_created", date=day)
            assert next_line == next_words("F8", "record_after_file", date=day)
            assert isinstance(after_f8, ConfirmScreen), "F8 asks before recording the filing"
            assert actions.requested == ["file"]
        else:
            assert shown and warned
            assert file_colour == warning, "a file that no longer matches reads as a warning"
            assert file_text == tr("tui.modelo.workbench.header.file_out_of_date", date=day, key="e")
            assert next_line == next_words("e", "export_again", date=day)
            assert after_f8 is screen, "F8 neither records the filing nor asks to"
            assert notice == tr("tui.modelo.workbench.record.refused_file_out_of_date", date=day)
            assert actions.requested == []
            assert actions.exports == []


_FILING_YEAR = 2026
_PERIOD_CODE = "4T"
_ACTIVITY_START = date(_FILING_YEAR, 10, 1)
_SURFACE = "workbench export state test"
_RESULT_BOX = validated_casilla_id("19", surface=_SURFACE)
_INPUTS = {validated_casilla_id("01", surface=_SURFACE): "250.00", validated_casilla_id("02", surface=_SURFACE): "0.00"}
_ZERO_PRIOR_BINDINGS: dict[BindingId, str] = {
    "modelo-130-pagos-fraccionados-anteriores": "0",
    "modelo-130-resultados-negativos-anteriores": "0",
    "irpf.previous_year_economic_activity_net_income": "0",
}


@pytest.mark.integration
@pytest.mark.hex_entrypoint
@pytest.mark.timeout(300)
def test_a_file_exported_for_real_reaches_the_header_through_the_installed_workbench(
    isolated_backend: None, tmp_path: Path
) -> None:
    with bundled_indexed_authority().operation() as operation, override_settings(cadrumo_output_language="en"):
        bucket_id = seed_profile()
        ports = modelo_export_ports_for_test(bucket_id=bucket_id)
        work_unit_id, revision_id = seed_revision(
            bucket_id=bucket_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            modelo="130",
            filing_year=_FILING_YEAR,
            period=_PERIOD_CODE,
            input_values_by_casilla_id=dict(_INPUTS),
            binding_overrides=dict(_ZERO_PRIOR_BINDINGS),
            casilla_values={_RESULT_BOX: Decimal("-50.00")},
        )

        def advance(catalogue: WorkUnitCatalogue) -> WorkUnitCatalogue:
            """Make the seeded calculation the declaration's current one, as committing a calculation does."""
            seeded = catalogue.get(work_unit_id)
            assert seeded is not None
            return upsert_work_unit(
                catalogue, seeded.model_copy(update={"current_calculation_revision_id": revision_id})
            )

        ports.work_unit.mutate(advance)
        exported_at = datetime.now(UTC)
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision_id,
                output_path=tmp_path / "modelo-130-2026-4T.txt",
                actor="operator",
            ),
            workflow_profile=export_taxpayer_profile().model_copy(update={"activity_start_date": _ACTIVITY_START}),
            export_ports=ports,
            clock=exported_at,
            operation=operation,
        )
        unit = ports.work_unit.load().get(work_unit_id)
        assert unit is not None
        installed = InstalledModeloWorkbench(
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
            operation=operation,
            repositories=WorkbenchRepositories(
                work_units=ports.work_unit,
                calculations=ports.calculation,
                verifications=VerificationReportCatalogueRepository(bucket_id=bucket_id),
                bucket_events=ports.bucket_event,
            ),
            door=lambda calculation, report: ModeloWorkspaceLifecycleDoor(
                services=cast(Any, object()),
                work_unit_id=work_unit_id,
                calculation_revision_id=calculation,
                verification_report_id=report,
            ),
        )
        read = installed.load(_EN).form.last_export
        expected = tr("tui.modelo.workbench.header.file_created", date=day_text(exported_at, _EN))

        async def header() -> str:
            screen = ModeloWorkbenchScreen(installed)
            app = ScreenHostApp(screen)
            async with app.run_test(size=(160, 40)) as pilot:
                await _settle(pilot, 10)
                shown = _text(screen, "#wb-file")
                app.exit(None)
            return shown

        shown = asyncio.run(header())

    assert read is not None and read.current and read.calculation_revision_id == revision_id
    assert shown == expected
