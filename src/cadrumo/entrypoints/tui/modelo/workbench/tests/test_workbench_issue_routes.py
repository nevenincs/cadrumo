"""The workbench goes where the findings list leads: the owning area, or the confirm step for one part of the form.

Driven through the real workbench over the synthetic declaration, opening the
findings list with ``i``. Asking there to open the area that owns a value fed
by the filer's records leaves the workbench for that area through the
navigation it was given. Asking with ``b`` over a finding to confirm the
assumed values opens the confirm step on the section that holds the finding's
box, and leaves another section's assumed values out.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ......application.modelo.source_policy import SourceSurface
from ......application.modelo.withholding_total_reconciliation import WITHHOLDING_TOTAL_MISMATCH_KEY
from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
)
from ......application.modelo.work_form_findings import ModeloFormIssue
from ......application.modelo.work_form_models import ModeloWorkForm
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1
from ....tests.settling import settle
from ..bulk_confirm import BulkConfirmScreen
from ..editor import area_words
from ..issues import WorkbenchIssuesScreen
from ..screen import ModeloWorkbenchScreen
from ..sources import surface_target
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ASSUMED = "07"
_OTHER_ASSUMED = "03"


def _finding_on(box: str) -> ModeloFormIssue:
    return ModeloFormIssue(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=box,
            message_locale_key="application.modelo.findings.oss_evidence_missing",
            legal_refs=("ley-37-1992:art-99",),
        ),
        box=box,
    )


def _assumed_in_two_sections() -> ModeloWorkForm:
    """Box 07 assumed in the IVA grid's section and box 03 assumed in the first section, with a finding on 07."""
    form = synthetic_form(needs_input=False)
    assumed = {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")}
    form = replace_fields(
        form,
        {
            _ASSUMED: assumed,
            _OTHER_ASSUMED: {**assumed, "editability": ModeloFormEditability.EDITABLE_VALUE},
        },
    )
    counts = form.counts.model_copy(update={"default_to_confirm": 2})
    return form.model_copy(update={"counts": counts, "issues": (_finding_on(_ASSUMED),)})


@pytest.mark.asyncio
async def test_opening_the_owning_area_from_the_findings_leaves_for_that_area() -> None:
    form = synthetic_form(needs_input=False).model_copy(update={"issues": (_finding_on("01"),)})
    opened: list[TuiNavigationTargetV1] = []
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions(), navigate=opened.append)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(pilot)
            await pilot.press("i")
            await settle(pilot)
            await pilot.press("end")
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            app.exit(None)

    target = surface_target(SourceSurface.LEDGER)
    assert target is not None
    assert opened == [target]


@pytest.mark.asyncio
async def test_b_on_a_finding_confirms_only_the_assumed_values_of_its_section() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_assumed_in_two_sections()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(pilot)
            await pilot.press("i")
            await settle(pilot)
            # The finding worth checking is the list's last entry, below the assumed values.
            await pilot.press("end")
            await settle(pilot)
            await pilot.press("b")
            await settle(pilot)
            dialog = app.screen
            listed = [field.address for field in dialog.fields] if isinstance(dialog, BulkConfirmScreen) else []
            app.exit(None)

    assert isinstance(dialog, BulkConfirmScreen)
    assert listed == [ModeloFormCasillaAddressV1(casilla_id=_ASSUMED)]
    assert ModeloFormCasillaAddressV1(casilla_id=_OTHER_ASSUMED) not in listed


def _withholding_total_finding_on(box: str) -> ModeloFormIssue:
    """The Modelo 190 finding that compares its withholding total with the 111 returns, with synthetic figures."""
    return ModeloFormIssue(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=box,
            message_locale_key=WITHHOLDING_TOTAL_MISMATCH_KEY,
            message_facts={
                "modelo": "190",
                "filing_year": filing_year_envelope().years[-1],
                "source_modelo": "111",
                "checked_periods": "1T|2T|3T|4T",
                "summary_total": Decimal("760.00"),
                "periodic_total": Decimal("9405.00"),
                "gap": Decimal("8645.00"),
            },
            legal_refs=("rd-439-2007:art-108",),
        ),
        box=box,
    )


async def _open_second_door(form: ModeloWorkForm, key: str) -> tuple[list[TuiNavigationTargetV1], list[str]]:
    """Open the findings list over ``form``, press ``key`` on its last entry and report where the app went."""
    opened: list[TuiNavigationTargetV1] = []
    footer: list[str] = []
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions(), navigate=opened.append)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(pilot)
            await pilot.press("i")
            await settle(pilot)
            await pilot.press("end")
            await settle(pilot)
            dialog = app.screen
            if isinstance(dialog, WorkbenchIssuesScreen):
                footer = [
                    str(b.description)
                    for k in ("a", "o")
                    for b in dialog._bindings.key_to_bindings.get(k, [])
                    if b.show
                ]
            await pilot.press(key)
            await settle(pilot)
            app.exit(None)
    return opened, footer


@pytest.mark.asyncio
async def test_a_finding_with_two_doors_offers_each_door_by_its_own_area_words() -> None:
    form = synthetic_form(needs_input=False).model_copy(update={"issues": (_withholding_total_finding_on("01"),)})
    opened, footer = await _open_second_door(form, "a")
    withholding = surface_target(SourceSurface.WITHHOLDING)
    assert withholding is not None
    assert opened == [withholding]
    with override_settings(cadrumo_output_language="en"):
        assert footer == [
            tr("workspace.modelo.issues.open_area", area=area_words(SourceSurface.WITHHOLDING)),
            tr("workspace.modelo.issues.open_area", area=area_words(SourceSurface.DECLARATIONS)),
        ]


@pytest.mark.asyncio
async def test_the_second_door_opens_the_declarations_it_was_compared_with() -> None:
    form = synthetic_form(needs_input=False).model_copy(update={"issues": (_withholding_total_finding_on("01"),)})
    opened, _ = await _open_second_door(form, "o")
    declarations = surface_target(SourceSurface.DECLARATIONS)
    assert declarations is not None
    assert opened == [declarations]


@pytest.mark.asyncio
async def test_a_finding_with_only_one_door_leaves_the_second_key_idle() -> None:
    form = synthetic_form(needs_input=False).model_copy(update={"issues": (_finding_on("01"),)})
    opened, footer = await _open_second_door(form, "o")
    assert opened == []
    with override_settings(cadrumo_output_language="en"):
        assert footer == [tr("workspace.modelo.issues.open_area", area=area_words(SourceSurface.LEDGER))]
