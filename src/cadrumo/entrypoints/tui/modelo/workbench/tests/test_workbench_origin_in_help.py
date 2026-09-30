"""The workbench says where a box's value comes from in full wherever it explains the box.

Driven through the real workbench over the synthetic declaration. With box 01
taken from AEAT tax data imported on a known day, the help band under the
cursor, the box panel and a search hit each say the day the data was imported.
With box 01 a zero carried where no earlier declaration applies, the help band
says why it holds zero, so the filer does not look for a filing that does not
exist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.work_form_models import (
    ModeloFormAeatData,
    ModeloFormCasillaAddressV1,
    ModeloFormValueSource,
    ModeloWorkForm,
    address_key,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..editor import CasillaEditorScreen
from ..screen import ModeloWorkbenchScreen
from ..search import WorkbenchSearchPanel
from ..vocabulary import aeat_imported_on
from ..wording import date_text
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_IMPORTED_AT = datetime(2026, 4, 2, 10, 30, tzinfo=UTC)
_INCOME = "01"


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _from_aeat_data() -> ModeloWorkForm:
    source = ModeloFormValueSource(
        family=SourceFamily.AEAT_DRAFT, source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
    )
    form = replace_fields(synthetic_form(needs_input=False), {_INCOME: {"source": source}})
    return form.model_copy(update={"aeat_data": ModeloFormAeatData(snapshot_id="snapshot-1", imported_at=_IMPORTED_AT)})


@pytest.mark.asyncio
async def test_the_help_band_the_panel_and_search_say_the_day_the_aeat_data_was_imported() -> None:
    form = _from_aeat_data()
    imported = aeat_imported_on(form)
    assert imported is not None
    with override_settings(cadrumo_output_language="en"):
        dated = tr("tui.modelo.workbench.origin_source.aeat_imported_on", date=date_text(imported, OutputLanguage.EN))
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            screen.query_one(CasillaList).focus_address(address_key(ModeloFormCasillaAddressV1(casilla_id=_INCOME)))
            await _settle(pilot)
            band = str(screen.query_one("#wb-help", Static).render())
            await pilot.press("enter")
            await _settle(pilot, 6)
            panel = app.screen
            panel_text = (
                "\n".join(str(widget.render()) for widget in panel.query(Static))
                if isinstance(panel, CasillaEditorScreen)
                else ""
            )
            await pilot.press("escape")
            await _settle(pilot)
            await pilot.press("slash", *_INCOME)
            await _settle(pilot)
            hits = screen.query_one(WorkbenchSearchPanel).hits
            app.exit(None)

    assert dated in band
    assert isinstance(panel, CasillaEditorScreen)
    assert dated in panel_text
    income = [hit for hit in hits if hit.box == _INCOME]
    assert income and all(hit.origin.endswith(dated) for hit in income)


@pytest.mark.asyncio
async def test_the_help_band_says_why_a_carry_with_no_earlier_declaration_holds_zero() -> None:
    source = ModeloFormValueSource(family=SourceFamily.EARLIER_FILINGS, source_kind=BindingSourceKind.PREVIOUS_FILING)
    form = replace_fields(synthetic_form(needs_input=False), {_INCOME: {"source": source, "value": Decimal("0")}})
    with override_settings(cadrumo_output_language="en"):
        explanation = tr("tui.modelo.workbench.help.origin_no_earlier_declaration")
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            screen.query_one(CasillaList).focus_address(address_key(ModeloFormCasillaAddressV1(casilla_id=_INCOME)))
            await _settle(pilot)
            band = str(screen.query_one("#wb-help", Static).render())
            app.exit(None)

    assert explanation in band
