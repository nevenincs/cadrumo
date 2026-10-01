"""Confirming an assumed value on a real declaration makes it the filer's own once applied.

A seeded declaration is calculated outside the workbench with a value in box
06, so the form reads that value as assumed: the calculation holds it and
nobody is recorded as having entered it. The box panel opens over the real
field with the production parser and the header's result line for the real
declaration as its first line, Enter keeps the prefilled value, and the
change is checked and applied through the production edit contract: the
installed actions check it and submit it, and the captured request runs
through the production edit executor, as the supervised operation would.
Read again, the box says it was entered by the filer.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel
from textual.widgets import Static

from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.edit_preflight import preflight_modelo_edit
from ......application.modelo.work_form_models import ModeloFormCasillaAddressV1, ModeloFormField, ModeloFormOrigin
from ......application.operations.models import OperationRequest
from ......core.casilla_id import validated_casilla_id
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.tax_id_format import runtime_tax_id_format
from .....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..editor import CasillaEditorScreen, EditorDecision, EditorOutcome
from ..header import StatusLine, status_line
from ..installed import InstalledModeloWorkbench, WorkbenchRepositories
from ..session import WorkbenchEditSession
from ..vocabulary import origin_words

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BOX = validated_casilla_id("06")


@dataclass
class _Bench:
    work: SeededOperatorWork
    installed: InstalledModeloWorkbench
    submitted: list[OperationRequest[BaseModel]]

    def box(self) -> ModeloFormField:
        form = self.installed.load(OutputLanguage.EN).form
        return next(item for item in form.fields() if item.address == ModeloFormCasillaAddressV1(casilla_id=_BOX))

    def result_line(self) -> StatusLine:
        line = status_line(self.installed.load(OutputLanguage.EN).form, OutputLanguage.EN, staged=0, recorded=False)
        assert line is not None
        return line


@contextmanager
def _bench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[_Bench]:
    submitted: list[OperationRequest[BaseModel]] = []

    async def capture(_door: ModeloWorkspaceLifecycleDoor, request: OperationRequest[BaseModel]) -> object:
        submitted.append(request)
        return request

    monkeypatch.setattr(ModeloWorkspaceLifecycleDoor, "_submit", capture)
    with seeded_operator_work(tmp_path) as work:
        unit = work.work_unit

        def door(
            calculation_revision_id: str | None, verification_report_id: str | None
        ) -> ModeloWorkspaceLifecycleDoor:
            return ModeloWorkspaceLifecycleDoor(
                services=cast(Any, object()),
                work_unit_id=work.work_unit_id,
                calculation_revision_id=calculation_revision_id,
                verification_report_id=verification_report_id,
                edit_admission=work.admit,
                edit_renewal=work.renew,
                edit_preflight=lambda submission: preflight_modelo_edit(
                    submission,
                    work_catalogue=work.ports.work_unit_repository.load(),
                    calculation_catalogue=work.ports.calculation_repository.load(),
                    tax_id_format=runtime_tax_id_format(authority=work.operation),
                ),
            )

        installed = InstalledModeloWorkbench(
            bucket_id=unit.bucket_id,
            declaration=DeclarationsWorkspaceDeclarationRefV1(
                work_unit_id=unit.work_unit_id,
                modelo=unit.modelo,
                filing_year=unit.filing_year,
                period=unit.period,
                state=unit.state,
                has_current_calculation=False,
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
        yield _Bench(work=work, installed=installed, submitted=submitted)


async def _keep_in_panel(
    field: ModeloFormField, installed: InstalledModeloWorkbench, status: StatusLine
) -> tuple[EditorOutcome | None, str]:
    """Open the box panel over ``field`` and press Enter, as a filer confirming it would.

    Returns the panel's decision and the result line it showed first.
    """
    editor = CasillaEditorScreen(field, parse=installed.parse, language=OutputLanguage.EN, status_line=status)
    app = ScreenHostApp(editor)
    async with app.run_test(size=(80, 24)) as pilot:
        for _ in range(3):
            await pilot.pause()
        shown = str(editor.query_one("#editor-status", Static).render())
        await pilot.press("enter")
        for _ in range(3):
            await pilot.pause()
    return app.return_value, shown


@pytest.mark.timeout(300)
def test_confirming_an_assumed_value_then_applying_makes_it_entered_by_the_filer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _bench(tmp_path, monkeypatch) as bench, override_settings(cadrumo_output_language="en"):
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            bench.work.work_unit_id, ports=bench.work.ports, clock=SEEDED_AT, casilla_inputs={_BOX: Decimal("100")}
        )
        assumed = bench.box()
        result_line = bench.result_line()
        decision, shown = asyncio.run(_keep_in_panel(assumed, bench.installed, result_line))
        assert isinstance(decision, EditorDecision)

        session = WorkbenchEditSession(OutputLanguage.EN)
        assert session.stage_value(assumed, decision.value, decision.display) is None
        preflight = asyncio.run(bench.installed.preflight(session.payload()))
        asyncio.run(bench.installed.apply(session.payload()))
        refusal = bench.work.execute(bench.submitted.pop())
        confirmed = bench.box()
        words = origin_words(confirmed)

    assert result_line
    assert shown == result_line
    assert assumed.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert assumed.value == Decimal("100")
    assert decision.value == assumed.value
    assert decision.advance
    assert not [finding for finding in preflight.findings if finding.blocking]
    assert refusal is None, f"the edit executor refused the confirmation: {refusal!r}"
    assert confirmed.origin is ModeloFormOrigin.ENTERED
    assert confirmed.value == Decimal("100")
    assert words == "Entered by you"
