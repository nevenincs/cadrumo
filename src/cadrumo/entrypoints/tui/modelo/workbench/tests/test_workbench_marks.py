"""Every mark the workbench draws means one thing, and a section shows the most severe one it holds.

The registry refuses, at import and for any set handed to it, a glyph that
means two things or a meaning drawn two ways; the navigator's section mark
ranks a blocker above a missing value above an assumed one.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ......application.modelo.work_form_models import (
    ModeloFormBlocker,
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormOrigin,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
)
from ......core.config import override_settings
from ......core.i18n.render import lookup_translation
from ..page_items import section_heading_text, section_mark, section_nav_text
from ..vocabulary import (
    BLOCKS_MARK,
    CHECK_MARK,
    CONFIRM_MARK,
    DONE_MARK,
    HERE_MARK,
    MISSING_MARK,
    ORIGIN_MARKS,
    WORKBENCH_MARKS,
    WorkbenchMark,
    origin_words,
    require_one_meaning_per_glyph,
)
from .workbench_fixture import form_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_shipped_marks_give_each_glyph_one_meaning_and_each_meaning_one_glyph() -> None:
    require_one_meaning_per_glyph(WORKBENCH_MARKS)

    # A glyph repeats across surfaces only as the same meaning: the row's blocker is the stepper's.
    assert BLOCKS_MARK.translation_key == "tui.modelo.workbench.level.blocks"
    # The marks that used to mean two things now mean one.
    by_glyph = {mark.glyph: mark.translation_key for mark in WORKBENCH_MARKS}
    assert by_glyph["●"] == "tui.modelo.workbench.origin.entered"
    assert by_glyph["○"] == "tui.modelo.workbench.origin.optional_empty"
    assert by_glyph["!"] == "tui.modelo.workbench.origin.needs_input"
    assert HERE_MARK.glyph == "▸"
    assert CHECK_MARK.glyph == "◆"


def test_every_mark_has_words_in_every_language() -> None:
    for mark in WORKBENCH_MARKS:
        for locale in ("es", "en", "ca", "hu"):
            assert lookup_translation(mark.translation_key, locale=locale), (mark, locale)


def test_a_glyph_given_a_second_meaning_is_refused() -> None:
    entered = ORIGIN_MARKS[ModeloFormOrigin.ENTERED]
    current_step = WorkbenchMark(entered.glyph, translation_key="tui.modelo.workbench.legend.name.here")

    with pytest.raises(ValueError, match="means more than one thing"):
        require_one_meaning_per_glyph((*WORKBENCH_MARKS, current_step))


def test_a_meaning_drawn_with_a_second_glyph_is_refused() -> None:
    second_done = WorkbenchMark("✔", translation_key=DONE_MARK.translation_key)

    with pytest.raises(ValueError, match="more than one glyph"):
        require_one_meaning_per_glyph((*WORKBENCH_MARKS, second_done))


def test_repeating_a_mark_with_its_own_meaning_is_allowed() -> None:
    require_one_meaning_per_glyph((*WORKBENCH_MARKS, BLOCKS_MARK, DONE_MARK))


def _section(*fields: ModeloFormField) -> ModeloFormSection:
    return ModeloFormSection(
        id="s1",
        heading=ModeloFormText(text="I. Activities", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        official_heading=None,
        blocks=tuple(ModeloFormFieldBlock(id=f"f{item.box}", field=item) for item in fields),
        counts=ModeloFormCounts(
            total=len(fields),
            needs_input=0,
            entered=0,
            imported=0,
            calculated=0,
            overridden=0,
            default_to_confirm=0,
            not_applicable=0,
            blocked=0,
        ),
    )


def test_a_section_shows_the_most_severe_thing_it_still_holds() -> None:
    entered = form_field("01", "Income", ModeloFormOrigin.ENTERED, Decimal("1"))
    assumed = form_field("02", "Expenses", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("0"))
    missing = form_field("03", "Withholdings", ModeloFormOrigin.NEEDS_INPUT)
    blocked = form_field("04", "Payments", ModeloFormOrigin.ENTERED, Decimal("2")).model_copy(
        update={"blockers": (ModeloFormBlocker(code="synthetic_blocker"),)}
    )

    assert section_mark(_section(entered)) == DONE_MARK
    assert section_mark(_section(entered, assumed)) == CONFIRM_MARK
    assert section_mark(_section(assumed, missing)) == MISSING_MARK
    assert section_mark(_section(assumed, missing, blocked)) == BLOCKS_MARK
    with override_settings(cadrumo_output_language="en"):
        assert section_nav_text(_section(assumed, missing, blocked), 40) == "▲ I. Activities (3)"
        assert section_nav_text(_section(entered, assumed), 40) == "◐ I. Activities (1)"
        assert section_nav_text(_section(entered), 40) == "✓ I. Activities"
        assert section_heading_text(_section(entered, missing)).startswith("! ")


def test_an_informational_value_reads_as_a_reference_value() -> None:
    reference = form_field("99", "Rate", ModeloFormOrigin.INFORMATIONAL, Decimal("21"))

    with override_settings(cadrumo_output_language="en"):
        assert origin_words(reference) == "Reference value"
    with override_settings(cadrumo_output_language="es"):
        assert origin_words(reference) == "Valor de referencia"
