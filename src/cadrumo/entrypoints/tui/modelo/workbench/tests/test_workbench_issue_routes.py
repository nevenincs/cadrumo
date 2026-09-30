"""The workbench goes where the findings list leads: the owning area, or the confirm step for one part of the form.

Driven through the real workbench over the synthetic declaration, opening the
findings list with ``i``. Asking there to open the area that owns a value fed
by the filer's records leaves the workbench for that area through the
navigation it was given. Asking to confirm the assumed values opens the
confirm step on the part of the form that holds them, never on the whole
declaration at once.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot

from ......application.modelo.source_policy import SourceSurface
from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1
from ..bulk_confirm import BulkConfirmScreen
from ..screen import ModeloWorkbenchScreen
from ..sources import surface_target
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ASSUMED = "07"


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _finding_on_income() -> ModeloFormIssue:
    return ModeloFormIssue(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id="01",
            message_locale_key="application.modelo.findings.oss_evidence_missing",
            legal_refs=("ley-37-1992:art-99",),
        ),
        box="01",
    )


def _assumed_in_the_grid() -> ModeloWorkForm:
    form = synthetic_form(needs_input=False)
    form = replace_fields(form, {_ASSUMED: {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")}})
    return form.model_copy(update={"counts": form.counts.model_copy(update={"default_to_confirm": 1})})


@pytest.mark.asyncio
async def test_opening_the_owning_area_from_the_findings_leaves_for_that_area() -> None:
    form = synthetic_form(needs_input=False).model_copy(update={"issues": (_finding_on_income(),)})
    opened: list[TuiNavigationTargetV1] = []
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions(), navigate=opened.append)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            await pilot.press("end", "a")
            await _settle(pilot)
            app.exit(None)

    target = surface_target(SourceSurface.LEDGER)
    assert target is not None
    assert opened == [target]


@pytest.mark.asyncio
async def test_confirming_from_the_findings_opens_the_confirm_step_on_the_part_that_holds_them() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_assumed_in_the_grid()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot)
            dialog = app.screen
            listed = [field.address for field in dialog.fields] if isinstance(dialog, BulkConfirmScreen) else None
            app.exit(None)

    assert isinstance(dialog, BulkConfirmScreen)
    assert listed == [ModeloFormCasillaAddressV1(casilla_id=_ASSUMED)]
