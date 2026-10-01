"""A real modelo 303 reads its rate boxes as the official form prints them, and a filed one asks for nothing.

The form is built by the real read model from the published authority, and the
rows come from the workbench's own page layout. Expected rates are the ones the
official 303 design prints for these rows: 4 % super-reduced, 10 % reduced and
the 2 % transitional rate, grounded on their base bindings. Only a rate box the
design fixes shows its row's rate as its value; a rate box the calculation
fills shows its own value, in its rate unit, and says the row's rate beside it.
A held zero reads as a zero rate, never as an empty box. The design's own
literals ("02100") declare no scale, so a rate box with no grounded rate shows
none, and a literal is only printed as a rate where it states one outright.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import override

import pytest
from textual.app import App, ComposeResult

from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormOrigin,
    ModeloFormPrintedRate,
    ModeloWorkForm,
    address_key,
)
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import (
    ModeloWorkProgress,
    ModeloWorkReview,
    build_modelo_work_review_casillas,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.filing.schema import ModeloValueKind
from ......domain.modelos.calculation_revision import CalculationRevisionState
from ......domain.modelos.codes import ModeloCode
from ....components.theme import install_cadrumo_themes
from ..casilla_list import (
    CasillaList,
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
    grid_value_text,
    rate_note,
    row_value_text,
    value_text,
)
from ..page_items import WorkbenchFilter, first_attention, page_items, section_nav_text, workbench_pages
from ..vocabulary import DONE_MARK, NOT_IMPORTED_MARK, origin_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERCENT = "\u00a0%"
# 02 and 05 are fixed by the design; 166 is calculated, so the rate is its row's and not its own value.
_GROUNDED = {"02": f"4{_PERCENT}", "05": f"10{_PERCENT}"}
_CALCULATED_RATE = ("166", f"2{_PERCENT}")
# 151 and 17 print zeros, the design's placeholder; 154 and 169 are rate boxes no base binding grounds;
# 08, 157, 20 and 23 print literals whose scale nothing declares.
_UNGROUNDED = ("08", "151", "154", "157", "169", "17", "20", "23")


def _form(
    operation: PinnedAuthorityOperation,
    *,
    held: dict[str, Decimal] | None = None,
    lifecycle: CalculationRevisionState | None = None,
) -> ModeloWorkForm:
    period = Period.from_year_and_code(2026, "1T")
    revision_id = str(operation.revision_for_context("303", filing_year=2026, period="1T").id)
    snapshot = modelo_form_snapshot(operation, ModeloCode("303"), 2026, period, revision_id)
    values = held or {}
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000455",
        modelo="303",
        filing_year=2026,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=None,
        lifecycle_state=lifecycle,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            row.model_copy(update={"value": values[str(row.casilla_id)], "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) in values
            else row
            for row in rows
        ),
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout("303", snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def _entries(form: ModeloWorkForm) -> dict[str, CasillaListEntry]:
    """Every row the workbench lays out, by its box number."""
    return {
        item.field.box: item
        for page in workbench_pages(form)
        for item in page_items(page, staged={})
        if isinstance(item, CasillaListEntry) and item.field.box is not None
    }


def test_a_grounded_rate_box_reads_the_rate_and_an_ungrounded_one_claims_none(
    operation: PinnedAuthorityOperation,
) -> None:
    entries = _entries(_form(operation))

    with override_settings(cadrumo_output_language="en"):
        for box, rate in _GROUNDED.items():
            entry = entries[box]
            assert entry.rate_of_row, box
            assert row_value_text(entry, OutputLanguage.EN) == rate, box
            assert value_text(entry, OutputLanguage.EN) == rate, box
            assert rate_note(entry) is None, box
        # A rate box the calculation fills shows its own value, not yet calculated here, and says the rate apart.
        box, rate = _CALCULATED_RATE
        calculated = entries[box]
        assert calculated.rate_of_row
        assert calculated.field.origin is ModeloFormOrigin.NOT_CALCULATED_YET
        assert calculated.field.grounded_rate is not None
        assert row_value_text(calculated, OutputLanguage.EN) == "·"
        assert value_text(calculated, OutputLanguage.EN) == "…"
        assert rate_note(calculated, OutputLanguage.EN) == f"This row's rate is {rate}."
        typed = replace(calculated, staged_text="3,50")
        assert row_value_text(typed, OutputLanguage.EN) == "3,50"
        worked_out = replace(
            calculated,
            field=calculated.field.model_copy(update={"origin": ModeloFormOrigin.CALCULATED, "value": Decimal("0.00")}),
        )
        failed = replace(
            calculated, field=calculated.field.model_copy(update={"origin": ModeloFormOrigin.CALCULATION_FAILED})
        )
        # A worked-out rate in a row grounded on one rate reads that rate, as the form prints it, whatever the
        # base: never a 0 % worked out of an empty base, and with nothing more to say beside it.
        assert rate_note(worked_out, OutputLanguage.EN) is None
        assert row_value_text(worked_out, OutputLanguage.EN) == rate
        assert grid_value_text(worked_out, OutputLanguage.EN) == rate
        assert row_value_text(failed, OutputLanguage.EN) == "·"

        def worked(figure: str) -> str:
            field = calculated.field.model_copy(
                update={"origin": ModeloFormOrigin.CALCULATED, "value": Decimal(figure)}
            )
            return row_value_text(replace(calculated, field=field), OutputLanguage.EN)

        # The row's grounded rate is what the cell reads, at either scale of the worked-out figure; a figure
        # departing from it is a matter for the check, not for the cell, which still prints the row's rate.
        assert worked("2.00") == rate
        assert worked("0.02") == rate
        assert worked("3") == rate
        # An optional rate box nobody filled shows nothing; one holding a zero shows it, and says it was left at 0.
        optional = entries["169"]
        assert optional.field.origin is ModeloFormOrigin.OPTIONAL_EMPTY
        assert optional.field.value is None
        assert row_value_text(optional, OutputLanguage.EN) == "·"
        held_zero = replace(optional, field=optional.field.model_copy(update={"value": Decimal("0.00")}))
        assert row_value_text(held_zero, OutputLanguage.EN) == f"0{_PERCENT}"
        assert grid_value_text(held_zero, OutputLanguage.EN) == f"0{_PERCENT}"
        assert origin_words(held_zero.field) == "Optional, left at 0"
        assert origin_words(optional.field) == "Optional, empty"
        assert row_value_text(entries["05"], OutputLanguage.ES) == f"10{_PERCENT}"
        # A literal that states its rate outright is printed, and the band says only the form prints it.
        stated = replace(
            entries["157"],
            field=entries["157"].field.model_copy(
                update={"printed_rate": ModeloFormPrintedRate(ratio=Decimal("0.0175"), literal="1,75 %")}
            ),
        )
        assert row_value_text(stated, OutputLanguage.EN) == f"1.75{_PERCENT}"
        assert row_value_text(stated, OutputLanguage.ES) == f"1,75{_PERCENT}"
        assert rate_note(stated) == lookup_translation("tui.modelo.workbench.rate.printed_by_form", locale="en")
        for box in _UNGROUNDED:
            entry = entries[box]
            assert entry.rate_of_row, box
            assert entry.field.grounded_rate is None, box
            assert entry.field.printed_rate is None, box
            assert row_value_text(entry, OutputLanguage.EN) == "·", box
            assert rate_note(entry) == lookup_translation("tui.modelo.workbench.rate.not_grounded", locale="en")
        # A box that is not a row's rate box never carries the note.
        assert rate_note(entries["01"]) is None


def test_a_declaration_recorded_as_filed_marks_nothing_to_do(operation: PinnedAuthorityOperation) -> None:
    unheld = _form(operation)
    optional = next(
        field
        for field in unheld.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.origin is ModeloFormOrigin.OPTIONAL_EMPTY
        and field.data_type == "money"
    )
    address = optional.address
    assert isinstance(address, ModeloFormCasillaAddressV1)
    held = {str(address.casilla_id): Decimal("35.00")}
    draft = _form(operation, held=held)
    filed = _form(operation, held=held, lifecycle=CalculationRevisionState.PRESENTADO)
    assert filed.filing is not None

    key = address_key(optional.address)
    assumed = next(field for field in draft.fields() if address_key(field.address) == key)
    assert assumed.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    # Filing keeps the box's origin; only the counts say nothing is left to confirm.
    still_assumed = next(field for field in filed.fields() if address_key(field.address) == key)
    assert still_assumed.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert filed.counts.default_to_confirm == 0

    def to_do(form: ModeloWorkForm) -> set[tuple[str, str]]:
        return {
            item.key
            for page in workbench_pages(form)
            for item in page_items(page, staged={}, mode=WorkbenchFilter.ATTENTION)
            if isinstance(item, CasillaListEntry)
        }

    def marks(form: ModeloWorkForm) -> str:
        pages = workbench_pages(form)
        navigator = [
            section_nav_text(section, 60, recorded=page.recorded) for page in pages for section in page.sections
        ]
        headings = [
            item.text for page in pages for item in page_items(page, staged={}) if isinstance(item, CasillaListHeading)
        ]
        return " | ".join((*navigator, *headings))

    assert key in to_do(draft)
    assert key not in to_do(filed)
    assert not any(
        address_key(field.address) in to_do(filed)
        for field in filed.fields()
        if field.origin in {ModeloFormOrigin.DEFAULT_TO_CONFIRM, ModeloFormOrigin.NEEDS_INPUT}
    )
    assert "◐" not in marks(filed)
    # Nothing on a filed declaration sends the filer to a missing or assumed value.
    attention = first_attention(workbench_pages(filed))
    if attention is not None:
        index, found = attention
        field = next(item for item in workbench_pages(filed)[index].fields() if address_key(item.address) == found)
        assert field.origin not in {ModeloFormOrigin.DEFAULT_TO_CONFIRM, ModeloFormOrigin.NEEDS_INPUT}, found


class _ListHarness(App[None]):
    def __init__(self, items: tuple[CasillaListItem, ...]) -> None:
        super().__init__()
        self._items = items

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList(self._items, language=OutputLanguage.EN)

    def on_mount(self) -> None:
        install_cadrumo_themes(self, appearance="dark")


async def _drawn(items: tuple[CasillaListItem, ...]) -> list[str]:
    with override_settings(cadrumo_output_language="en"):
        app = _ListHarness(items)
        async with app.run_test(size=(160, 400)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            return [widget.render_line(y).text for y in range(widget.size.height)]


def _page_with(form: ModeloWorkForm, box: str) -> tuple[CasillaListItem, ...]:
    for page in workbench_pages(form):
        items = page_items(page, staged={})
        if any(isinstance(item, CasillaListEntry) and item.field.box == box for item in items):
            return items
    raise AssertionError(box)


@pytest.mark.asyncio
async def test_a_filed_declaration_draws_no_attention_mark_but_keeps_its_origin_words(
    operation: PinnedAuthorityOperation,
) -> None:
    unheld = _page_with(_form(operation), "65")
    optional = next(
        item.field
        for item in unheld
        if isinstance(item, CasillaListEntry)
        and item.field.origin is ModeloFormOrigin.OPTIONAL_EMPTY
        and item.field.data_type == "money"
    )
    held = {str(optional.box): Decimal("35.00")}
    draft = _page_with(_form(operation, held=held), "65")
    filed = _page_with(_form(operation, held=held, lifecycle=CalculationRevisionState.PRESENTADO), "65")

    def box(items: tuple[CasillaListItem, ...], number: str) -> CasillaListEntry:
        return next(item for item in items if isinstance(item, CasillaListEntry) and item.field.box == number)

    # A box waiting on an import is not the filer's to type into, filed or not.
    assert box(draft, "65").field.origin is ModeloFormOrigin.NOT_IMPORTED_YET
    assert not box(draft, "65").needs_filer
    assert box(filed, "65").field.origin is ModeloFormOrigin.NOT_IMPORTED_YET
    assert not box(filed, "65").needs_filer
    # An assumed value is, until the declaration is filed.
    assert box(draft, str(optional.box)).field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert box(draft, str(optional.box)).needs_filer
    assert not box(filed, str(optional.box)).needs_filer

    draft_lines = await _drawn(draft)
    filed_lines = await _drawn(filed)
    with override_settings(cadrumo_output_language="en"):
        words = origin_words(box(filed, "65").field)
    row = next(line for line in filed_lines if "[65]" in line)
    assert f" {words}" in row
    waiting = _heading_over(filed, "65")
    # A section still holding a value that was never imported is not done, even once filed.
    assert waiting.mark == NOT_IMPORTED_MARK
    assert not waiting.text.startswith(DONE_MARK.glyph)
    # The same draft still marks what is left to do, so the filed page's silence is the filing's doing.
    assert any(" ◐ " in line for line in draft_lines)
    for line in filed_lines:
        assert "▲" not in line and "◐" not in line, line
        assert " ! " not in line, line


def _heading_over(items: tuple[CasillaListItem, ...], number: str) -> CasillaListHeading:
    """The section heading a box is listed under."""
    heading: CasillaListHeading | None = None
    for item in items:
        if isinstance(item, CasillaListHeading) and item.level == 0:
            heading = item
        if isinstance(item, CasillaListEntry) and item.field.box == number and heading is not None:
            return heading
    raise AssertionError(number)
