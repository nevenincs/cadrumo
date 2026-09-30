"""A casilla row reads like the official form: whole box numbers, whole labels, the origin beside the value.

Every test renders the list through a real Textual pilot and reads the lines
:meth:`CasillaList.render_line` paints, at the widths where the row changes
shape. Expectations are written by hand, never read back from the renderer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import override

import pytest
from textual.app import App, ComposeResult

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.work_form_models import (
    ModeloFormBlocker,
    ModeloFormCasillaAddressV1,
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloFormValueSource,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.calculations.registry.schema_surfaces import CasillaConstraints
from ....components.theme import install_cadrumo_themes
from ..casilla_list import (
    CasillaList,
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
    Density,
    description_text,
)
from ..vocabulary import EARLIER_FILING_GLYPH, ORIGIN_GLYPHS, origin_text, origin_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EURO = "\u00a0\u20ac"
_PERCENT = "\u00a0%"


def _field(
    box: str,
    label: str,
    origin: ModeloFormOrigin,
    value: Decimal | None = None,
    *,
    help_text: str | None = None,
    disclosure: ModeloFormTextDisclosure = ModeloFormTextDisclosure.LOCALIZED,
    blocked: bool = False,
    data_type: str = "money",
    constraints: CasillaConstraints | None = None,
    source: ModeloFormValueSource | None = None,
) -> ModeloFormField:
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=box),
        box=box,
        label=ModeloFormText(text=label, disclosure=disclosure),
        help=help_text,
        data_type=data_type,
        value=value,
        origin=origin,
        editability=ModeloFormEditability.EDITABLE_VALUE,
        required=origin is ModeloFormOrigin.NEEDS_INPUT,
        blockers=(ModeloFormBlocker(code="synthetic_blocker"),) if blocked else (),
        constraints=constraints,
        source=source,
    )


def _bounds(maximum: str) -> CasillaConstraints:
    return CasillaConstraints(
        min_value=Decimal(0),
        max_value=Decimal(maximum),
        legal_refs=("ley-37-1992:art-104",),
        source_refs=("aeat-manual",),
    )


class _ListHarness(App[None]):
    def __init__(self, items: tuple[CasillaListItem, ...], language: OutputLanguage, density: Density) -> None:
        super().__init__()
        self._items = items
        self._language = language
        self._density = density

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList(self._items, language=self._language, density=self._density, id="list")

    def on_mount(self) -> None:
        install_cadrumo_themes(self, appearance="dark")


async def _render(
    items: tuple[CasillaListItem, ...],
    *,
    width: int,
    language: OutputLanguage = OutputLanguage.EN,
    density: Density = "comfortable",
) -> list[str]:
    """Paint the list at one width and return its non-blank lines."""
    with override_settings(cadrumo_output_language=language.value):
        app = _ListHarness(items, language, density)
        async with app.run_test(size=(width, 40)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            lines = [widget.render_line(y).text for y in range(widget.size.height)]
    return [line.rstrip() for line in lines if line.strip()]


def _line_with(lines: list[str], text: str) -> str:
    return next(line for line in lines if text in line)


@pytest.mark.asyncio
async def test_the_box_column_is_as_wide_as_the_widest_box_number_on_the_page() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("01", "Income", ModeloFormOrigin.ENTERED, Decimal("10"))),
        CasillaListEntry(_field("0670", "Result", ModeloFormOrigin.CALCULATED, Decimal("1106.69"))),
        CasillaListEntry(_field("123456", "Six-digit box", ModeloFormOrigin.ENTERED, Decimal("1"))),
    )

    for width in (60, 80, 160):
        lines = await _render(items, width=width)
        assert "[0670]" in _line_with(lines, "Result")
        assert "[123456]" in _line_with(lines, "Six-digit box")
        assert not any("…" in line for line in lines)
        # Every label starts in the same column, so a short box number is padded, not the long one cut.
        starts = {_line_with(lines, label).index(label) for label in ("Income", "Result", "Six-digit box")}
        assert len(starts) == 1


@pytest.mark.asyncio
async def test_a_long_label_wraps_onto_further_lines_and_is_never_cut() -> None:
    label = "Reductions for net yields generated over more than two years or obtained in a notoriously irregular way"
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("0011", label, ModeloFormOrigin.ENTERED, Decimal("500"))),
        CasillaListEntry(_field("0012", "Total", ModeloFormOrigin.CALCULATED, Decimal("24000"))),
    )

    densities: tuple[Density, ...] = ("comfortable", "compact")
    for density in densities:
        lines = await _render(items, width=80, density=density)
        first = _line_with(lines, "Reductions")
        start = first.index("Reductions")
        continuation = [line[start:].strip() for line in lines[1 : lines.index(_line_with(lines, "[0012]"))]]
        label_column = [first[start : first.index("500.00" + _EURO)].strip(), *continuation]
        assert len(label_column) >= 2
        assert " ".join(label_column) == label, f"the label lost words in {density} density"
        assert not any("…" in line for line in lines)
        assert ORIGIN_GLYPHS[ModeloFormOrigin.ENTERED] in first


@pytest.mark.asyncio
async def test_only_the_description_line_is_cut_and_it_never_repeats_the_box_number() -> None:
    help_text = "Box 0003: gross amount of monetary remuneration, including every compensatory payment received. More."
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("0003", "Monetary pay", ModeloFormOrigin.ENTERED, Decimal("1"), help_text=help_text)),
    )

    lines = await _render(items, width=70)

    assert len(lines) == 2
    note = lines[1]
    assert note.strip().startswith("Gross amount of monetary")
    assert "Box 0003" not in note
    assert note.endswith("…")


def test_a_description_that_opens_by_naming_its_box_loses_that_opening_in_every_language() -> None:
    def described(help_text: str) -> str | None:
        return description_text(_field("0002", "x", ModeloFormOrigin.ENTERED, help_text=help_text))

    assert described("Box 0002: use this when you allocate advance payments.") == (
        "Use this when you allocate advance payments."
    )
    assert described("Casilla 01: base imponible del IVA devengado.") == "Base imponible del IVA devengado."
    assert described("Casella 01: base imposable de l'IVA meritat.") == "Base imposable de l'IVA meritat."
    assert described("0002. mező: akkor használja, ha a szerzői jogok.") == "Akkor használja, ha a szerzői jogok."
    # A description that only starts with a number, or names something else, is kept whole.
    assert described("Enter expense 3: the amount paid.") == "Enter expense 3: the amount paid."
    assert described("Producto 1: aceite.") == "Producto 1: aceite."
    assert described("Box 700 of modelo 303, tax year 2022.") == "Box 700 of modelo 303, tax year 2022."


@pytest.mark.asyncio
async def test_the_origin_words_sit_right_after_the_value_when_they_fit() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("01", "Net yield", ModeloFormOrigin.CALCULATED, Decimal("500"))),
        CasillaListEntry(_field("06", "Withholdings", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("0"))),
    )

    lines = await _render(items, width=200)

    row = _line_with(lines, "Net yield")
    value_end = row.index("500.00" + _EURO) + len("500.00" + _EURO)
    assert row[value_end:].startswith(" = Calculated")
    # The value follows the longest label on the page, not the far edge of a wide terminal.
    assert value_end < row.index("Net yield") + len("Withholdings") + 20
    assumed = _line_with(lines, "Withholdings")
    assert assumed.endswith("0.00" + _EURO + " ◐ Assumed, please confirm")


@pytest.mark.asyncio
async def test_a_narrow_row_keeps_the_glyph_and_leaves_the_words_to_the_help_band() -> None:
    long_label = "Withholdings and payments on account for professional activities in the quarter"
    field = _field("0006", long_label, ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("0"))
    items: tuple[CasillaListItem, ...] = (CasillaListEntry(field),)

    for width in (24, 40, 60):
        lines = await _render(items, width=width)
        first = lines[0]
        assert "[0006]" in first
        assert first.endswith(ORIGIN_GLYPHS[ModeloFormOrigin.DEFAULT_TO_CONFIRM]), (width, first)
        assert "Assumed" not in "\n".join(lines)

    with override_settings(cadrumo_output_language="en"):
        assert origin_words(field) == "Assumed, please confirm"
        assert origin_text(field) == "◐ Assumed, please confirm"
    with override_settings(cadrumo_output_language="es"):
        assert origin_words(field) == "Supuesta, confírmala"


@pytest.mark.asyncio
async def test_a_narrow_row_says_in_words_when_a_box_blocks_filing() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(
            _field(
                "0006",
                "Withholdings and payments on account for professional activities",
                ModeloFormOrigin.ENTERED,
                Decimal("5"),
                blocked=True,
            )
        ),
    )

    lines = await _render(items, width=60)

    assert "▲" in lines[0][: lines[0].index("[0006]")]
    assert lines[-1].strip() == "Blocks filing"


@pytest.mark.asyncio
async def test_a_label_shown_in_spanish_says_so_in_the_filers_language() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListHeading("I. Rendimientos"),
        CasillaListEntry(
            _field(
                "01",
                "Ingresos computables",
                ModeloFormOrigin.ENTERED,
                Decimal("1"),
                disclosure=ModeloFormTextDisclosure.SPANISH_FALLBACK,
            )
        ),
    )

    english = await _render(items, width=120, language=OutputLanguage.EN)
    catalan = await _render(items, width=120, language=OutputLanguage.CA)
    spanish = await _render(items, width=120, language=OutputLanguage.ES)

    assert "Ingresos computables (in Spanish)" in _line_with(english, "Ingresos")
    assert "Ingresos computables (en castellà)" in _line_with(catalan, "Ingresos")
    assert "(es)" not in "\n".join(english + catalan)
    assert "(" not in _line_with(spanish, "Ingresos")


@pytest.mark.asyncio
async def test_a_rate_reads_as_a_percentage_only_where_its_bounds_declare_the_unit() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(
            _field(
                "44", "Pro rata", ModeloFormOrigin.ENTERED, Decimal("21"), data_type="ratio", constraints=_bounds("100")
            )
        ),
        CasillaListEntry(
            _field(
                "45", "Share", ModeloFormOrigin.ENTERED, Decimal("0.125"), data_type="ratio", constraints=_bounds("1")
            )
        ),
        CasillaListEntry(_field("02", "VAT rate", ModeloFormOrigin.CALCULATED, Decimal("4"), data_type="ratio")),
    )

    lines = await _render(items, width=100, language=OutputLanguage.ES)

    assert f"21{_PERCENT} " in _line_with(lines, "Pro rata")
    assert f"12,5{_PERCENT} " in _line_with(lines, "Share")
    # A rate whose unit the registry does not declare keeps its bare figure rather than guessing one.
    undeclared = _line_with(lines, "VAT rate")
    assert " 4 " in undeclared
    assert "%" not in undeclared


def _sourced(origin: ModeloFormOrigin, source: ModeloFormValueSource) -> ModeloFormField:
    return _field("05", "Carried amount", origin, Decimal("500"), source=source)


def _earlier(*periods: Period) -> ModeloFormValueSource:
    return ModeloFormValueSource(
        family=SourceFamily.EARLIER_FILINGS,
        earlier_filings=tuple(ModeloFormEarlierFiling(modelo="130", period=period) for period in periods),
    )


def test_a_value_from_a_source_names_the_kind_of_place_it_comes_from() -> None:
    imported = ModeloFormOrigin.IMPORTED
    q4 = Period.from_year_and_code(2025, "4T")
    q3 = Period.from_year_and_code(2025, "3T")

    with override_settings(cadrumo_output_language="en"):
        assert origin_words(_sourced(imported, ModeloFormValueSource(family=SourceFamily.RECORDS))) == (
            "From your records"
        )
        assert origin_words(_sourced(imported, ModeloFormValueSource(family=SourceFamily.REGISTERS))) == (
            "From a register you keep"
        )
        assert origin_words(_sourced(imported, ModeloFormValueSource(family=SourceFamily.PROFILE))) == (
            "From your profile"
        )
        assert origin_words(_sourced(imported, ModeloFormValueSource(family=SourceFamily.AEAT_DRAFT))) == (
            "From AEAT data"
        )
        assert origin_words(_sourced(imported, ModeloFormValueSource(family=SourceFamily.FIXED_BY_DESIGN))) == (
            "Set by the form"
        )
        assert origin_words(_sourced(imported, _earlier(q4))) == "From modelo 130, 4th quarter 2025"
        # Two named declarations, or none named, are never narrowed to one.
        assert origin_words(_sourced(imported, _earlier(q3, q4))) == "From an earlier declaration"
        assert origin_words(_sourced(imported, _earlier())) == "From an earlier declaration"
        replaced = _sourced(ModeloFormOrigin.OVERRIDES_SOURCE, ModeloFormValueSource(family=SourceFamily.RECORDS))
        assert origin_words(replaced) == "Yours, replaces your records"
        waiting = _sourced(ModeloFormOrigin.NOT_IMPORTED_YET, ModeloFormValueSource(family=SourceFamily.PROFILE))
        assert origin_words(waiting) == "Not in your profile yet"
        # Without a source, or for an origin that is not a source's, the origin speaks for itself.
        assert origin_words(_field("05", "x", imported, Decimal("1"))) == "Imported"
        entered = _sourced(ModeloFormOrigin.ENTERED, ModeloFormValueSource(family=SourceFamily.RECORDS))
        assert origin_words(entered) == "Entered by you"
    with override_settings(cadrumo_output_language="es"):
        assert origin_words(_sourced(imported, ModeloFormValueSource(family=SourceFamily.RECORDS))) == (
            "De tus registros"
        )
        assert origin_words(_sourced(imported, _earlier(q4))) == "Del modelo 130, 4.º trimestre 2025"


@pytest.mark.asyncio
async def test_the_row_carries_the_source_words_and_marks_a_carried_value_apart() -> None:
    q4 = Period.from_year_and_code(2025, "4T")
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("01", "Income", ModeloFormOrigin.IMPORTED, Decimal("24000"), source=_records())),
        CasillaListEntry(_sourced(ModeloFormOrigin.IMPORTED, _earlier(q4))),
    )

    lines = await _render(items, width=140)

    income = _line_with(lines, "Income")
    assert income.endswith(f"24,000.00{_EURO} {ORIGIN_GLYPHS[ModeloFormOrigin.IMPORTED]} From your records")
    carried = _line_with(lines, "Carried amount")
    assert carried.endswith(f"500.00{_EURO} {EARLIER_FILING_GLYPH} From modelo 130, 4th quarter 2025")
    with override_settings(cadrumo_output_language="en"):
        assert origin_text(_sourced(ModeloFormOrigin.IMPORTED, _earlier(q4))).startswith(EARLIER_FILING_GLYPH)
    assert EARLIER_FILING_GLYPH not in ORIGIN_GLYPHS.values()


def _records() -> ModeloFormValueSource:
    return ModeloFormValueSource(family=SourceFamily.RECORDS)


@pytest.mark.asyncio
async def test_an_empty_box_says_so_once_in_its_origin_words_and_keeps_a_held_zero() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("01", "Optional amount", ModeloFormOrigin.OPTIONAL_EMPTY)),
        CasillaListEntry(_field("02", "Pending total", ModeloFormOrigin.NOT_CALCULATED_YET, Decimal("7"))),
        CasillaListEntry(_field("03", "Waiting amount", ModeloFormOrigin.NOT_IMPORTED_YET)),
        CasillaListEntry(_field("04", "Emptied amount", ModeloFormOrigin.CLEARED)),
        CasillaListEntry(_field("05", "Missing amount", ModeloFormOrigin.NEEDS_INPUT)),
        CasillaListEntry(_field("06", "Other amount", ModeloFormOrigin.NOT_APPLICABLE)),
        CasillaListEntry(_field("07", "Zero amount", ModeloFormOrigin.OPTIONAL_EMPTY, Decimal("0"))),
    )

    lines = await _render(items, width=140)

    assert _line_with(lines, "Optional amount").endswith(" · ○ Optional, empty")
    assert _line_with(lines, "Pending total").endswith(" · ◌ Not calculated yet")
    assert _line_with(lines, "Waiting amount").endswith(" · ⇣ Not imported yet")
    assert _line_with(lines, "Emptied amount").endswith(" · □ Cleared by you")
    assert _line_with(lines, "Missing amount").endswith(" · ! Needs your input")
    assert _line_with(lines, "Other amount").endswith(" · - Not applicable")
    # A zero is a value, not an absence: it is shown as one, and its words never call the box empty.
    zero = _line_with(lines, "Zero amount")
    assert zero.endswith("0.00" + _EURO + " ○ Optional, left at 0")
    assert "empty" not in zero
    # A box holding nothing shows no number beside its words.
    assert not any(character.isdigit() for character in _line_with(lines, "Optional amount").split("]", 1)[1])
    assert not any("no data" in line or "…" in line for line in lines)


@pytest.mark.asyncio
async def test_a_wrapped_label_never_breaks_at_a_no_break_space() -> None:
    label = "Deduction under Real Decreto 1624/1992, art.\u00a071"
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("71", label, ModeloFormOrigin.CALCULATED, Decimal("1"))),
    )

    for width in range(34, 52, 2):
        lines = await _render(items, width=width)
        assert len(lines) > 1, width
        assert any("art.\u00a071" in line for line in lines), (width, lines)


@pytest.mark.asyncio
async def test_on_a_wide_terminal_the_value_stays_beside_a_long_label() -> None:
    long_label = " ".join(["Deduction for investment in the main residence under the transitional regime"] * 2)
    items: tuple[CasillaListItem, ...] = (
        CasillaListEntry(_field("01", "Income", ModeloFormOrigin.CALCULATED, Decimal("500"))),
        CasillaListEntry(_field("02", long_label, ModeloFormOrigin.CALCULATED, Decimal("7"))),
    )

    lines = await _render(items, width=200)

    income = _line_with(lines, "Income")
    value_end = income.index("500.00" + _EURO) + len("500.00" + _EURO)
    # The label column stops at sixty cells, so the value sits there, not at the far edge.
    assert value_end - income.index("Income") <= 60 + 1 + len("500.00" + _EURO)
    assert income.endswith("= Calculated")
    # The long label wraps instead of pushing the value away.
    assert len([line for line in lines if line.strip() and "Income" not in line]) >= 2
