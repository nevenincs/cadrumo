"""One compile's marks become the stored form's slots, written as each position needs.

A page is written by hand carrying marks in the four positions a page offers --
a text node, an attribute value, the ``<title>`` element, and bare markup -- and
the strings each position must receive are stated here rather than taken from
the module. The expected renderings are the ones the writers that own those
positions produce: the docutils HTML writer escapes ``& < > " @`` in text and
folds whitespace in an attribute value, while the theme's ``<title>`` reaches
the page through Jinja, which escapes ``& < > " '`` and leaves ``@`` alone. The
apostrophe is the clearest case of why a mark must declare its writer: docutils
leaves it, Jinja writes ``&#39;`` and a generator's own :func:`html.escape`
writes ``&#x27;``, and the three are indistinguishable from the markup around
them.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from ..compile_slots import (
    MARK_CLOSE,
    MARK_OPEN,
    SLOTS_SCHEMA,
    CompileSlots,
    CompileSlotsError,
    Position,
    Rendering,
    activate,
    cache_key_slots,
    deactivate,
    escape,
    factor_page,
    mark_positions,
    read_escaped_marks,
    read_slots,
    refuse_escaped_marks,
)
from ..shared_structure import LanguageText, compose_page

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_LANGUAGES = ("en", "es", "ca")


@pytest.fixture
def slots() -> Iterator[CompileSlots]:
    """A compile recording three languages, with nothing left active after."""
    recorded = activate(_LANGUAGES)
    yield recorded
    deactivate()


def test_the_same_strings_are_one_mark(slots: CompileSlots) -> None:
    """A string that recurs is recorded once, so it is stored once."""
    first = slots.mark(Rendering.DOCUTILS, ["Filing", "Presentación", "Presentació"])
    again = slots.mark(Rendering.DOCUTILS, ["Filing", "Presentación", "Presentació"])
    assert first == again == f"{MARK_OPEN}0{MARK_CLOSE}"
    assert len(slots.values) == 1


def test_the_owning_writer_separates_two_marks(slots: CompileSlots) -> None:
    """The same strings written by two writers are two marks: they reach the page differently."""
    text = slots.mark(Rendering.DOCUTILS, ["a&b", "a&b", "a&b"])
    raw = slots.mark(Rendering.VERBATIM, ["a&b", "a&b", "a&b"])
    assert text != raw
    assert len(slots.values) == 2


def test_a_mark_needs_one_string_per_language(slots: CompileSlots) -> None:
    """A compile that recorded two of three languages would store a language's text short."""
    with pytest.raises(CompileSlotsError, match="one string per language"):
        slots.mark(Rendering.DOCUTILS, ["Filing", "Presentación"])


def test_a_recorded_string_may_not_carry_a_delimiter(slots: CompileSlots) -> None:
    """A string holding a delimiter would read as a mark of its own."""
    with pytest.raises(CompileSlotsError, match="reserved for mark delimiters"):
        slots.mark(Rendering.VERBATIM, ["ok", f"no{MARK_OPEN}", "ok"])


def test_every_position_a_page_offers_is_recognised(slots: CompileSlots) -> None:
    """The four positions are told apart, including a title tag that has closed."""
    mark = slots.mark(Rendering.VERBATIM, ["a", "b", "c"])
    page = f'<head><title>{mark}</title></head><body><p class="{mark}">{mark}</p><p {mark}>t</p></body>'
    assert [position for _, position in mark_positions(page)] == [
        Position.TITLE,
        Position.ATTRIBUTE,
        Position.TEXT,
        Position.MARKUP,
    ]


def test_each_position_receives_the_string_its_writer_writes(slots: CompileSlots) -> None:
    """A docutils mark's strings are escaped as the writer that owns the position escapes."""
    mark = slots.mark(Rendering.DOCUTILS, ["a&b<c>@e", "x\ty\nz", "l'IVA"])
    page = f'<head><title>{mark}</title></head><body><p>{mark}</p><p title="{mark}">t</p></body>'
    factored = factor_page(page, slots)
    assert factored == [
        "<head><title>",
        ("a&amp;b&lt;c&gt;@e", "x y z", "l’IVA"),
        "</title></head><body><p>",
        ("a&amp;b&lt;c&gt;&#64;e", "x\ty\nz", "l’IVA"),
        '</p><p title="',
        ("a&amp;b&lt;c&gt;&#64;e", "x y z", "l’IVA"),
        '">t</p></body>',
    ]


