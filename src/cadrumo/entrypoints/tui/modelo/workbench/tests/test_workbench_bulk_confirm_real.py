"""An assumed value the confirm step counts can be confirmed from F8, on a real declaration.

The declaration is seeded in real encrypted storage, calculated outside the
workbench with a value nobody typed in the workbench, and read through the
production reader with the real edit admission, parser, preflight and edit
executor. Only the operation supervisor is stood in for: the door's submission
is captured and run through the production edit executor, as the supervised
operation would run it.

On a Modelo 131 whose only assumed value is a typed amount no printed box
shows, F8 on the confirm step lists that value, the filer ticks it right, and
once applied it reads as entered by the filer.
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
from textual.pilot import Pilot
from textual.widgets import Checkbox

from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.edit_preflight import preflight_modelo_edit
from ......application.modelo.work_form_models import (
    ModeloFormAddressV1,
    ModeloFormBindingAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    confirmable,
)
from ......application.operations.models import OperationRequest
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.ids import BindingId
from ......domain.calculations.registry.tax_id_format import runtime_tax_id_format
from .....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..bulk_confirm import BulkConfirmScreen
from ..installed import InstalledModeloWorkbench, WorkbenchRepositories
from ..ports import WorkbenchChangeKind
from ..screen import ModeloWorkbenchScreen
from ..session import WorkbenchEditSession
from ..vocabulary import origin_words

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NO_VOLUME_BASE: BindingId = "modelo-131.page1.sin-datos-base-volumen"
"""A Modelo 131 amount the filer types that no printed box shows."""


@dataclass
class _Bench:
    work: SeededOperatorWork
    installed: InstalledModeloWorkbench
    submitted: list[OperationRequest[BaseModel]]

    def field(self, address: ModeloFormAddressV1) -> ModeloFormField:
        form = self.installed.load(OutputLanguage.EN).form
        return next(item for item in form.fields() if item.address == address)

    def apply(self, session: WorkbenchEditSession) -> None:
        """Check and apply the staged changes as the workbench would, and run the captured edit."""
        preflight = asyncio.run(self.installed.preflight(session.payload()))
        assert not [finding for finding in preflight.findings if finding.blocking], preflight.findings
        asyncio.run(self.installed.apply(session.payload()))
        refusal = self.work.execute(self.submitted.pop())
        assert refusal is None, f"the edit executor refused the change: {refusal!r}"


@contextmanager
def _bench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, modelo: str) -> Generator[_Bench]:
    submitted: list[OperationRequest[BaseModel]] = []

    async def capture(_door: ModeloWorkspaceLifecycleDoor, request: OperationRequest[BaseModel]) -> object:
        submitted.append(request)
        return request

    monkeypatch.setattr(ModeloWorkspaceLifecycleDoor, "_submit", capture)
    with seeded_operator_work(tmp_path, modelo=modelo) as work:
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


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> None:
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            return
    raise AssertionError("the workbench never finished reading its declaration")


@dataclass
class _Confirmed:
    listed: tuple[ModeloFormField, ...]
    tick_offered: bool
    notes: int
    staged: tuple[tuple[ModeloFormAddressV1, WorkbenchChangeKind, object], ...]


async def _confirm_with_f8(installed: InstalledModeloWorkbench) -> _Confirmed:
    """Open the workbench, press F8 on the confirm step, tick the values right and confirm them."""
    screen = ModeloWorkbenchScreen(installed, actions=installed)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(160, 48)) as pilot:
        await _opened(pilot, screen)
        await pilot.press("f8")
        await _settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, BulkConfirmScreen), f"F8 opened {type(dialog).__name__}, not the confirm list"
        listed = dialog.fields
        tick = dialog.query_one("#bulk-tick", Checkbox)
        tick_offered = not tick.disabled
        notes = len(dialog.query("#bulk-left-out"))
        tick.value = True
        await _settle(pilot)
        await pilot.click("#bulk-confirm")
        await _settle(pilot)
        staged = tuple((change.change.address, change.kind, change.value) for change in screen.staged_changes)
        app.exit(None)
    return _Confirmed(listed=listed, tick_offered=tick_offered, notes=notes, staged=staged)


@pytest.mark.timeout(300)
def test_f8_confirms_a_typed_amount_no_printed_box_shows_and_applying_keeps_it_as_the_filers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    address = ModeloFormBindingAddressV1(binding_id=_NO_VOLUME_BASE)
    with _bench(tmp_path, monkeypatch, modelo="131") as bench, override_settings(cadrumo_output_language="en"):
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            bench.work.work_unit_id,
            ports=bench.work.ports,
            clock=SEEDED_AT,
            binding_values={_NO_VOLUME_BASE: Decimal("250")},
        )
        form = bench.installed.load(OutputLanguage.EN).form
        assumed = bench.field(address)
        confirmed = asyncio.run(_confirm_with_f8(bench.installed))
        session = WorkbenchEditSession(OutputLanguage.EN)
        assert session.stage_confirmation(assumed) is None
        bench.apply(session)
        kept = bench.field(address)
        words = origin_words(kept)

    assert form.counts.default_to_confirm == 1, "the confirm step counts exactly this one value"
    assert assumed.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert assumed.value == Decimal("250")
    assert confirmable(assumed)
    assert [field.address for field in confirmed.listed] == [address]
    assert confirmed.tick_offered
    assert confirmed.notes == 0, "nothing assumed here is left out, so no note says anything is"
    assert confirmed.staged == ((address, WorkbenchChangeKind.SET, Decimal("250")),)
    assert kept.origin is ModeloFormOrigin.ENTERED
    assert kept.value == Decimal("250")
    assert words == "Entered by you"
