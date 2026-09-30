"""A real modelo 303 reads its rate boxes as the official form prints them, and a filed one asks for nothing.

The form is built by the real read model from the published authority, and the
rows come from the workbench's own page layout. Expected rates are the ones the
official 303 design prints for these rows: 4 % super-reduced, 10 % reduced and
the 2 % transitional rate, grounded on their base bindings. The design's own
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
    rate_note,
    row_value_text,
    value_text,
)
from ..page_items import WorkbenchFilter, first_attention, page_items, section_nav_text, workbench_pages
from ..vocabulary import DONE_MARK, origin_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERCENT = "\u00a0%"
_GROUNDED = {"02": f"4{_PERCENT}", "05": f"10{_PERCENT}", "166": f"2{_PERCENT}"}
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
    fixed = {
        lookup_translation("tui.modelo.workbench.value.fixed_by_design", locale=item.value) for item in OutputLanguage
    }

    with override_settings(cadrumo_output_language="en"):
        for box, rate in _GROUNDED.items():
            entry = entries[box]
            assert entry.rate_of_row, box
            assert row_value_text(entry, OutputLanguage.EN) == rate, box
            assert value_text(entry, OutputLanguage.EN) == rate, box
            assert rate_note(entry) is None, box
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
            assert value_text(entry, OutputLanguage.EN) not in fixed, box
            assert rate_note(entry) == lookup_translation("tui.modelo.workbench.rate.not_grounded", locale="en")
        # A box that is not a row's rate box never carries the note.
        assert rate_note(entries["01"]) is None
        assert not any(row_value_text(entry, OutputLanguage.EN) in fixed for entry in entries.values())


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
        navigator = [section_nav_text(section, 60) for page in pages for section in page.sections]
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
    draft = _page_with(_form(operation), "65")
    filed = _page_with(_form(operation, lifecycle=CalculationRevisionState.PRESENTADO), "65")

    def box(items: tuple[CasillaListItem, ...]) -> CasillaListEntry:
        return next(item for item in items if isinstance(item, CasillaListEntry) and item.field.box == "65")

    assert box(draft).field.origin is ModeloFormOrigin.NOT_IMPORTED_YET
    assert box(draft).needs_filer
    assert box(filed).field.origin is ModeloFormOrigin.NOT_IMPORTED_YET
    assert not box(filed).needs_filer

    draft_lines = await _drawn(draft)
    filed_lines = await _drawn(filed)
    with override_settings(cadrumo_output_language="en"):
        words = origin_words(box(filed).field)
    row = next(line for line in filed_lines if "[65]" in line)
    assert f" {words}" in row
    headings = [item.text for item in filed if isinstance(item, CasillaListHeading) and item.level == 0]
    assert headings and all(heading.startswith(DONE_MARK.glyph) for heading in headings)
    # The same draft still marks what is left to do, so the filed page's silence is the filing's doing.
    assert any(" ! " in line or " ◐ " in line for line in draft_lines)
    for line in filed_lines:
        assert "▲" not in line and "◐" not in line, line
        assert " ! " not in line, line