def test_a_navigation_or_toctree_title_is_written_the_way_its_region_writes_it(slots: CompileSlots) -> None:
    """The region says who escapes a title, and the rendering says if it was educated.

    Read off the English desktop root built on 2026-10-06: Modelo 151's title
    carries ``"Beckham law"`` with straight quotation marks in the sidebar and
    in the body toctree, while the same title in the page's own heading carries
    ``“Beckham law”``. The two are not one string. The sidebar's is the explicit
    toctree entry title, an attribute of the toctree node that the smart-quotes
    transform passes by, and the heading's is a text node it educates -- and the
    same sidebar also carries titles a page's own educated heading supplied. So
    the uneducated ones are told apart by their rendering and not by the region.

    The regions do say who escapes: the sidebar is re-serialised by Furo through
    BeautifulSoup, which leaves ``"`` and ``@`` where the docutils writer
    escapes both.
    """
    strings = ['a "q" @ b', "l'IVA & z", "<y>"]
    heading = slots.mark(Rendering.DOCUTILS, strings)
    title = slots.mark(Rendering.PLAIN, strings)
    page = (
        f"<p>{heading}</p>"
        f'<div class="sidebar-tree"><ul><li><input aria-label="n {title}"><a>{title}</a></li></ul></div>'
        f'<div class="toctree-wrapper compound"><ul><li><a>{title}</a></li></ul></div>'
        f'<div class="sidebar-tree"><ul><li><a>{heading}</a></li></ul></div>'
    )
    educated_text = ("a “q” &#64; b", "l’IVA &amp; z", "&lt;y&gt;")
    educated_navigation = ("a “q” @ b", "l’IVA &amp; z", "&lt;y&gt;")
    navigation = ('a "q" @ b', "l'IVA &amp; z", "&lt;y&gt;")
    entry = ("a &quot;q&quot; &#64; b", "l'IVA &amp; z", "&lt;y&gt;")
    factored = factor_page(page, slots)
    assert [piece for piece in factored if isinstance(piece, tuple)] == [
        educated_text,
        navigation,
        navigation,
        entry,
        educated_navigation,
    ]


#: Strings a built root carries, with the typography that root's own language
#: gave them. Read off the desktop roots built on 2026-10-06: the English root
#: writes the legal catalogue's ``Cataloguer's note`` as ``Cataloguer’s note``
#: and Modelo 151's ``"Beckham law"`` as ``“Beckham law”``, and the Catalan root
#: writes ``l'Estat`` as ``l’Estat``. The transform that does that never sees a
#: mark, so each language's string is given the same treatment where the mark is
#: factored, in that language.
_BUILT_TYPOGRAPHY: tuple[tuple[str, str, str], ...] = (
    ("en", "Cataloguer's note", "Cataloguer’s note"),
    (
        "en",
        'special regime for posted workers (inbound expatriates, "Beckham law")',
        "special regime for posted workers (inbound expatriates, “Beckham law”)",
    ),
    ("ca", "publicat al Butlletí Oficial de l'Estat", "publicat al Butlletí Oficial de l’Estat"),
)


@pytest.mark.parametrize(("language", "authored", "built"), _BUILT_TYPOGRAPHY)
def test_a_marked_string_gets_the_typography_its_own_build_gives_it(language: str, authored: str, built: str) -> None:
    """A page composed without this reads ``'`` and ``&quot;`` where the build wrote ``’`` and ``“``."""
    recorded = activate([language])
    try:
        mark = recorded.mark(Rendering.DOCUTILS, [authored])
        assert factor_page(f"<p>{mark}</p>", recorded) == ["<p>", (built,), "</p>"]
    finally:
        deactivate()


def test_a_verbatim_string_keeps_the_form_its_creation_site_wrote(slots: CompileSlots) -> None:
    """A generator's own raw HTML never met the transform, so educating it would change it."""
    mark = slots.mark(Rendering.VERBATIM, ["Cataloguer's note"] * len(_LANGUAGES))
    assert factor_page(f"<p>{mark}</p>", slots) == ["<p>", ("Cataloguer's note",) * len(_LANGUAGES), "</p>"]


def test_a_verbatim_mark_is_placed_as_it_was_recorded(slots: CompileSlots) -> None:
    """A generator that wrote its own markup already escaped its strings for it."""
    mark = slots.mark(Rendering.VERBATIM, ["a&amp;b", "x", "y"])
    assert factor_page(f'<p title="{mark}">{mark}</p>', slots) == [
        '<p title="',
        ("a&amp;b", "x", "y"),
        '">',
        ("a&amp;b", "x", "y"),
        "</p>",
    ]


def test_the_plain_text_a_mark_reads_as_is_the_message_rendering_stripped(slots: CompileSlots) -> None:
    """A creation site that describes a page needs its words, not the markup around them."""
    message = slots.reserve(Rendering.MESSAGE)
    slots.supply(
        message,
        ['Read <a href="x.html">the guide</a>', "Lee la guía", "Llegeix la guia"],
        ["Read the guide", "Lee la guía", "Llegeix la guia"],
    )
    assert slots.plain_resolved(f"{message} now", 0) == "Read the guide now"
    assert slots.plain_resolved(f"{message} now", 1) == "Lee la guía now"


def test_the_plain_text_of_a_docutils_mark_is_typeset_in_its_own_language(slots: CompileSlots) -> None:
    """A docutils string reaches a page educated, and a description quotes the page."""
    mark = slots.mark(Rendering.DOCUTILS, ['the "local" copy'] * len(_LANGUAGES))
    assert slots.plain_resolved(mark, 0) == "the “local” copy"
    assert slots.plain_resolved(mark, 1) == "the «local» copy"


def test_a_docutils_mark_in_bare_markup_is_refused(slots: CompileSlots) -> None:
    """Nothing can say how a docutils writer would have written a tag's own bytes."""
    mark = slots.mark(Rendering.DOCUTILS, ["a", "b", "c"])
    with pytest.raises(CompileSlotsError, match="reached page markup"):
        factor_page(f"<p {mark}>t</p>", slots)


def test_a_mark_the_compile_never_recorded_is_refused(slots: CompileSlots) -> None:
    """A page naming an unrecorded mark would store a slot with no string."""
    slots.mark(Rendering.VERBATIM, ["a", "b", "c"])
    with pytest.raises(CompileSlotsError, match="recorded 1 mark"):
        factor_page(f"<p>{MARK_OPEN}9{MARK_CLOSE}</p>", slots)


def test_a_mark_escaped_into_javascript_is_read_back_as_the_mark(slots: CompileSlots) -> None:
    """A creation site serialising a URL escapes the mark, and the escape means the mark.

    The error page's module import is written through ``json.dumps``, which
    escapes every non-ASCII character: the page states the escape in both
    cases, as a serialiser may write either.
    """
    mark = slots.mark(Rendering.VERBATIM, ["en", "es", "ca"])
    page = f'<script>import m from "/docs/\\u{ord(MARK_OPEN):04x}0\\u{ord(MARK_CLOSE):04X}/m.js";</script>'
    assert read_escaped_marks(page) == f'<script>import m from "/docs/{mark}/m.js";</script>'
    assert factor_page(read_escaped_marks(page), slots) == [
        '<script>import m from "/docs/',
        ("en", "es", "ca"),
        '/m.js";</script>',
    ]


def test_an_escape_of_a_character_the_marks_do_not_use_is_left_alone(slots: CompileSlots) -> None:
    """A vendored script escapes private-use characters of its own, which are not ours."""
    page = "<script>const glyph = \\ue006;</script>"
    assert read_escaped_marks(page) == page


def test_a_file_that_is_not_a_page_cannot_carry_an_escaped_mark() -> None:
    """Stored whole, its escape is a language-dependent string nothing would resolve."""
    with pytest.raises(CompileSlotsError, match=r"_static/app\.js is not a page and carries an escaped mark"):
        refuse_escaped_marks('const root = "/docs/\\ue002k\\ue003/";', "_static/app.js")


def test_a_page_carrying_half_a_mark_is_refused_by_name(slots: CompileSlots) -> None:
    """A mark something cut through stands for strings no composition could read.

    The page is written by hand with the opening delimiter and no closing one,
    which is what a description cut at a character count left on 43 pages of
    every language.
    """
    mark = slots.mark(Rendering.VERBATIM, ["a", "b", "c"])
    page = f'<meta content="The filing workflow {mark[0]}" /><p>{mark}</p>'
    with pytest.raises(CompileSlotsError, match=r"how-to/index\.html carries an opening mark delimiter"):
        factor_page(page, slots, path="how-to/index.html")


def test_a_page_carrying_a_stray_closing_delimiter_is_refused(slots: CompileSlots) -> None:
    """The closing delimiter is checked as well, so neither half passes alone."""
    with pytest.raises(CompileSlotsError, match="closing mark delimiter"):
        factor_page(f"<p>cut{MARK_CLOSE}</p>", slots, path="index.html")


def test_escaping_reaches_every_language_rather_than_the_mark(slots: CompileSlots) -> None:
    """Escaping a mark changes nothing, so the strings are escaped instead."""
    mark = slots.mark(Rendering.DOCUTILS, ["a&b", "d'IVA", "<x>"])
    escaped = escape(f"prefix {mark}", quote=True)
    assert escaped.startswith("prefix ")
    rendering, values = slots.strings(int(escaped.removeprefix("prefix ")[1:-1], 36))
    assert rendering is Rendering.VERBATIM
    assert values == ("a&amp;b", "d&#x27;IVA", "&lt;x&gt;")


def test_escaping_outside_a_compile_is_ordinary_escaping() -> None:
    """One root's build has no marks and must escape exactly as it does today."""
    deactivate()
    assert escape("a&b<c>", quote=True) == "a&amp;b&lt;c&gt;"


def test_the_default_escaping_is_the_default_html_escaping(slots: CompileSlots) -> None:
    """Every call site replaced an ``html.escape`` call, whose default escapes quotes.

    An apostrophe in a registry label is common enough that a looser default
    here silently writes a different page from the one the per-language build
    writes, at every site that took the default.
    """
    mark = slots.mark(Rendering.DOCUTILS, ["an employee's", "de l'empleat", "<x>"])
    _rendering, values = slots.strings(int(escape(mark)[1:-1], 36))
    assert values == ("an employee&#x27;s", "de l&#x27;empleat", "&lt;x&gt;")
    deactivate()
    assert escape('an employee\'s "name"') == "an employee&#x27;s &quot;name&quot;"


def test_each_language_composes_back_to_its_own_page(slots: CompileSlots) -> None:
    """The stored form is only as good as the page it gives back."""
    mark = slots.mark(Rendering.DOCUTILS, ["Filing", "Presentación", "Presentació"])
    other = slots.mark(Rendering.VERBATIM, ["en", "es", "ca"])
    page = f'<html lang="{other}"><h1>{mark}</h1></html>'
    text = LanguageText(_LANGUAGES)
    structure = text.structure(factor_page(page, slots))
    assert [compose_page(structure, text.strings[language]) for language in _LANGUAGES] == [
        '<html lang="en"><h1>Filing</h1></html>',
        '<html lang="es"><h1>Presentación</h1></html>',
        '<html lang="ca"><h1>Presentació</h1></html>',
    ]


def test_a_language_dependent_assets_cache_key_becomes_a_slot(slots: CompileSlots) -> None:
    """Each language's file has its own key, and one compile wrote neither."""
    page = '<script src="_static/chrome.js?v=0000"></script><link href="_static/app.css?v=1111">'
    assert cache_key_slots(page, {"_static/chrome.js?v=0000": ("aa", "bb", "cc")}) == [
        '<script src="',
        ("_static/chrome.js?v=aa", "_static/chrome.js?v=bb", "_static/chrome.js?v=cc"),
        '"></script><link href="_static/app.css?v=1111">',
    ]


def test_the_recorded_marks_survive_the_process_that_wrote_them(slots: CompileSlots, tmp_path: Path) -> None:
    """The compile records marks in the Sphinx child; the driver factors the site after it."""
    slots.mark(Rendering.DOCUTILS, ["a", "b", "c"])
    slots.mark(Rendering.VERBATIM, ["x&amp;", "y", "z"])
    written = tmp_path / "marks.json"
    slots.write(written)
    assert json.loads(written.read_text(encoding="utf-8"))["schema"] == SLOTS_SCHEMA
    read = read_slots(written)
    assert read.languages == _LANGUAGES
    assert read.strings(0) == (Rendering.DOCUTILS, ("a", "b", "c"))
    assert read.strings(1) == (Rendering.VERBATIM, ("x&amp;", "y", "z"))


def test_an_unreadable_mark_record_is_refused(tmp_path: Path) -> None:
    """A driver that factored a site without the compile's strings would store English four times."""
    absent = tmp_path / "missing.json"
    with pytest.raises(CompileSlotsError, match="no readable compile marks"):
        read_slots(absent)
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"schema": SLOTS_SCHEMA + 1}), encoding="utf-8")
    with pytest.raises(CompileSlotsError, match="schema"):
        read_slots(wrong)


def test_a_string_a_mark_is_built_from_may_itself_hold_marks(slots: CompileSlots) -> None:
    """A chrome string takes an argument, and the argument can be a translated one."""
    argument = slots.mark(Rendering.DOCUTILS, ["filing", "presentación", "presentació"])
    composed = slots.mark(
        Rendering.DOCUTILS,
        [slots.resolved(f"Navigation of {argument}", index) for index in range(len(_LANGUAGES))],
    )
    assert slots.strings(int(composed[1:-1], 36))[1] == (
        "Navigation of filing",
        "Navigation of presentación",
        "Navigation of presentació",
    )


def test_resolving_leaves_a_string_with_no_marks_alone(slots: CompileSlots) -> None:
    """The ordinary case must not pay for the composed one."""
    assert slots.resolved("Ley 37/1992", 0) == "Ley 37/1992"


def test_an_element_only_some_languages_carry_owns_its_own_line_break(slots: CompileSlots) -> None:
    """A language without the element composes to no line, not to an empty one.

    The element's line break is a line feed, as every line break of a stored
    page is: the platform's own terminator is put back when the page is composed
    (:func:`~dev.docs.language_roots.compose_root`), and nothing before that
    knows which platform will compose it.
    """
    from cadrumo.core.external_constants import OutputLanguage

    from .._locale_chrome import docs_line

    break_ = "\n"
    titles = {OutputLanguage.EN: "<h3>Activity</h3>", OutputLanguage.ES: "<h3>Actividad</h3>"}
    lines = ["<header>", "<span>01</span>" + docs_line(titles.get, OutputLanguage.EN), "</header>"]
    composed = {}
    text = LanguageText(slots.languages)
    structure = text.structure(factor_page(break_.join(lines), slots))
    for language in slots.languages:
        composed[language] = compose_page(structure, text.strings[language])
    assert composed["en"] == f"<header>{break_}<span>01</span>{break_}<h3>Activity</h3>{break_}</header>"
    assert composed["es"] == f"<header>{break_}<span>01</span>{break_}<h3>Actividad</h3>{break_}</header>"
    assert composed["ca"] == f"<header>{break_}<span>01</span>{break_}</header>"


def _marks_taken_in_this_process(slots: CompileSlots) -> tuple[str, str]:
    """Read a recorded mark and try to record a new one, reporting what each did."""
    known = slots.mark(Rendering.VERBATIM, ["one", "uno"])
    try:
        slots.mark(Rendering.VERBATIM, ["two", "dos"])
    except CompileSlotsError as error:
        return known, str(error)
    return known, ""


def test_a_worker_process_reads_recorded_marks_and_is_refused_a_new_one() -> None:
    """A mark a worker adds never reaches the record, so it is refused where it is made."""
    slots = CompileSlots(("en", "es"))
    known = slots.mark(Rendering.VERBATIM, ["one", "uno"])

    assert _marks_taken_in_this_process(slots) == (known, "")
    assert slots.values == [("one", "uno"), ("two", "dos")]

    inherited = CompileSlots(("en", "es"))
    inherited.mark(Rendering.VERBATIM, ["one", "uno"])
    with ProcessPoolExecutor(max_workers=1) as pool:
        read, refusal = pool.submit(_marks_taken_in_this_process, inherited).result(timeout=120)

    assert read == known
    assert "worker process" in refusal
    assert inherited.values == [("one", "uno")]
