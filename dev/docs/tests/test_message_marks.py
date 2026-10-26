"""An authored page's translations reach one compile as marks and come back rendered.

The mechanism has two halves and they are tested as two: what is written into
the source tree before Sphinx reads it, and what is read back out of what
Sphinx wrote. Between them the real Sphinx renders the fragment documents, so
the expected values here are the ones gettext and the HTML of a written page
state, never values taken from the module under test: the generated catalogue
is read back with the standard library's own ``gettext``, and the renderings are
read out of fragment pages written by hand to say what a rendered paragraph
looks like.
"""

from __future__ import annotations

import gettext
from pathlib import Path

import pytest

from ..compile_slots import (
    BLOCK_CLOSE,
    BLOCK_MID,
    BLOCK_OPEN,
    MARK,
    MARK_CLOSE,
    MARK_OPEN,
    CompileSlots,
    CompileSlotsError,
    Rendering,
    factor_page,
)
from ..message_marks import (
    FRAGMENT_PREFIX,
    PSEUDO_LOCALE_DIR,
    MessageMarksError,
    MessagePlan,
    collect_notes,
    fragment_docname,
    harvest,
    merge_notes,
    notes_for,
    prepare,
    purge_notes,
    rendered_markup,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_LANGUAGES = ("en", "es")

_HEADER = 'msgid ""\nmsgstr "Content-Type: text/plain; charset=utf-8\\n"\n\n'


def _page(root: Path, docname: str, *, suffix: str = ".md") -> Path:
    """Write one authored source page and return its path."""
    source = root / f"{docname}{suffix}"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# a page\n", encoding="utf-8")
    return source


def _catalogue(root: Path, language: str, docname: str, pairs: dict[str, str]) -> None:
    """Write one authored gettext catalogue for one page."""
    path = root / "locales" / language / "LC_MESSAGES" / f"{docname}.po"
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = "".join(f'\nmsgid "{message}"\nmsgstr "{string}"\n' for message, string in pairs.items())
    path.write_text(_HEADER + entries, encoding="utf-8")


def _prepared(root: Path, docnames: list[str], *, suffix: str = ".md") -> tuple[CompileSlots, MessagePlan]:
    """Mark the given pages' messages and return the record and the plan."""
    slots = CompileSlots(_LANGUAGES)
    plan = prepare(
        root,
        slots=slots,
        docnames=docnames,
        doc2path=lambda docname: root / f"{docname}{suffix}",
        source_language="en",
        compact=False,
    )
    return slots, plan


def test_the_generated_catalogue_translates_each_message_to_its_own_mark(tmp_path: Path) -> None:
    """gettext must answer the mark, so Sphinx's own transform puts it on the page."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"Getting started": "Primeros pasos"})
    slots, _ = _prepared(tmp_path, ["guide"])

    catalogue = gettext.translation("guide", localedir=str(tmp_path / PSEUDO_LOCALE_DIR), languages=["en"])
    answered = catalogue.gettext("Getting started")

    # Sphinx reads the trailing suppression token as the translation's own
    # declaration that it carries none of the source's references, which is
    # true: every reference is inside the recorded renderings.
    assert answered.endswith("#noqa")
    assert MARK.fullmatch(answered.removesuffix("#noqa")) is not None
    assert len(slots.values) == 1
    assert slots.renderings == [Rendering.MESSAGE]


def test_a_message_no_language_translates_is_left_in_the_source_language(tmp_path: Path) -> None:
    """An untranslated message must stay as a build of that language leaves it."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"Translated": "Traducido", "Not yet": ""})
    slots, plan = _prepared(tmp_path, ["guide"])

    assert plan.messages == 1
    catalogue = gettext.translation("guide", localedir=str(tmp_path / PSEUDO_LOCALE_DIR), languages=["en"])
    assert catalogue.gettext("Not yet") == "Not yet"
    assert len(slots.values) == 1


def test_a_page_with_no_catalogue_gets_no_fragment_document(tmp_path: Path) -> None:
    """A generated page nobody translates must not be marked or rendered."""
    _page(tmp_path, "generated")
    slots, plan = _prepared(tmp_path, ["generated"])

    assert plan.pages == []
    assert plan.fragments == []
    assert slots.values == []
    assert not (tmp_path / f"{FRAGMENT_PREFIX}generated.md").exists()


@pytest.mark.parametrize(
    ("suffix", "first_line"),
    [(".md", "---"), (".rst", ":orphan:")],
)
def test_the_fragment_document_declares_itself_an_orphan_in_its_page_s_file_type(
    tmp_path: Path, suffix: str, first_line: str
) -> None:
    """Nothing links a fragment, and its roles are its page's, so both must hold."""
    _page(tmp_path, "guide", suffix=suffix)
    _catalogue(tmp_path, "es", "guide", {"Hello": "Hola"})
    _prepared(tmp_path, ["guide"], suffix=suffix)

    written = (tmp_path / f"{FRAGMENT_PREFIX}guide{suffix}").read_text(encoding="utf-8")

    assert written.splitlines()[0] == first_line
    # Every language's translation stands in its own paragraph, the source
    # language's first, and each is spaced away from its delimiters so that a
    # translation opening or closing in inline markup still parses as markup.
    assert f"{BLOCK_OPEN}0{BLOCK_MID} Hello {BLOCK_CLOSE}" in written
    assert f"{BLOCK_OPEN}1{BLOCK_MID} Hola {BLOCK_CLOSE}" in written


def test_the_fragment_document_sits_beside_its_page_so_a_relative_reference_resolves(
    tmp_path: Path,
) -> None:
    """A role resolves against the document it stands in, so the directory must match."""
    _page(tmp_path, "how-to/index")
    _catalogue(tmp_path, "es", "how-to/index", {"Hello": "Hola"})
    _, plan = _prepared(tmp_path, ["how-to/index"])

    assert plan.fragments == [f"how-to/{FRAGMENT_PREFIX}index"]
    assert fragment_docname("how-to/index") == f"how-to/{FRAGMENT_PREFIX}index"
    assert (tmp_path / "how-to" / f"{FRAGMENT_PREFIX}index.md").is_file()


def test_a_translation_holding_a_reserved_delimiter_is_refused(tmp_path: Path) -> None:
    """A delimiter inside content would make one artefact readable as another."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"Hello": f"Hola{BLOCK_MID}"})

    with pytest.raises(MessageMarksError, match="reserved for a block delimiter"):
        _prepared(tmp_path, ["guide"])


def _render(root: Path, plan: MessagePlan, rendered: dict[int, str]) -> None:
    """Write the pages a compile of the fragment documents would have written."""
    for docname in plan.fragments:
        blocks = [
            f'<p class="language-x">{BLOCK_OPEN}{index:x}{BLOCK_MID} {markup} {BLOCK_CLOSE}</p>'
            for index, markup in sorted(rendered.items())
        ]
        page = root / f"{docname}.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("<html><body>" + "".join(blocks) + "</body></html>", encoding="utf-8")


def test_each_language_s_rendering_is_recorded_and_the_fragment_page_is_dropped(
    tmp_path: Path,
) -> None:
    """A fragment is build scaffolding: read back, then gone from what was written."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"See the aeat command": "Mira el comando aeat"})
    slots, plan = _prepared(tmp_path, ["guide"])
    built = tmp_path / "built"
    _render(
        built,
        plan,
        {
            0: 'See the <code class="docutils literal">aeat</code> command',
            1: 'Mira el comando <code class="docutils literal">aeat</code>',
        },
    )

    supplied = harvest(plan, slots, lambda docname: built / f"{docname}.html")

    assert supplied == 1
    assert slots.values[0] == (
        'See the <code class="docutils literal">aeat</code> command',
        'Mira el comando <code class="docutils literal">aeat</code>',
    )
    # The plain form is the text that markup reads as, which is what the
    # theme's template is handed for the ``<title>`` element.
    assert slots.plain[0] == ("See the aeat command", "Mira el comando aeat")
    assert not (built / f"{FRAGMENT_PREFIX}guide.html").exists()


def test_a_message_reaching_a_text_node_a_title_and_the_navigation_reads_each_form(
    tmp_path: Path,
) -> None:
    """One page title stands in three writers' output, so one mark owns three forms."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"The aeat command": "El comando aeat"})
    slots, plan = _prepared(tmp_path, ["guide"])
    built = tmp_path / "built"
    _render(
        built,
        plan,
        {
            0: 'The <code class="docutils literal">aeat</code> command',
            1: 'El comando <code class="docutils literal">aeat</code>',
        },
    )
    harvest(plan, slots, lambda docname: built / f"{docname}.html")
    mark = f"{MARK_OPEN}0{MARK_CLOSE}"
    compiled = f'<title>{mark}</title><h1>{mark}</h1><div class="sidebar-tree"><a title="{mark}">{mark}</a></div>'

    factored = factor_page(compiled, slots)
    english = "".join(piece if isinstance(piece, str) else piece[0] for piece in factored)

    # The heading carries the rendering, the ``<title>`` element the plain text
    # the theme's template strips it to, and the navigation the rendering as
    # BeautifulSoup writes it back, because that is what Furo hands it through.
    assert "<title>The aeat command</title>" in english
    assert '<h1>The <code class="docutils literal">aeat</code> command</h1>' in english
    assert 'title="The aeat command"' in english
    assert '<a title="The aeat command">The <code class="docutils literal">aeat</code> command</a>' in english


def test_a_mark_whose_rendering_never_came_back_is_refused(tmp_path: Path) -> None:
    """A mark on a page with nothing to read is a defect, not an empty string."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"Hello": "Hola"})
    slots, plan = _prepared(tmp_path, ["guide"])
    built = tmp_path / "built"
    _render(built, plan, {0: "Hello"})

    with pytest.raises(MessageMarksError, match="did not render in every language"):
        harvest(plan, slots, lambda docname: built / f"{docname}.html")


def test_a_generated_page_s_markup_is_carried_by_a_fragment_beside_it(tmp_path: Path) -> None:
    """A generated page has no catalogue, so its chrome reaches the fragment directly."""
    _page(tmp_path, "cli/index", suffix=".rst")
    slots = CompileSlots(_LANGUAGES)
    mark = rendered_markup(slots, "cli/index", ["Open ``aeat``", "Abre ``aeat``"])
    plan = prepare(
        tmp_path,
        slots=slots,
        docnames=["cli/index"],
        doc2path=lambda docname: tmp_path / f"{docname}.rst",
        source_language="en",
        compact=False,
    )

    assert MARK.fullmatch(mark) is not None
    assert slots.renderings == [Rendering.MESSAGE]
    assert plan.pages == ["cli/index"]
    written = (tmp_path / "cli" / f"{FRAGMENT_PREFIX}index.rst").read_text(encoding="utf-8")
    assert f"{BLOCK_OPEN}0{BLOCK_MID} Open ``aeat`` {BLOCK_CLOSE}" in written
    assert f"{BLOCK_OPEN}1{BLOCK_MID} Abre ``aeat`` {BLOCK_CLOSE}" in written
    # Nothing translates a generated page, so no catalogue is generated for it.
    assert not (tmp_path / PSEUDO_LOCALE_DIR).exists()


def test_one_string_a_generated_page_carries_twice_is_rendered_once(tmp_path: Path) -> None:
    """A classification repeated on every command of a page must not be a mark each time."""
    _page(tmp_path, "cli/app", suffix=".rst")
    slots = CompileSlots(_LANGUAGES)
    first = rendered_markup(slots, "cli/app", ["Option, required.", "Opción, obligatoria."])
    again = rendered_markup(slots, "cli/app", ["Option, required.", "Opción, obligatoria."])
    plan = prepare(
        tmp_path,
        slots=slots,
        docnames=["cli/app"],
        doc2path=lambda docname: tmp_path / f"{docname}.rst",
        source_language="en",
        compact=False,
    )

    assert first == again
    assert plan.messages == 1
    assert len(slots.values) == 1


def test_markup_asked_for_on_a_page_the_build_does_not_read_is_refused(tmp_path: Path) -> None:
    """Nothing would render such a mark, so the compile must say so rather than write it."""
    _page(tmp_path, "guide")
    slots = CompileSlots(_LANGUAGES)
    rendered_markup(slots, "cli/index", ["Open ``aeat``", "Abre ``aeat``"])

    with pytest.raises(MessageMarksError, match="does not read"):
        _prepared(tmp_path, ["guide"])


def test_a_generated_page_s_markup_comes_back_rendered(tmp_path: Path) -> None:
    """The point of the fragment is the rendering: raw RST must not reach a reader."""
    _page(tmp_path, "cli/index", suffix=".rst")
    slots = CompileSlots(_LANGUAGES)
    rendered_markup(slots, "cli/index", ["Open ``aeat``", "Abre ``aeat``"])
    plan = prepare(
        tmp_path,
        slots=slots,
        docnames=["cli/index"],
        doc2path=lambda docname: tmp_path / f"{docname}.rst",
        source_language="en",
        compact=False,
    )
    built = tmp_path / "built"
    _render(
        built,
        plan,
        {
            0: 'Open <code class="docutils literal">aeat</code>',
            1: 'Abre <code class="docutils literal">aeat</code>',
        },
    )

    harvest(plan, slots, lambda docname: built / f"{docname}.html")

    assert slots.values[0] == (
        'Open <code class="docutils literal">aeat</code>',
        'Abre <code class="docutils literal">aeat</code>',
    )
    assert slots.plain[0] == ("Open aeat", "Abre aeat")


def test_a_chrome_string_is_markup_of_the_page_it_is_resolved_for(tmp_path: Path) -> None:
    """The generator knows the page; the resolver below it cannot, so it is declared."""
    from cadrumo.core.external_constants import OutputLanguage

    from .._locale_chrome import docs_chrome, markup_page
    from ..compile_slots import activate, deactivate

    _page(tmp_path, "cli/index", suffix=".rst")
    slots = activate(_LANGUAGES)
    try:
        with markup_page("cli/index"):
            inside = docs_chrome("docs.cli.index.intro", OutputLanguage.EN, count=7)
        outside = docs_chrome("docs.cli.index.intro", OutputLanguage.EN, count=7)
        plan = prepare(
            tmp_path,
            slots=slots,
            docnames=["cli/index"],
            doc2path=lambda docname: tmp_path / f"{docname}.rst",
            source_language="en",
            compact=False,
        )
    finally:
        deactivate()

    # The same string resolved outside the page is a string a docutils writer
    # escapes, which is the one thing a string carrying markup must not be.
    assert inside != outside
    assert slots.renderings == [Rendering.MESSAGE, Rendering.DOCUTILS]
    assert plan.pages == ["cli/index"]
    # Each language's own authored string reaches the fragment, with the
    # generator's placeholder value filled in and its markup intact.
    written = (tmp_path / "cli" / f"{FRAGMENT_PREFIX}index.rst").read_text(encoding="utf-8")
    assert "``aeat``" in written
    assert "7 leaf commands" in written


def test_what_a_worker_noted_while_reading_survives_the_merge(tmp_path: Path) -> None:
    """Sphinx reads in worker processes and keeps only the environment they pickle back.

    So the notes are the environment's, and the merge the parallel read runs is
    what carries them home. The handler is exercised here the way that read
    runs it: one environment per process, each with its own documents' notes,
    merged into the one the compile reads back from.
    """
    import pickle
    from copy import deepcopy
    from types import SimpleNamespace

    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"Hola": "Hello"})
    _, plan = _prepared(tmp_path, ["guide"])
    mark = plan.blocks[0].mark

    main = SimpleNamespace()
    worker = SimpleNamespace()
    notes_for(main, "index").titles.add(mark)
    worker_notes = notes_for(worker, "how-to/guide")
    worker_notes.dropped[mark] = {1}
    # The worker's environment reaches the main process as bytes and nothing
    # else, so the notes have to be serialisable, and the merge is given a
    # separate object rather than the one the notes were made on.
    assert pickle.dumps(worker)
    merge_notes(None, main, ["how-to/guide"], deepcopy(worker))
    collect_notes(main, plan)

    assert plan.titles == {mark}
    assert plan.dropped == {mark: {1}}

    # A document read again starts from no notes, so a note about a heading it
    # no longer carries cannot outlive it.
    purge_notes(None, main, "how-to/guide")
    purged = MessagePlan(languages=_LANGUAGES)
    collect_notes(main, purged)
    assert purged.dropped == {}
    assert purged.titles == {mark}


def test_a_message_reaching_bare_markup_is_refused(tmp_path: Path) -> None:
    """A message is markup, so markup is the one place it cannot be written into."""
    _page(tmp_path, "guide")
    _catalogue(tmp_path, "es", "guide", {"Hello": "Hola"})
    slots, plan = _prepared(tmp_path, ["guide"])
    built = tmp_path / "built"
    _render(built, plan, {0: "Hello", 1: "Hola"})
    harvest(plan, slots, lambda docname: built / f"{docname}.html")

    with pytest.raises(CompileSlotsError, match="reached page markup"):
        factor_page(f"<p data-x={MARK_OPEN}0{MARK_CLOSE}>text</p>", slots)


def _located_catalogue(root: Path, language: str, docname: str, entries: list[tuple[int, str, str]]) -> None:
    """Write one catalogue whose entries carry the source reference gettext extracts."""
    path = root / "locales" / language / "LC_MESSAGES" / f"{docname}.po"
    path.parent.mkdir(parents=True, exist_ok=True)
    written = "".join(
        f'\n#: ../../{docname}.md:{line}\nmsgid "{message}"\nmsgstr "{string}"\n' for line, message, string in entries
    )
    path.write_text(_HEADER + written, encoding="utf-8")


def test_the_source_language_reads_the_occurrence_the_message_was_extracted_from(tmp_path: Path) -> None:
    """A message is recovered from its own lines, not from another message's.

    The same link is a list item of its own and is also written inside a
    paragraph that wraps across lines. Both fold to the same words, so looking
    the shorter message up from the top of the file recovers the paragraph's
    line break and publishes a break the list item's own build has nowhere.
    The catalogue says which lines each message came from, and that is the
    occurrence read.
    """
    source = tmp_path / "guide.md"
    source.write_text(
        "# a page\n"
        "\n"
        "For the lifecycle, see [The filing\n"
        "workflow](filing-spine.md).\n"
        "\n"
        "- [The filing workflow](filing-spine.md)\n",
        encoding="utf-8",
    )
    _located_catalogue(
        tmp_path,
        "es",
        "guide",
        [
            (3, "For the lifecycle, see [The filing workflow](filing-spine.md).", "Para el ciclo, ver [x](y.md)."),
            (6, "[The filing workflow](filing-spine.md)", "[El flujo](filing-spine.md)"),
        ],
    )
    _prepared(tmp_path, ["guide"])

    written = (tmp_path / f"{FRAGMENT_PREFIX}guide.md").read_text(encoding="utf-8")

    # The list item reads as one line, as its own line in the source does.
    assert f"{BLOCK_OPEN}2{BLOCK_MID} [The filing workflow](filing-spine.md) {BLOCK_CLOSE}" in written
    # The paragraph keeps the line break its own source carries.
    assert "For the lifecycle, see [The filing\nworkflow](filing-spine.md)." in written


def test_a_message_the_catalogue_locates_in_another_file_is_looked_up_whole(tmp_path: Path) -> None:
    """A reference into another file says nothing about this source, so the file is searched."""
    source = tmp_path / "guide.md"
    source.write_text("# a page\n\nA sentence that\nwraps.\n", encoding="utf-8")
    path = tmp_path / "locales" / "es" / "LC_MESSAGES" / "guide.po"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'{_HEADER}\n#: ../../included/elsewhere.md:400\nmsgid "A sentence that wraps."\nmsgstr "Una frase."\n',
        encoding="utf-8",
    )
    _prepared(tmp_path, ["guide"])

    written = (tmp_path / f"{FRAGMENT_PREFIX}guide.md").read_text(encoding="utf-8")

    assert "A sentence that\nwraps." in written


def test_a_message_the_catalogue_does_not_place_stands_only_where_the_file_agrees(tmp_path: Path) -> None:
    """Two occurrences folded from different lines leave the message folded.

    A table cell is referenced by its file alone, so nothing says which
    occurrence this message is. One recorded string cannot be two, and the
    folded message is what every language's build of that cell reads.
    """
    source = tmp_path / "guide.md"
    source.write_text(
        "# a page\n\nOn a narrow terminal, use `[`\nand `]` to change page.\n\n| `[` and `]` | Page |\n",
        encoding="utf-8",
    )
    path = tmp_path / "locales" / "es" / "LC_MESSAGES" / "guide.po"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'{_HEADER}\n#: ../../guide.md\nmsgid "`[` and `]`"\nmsgstr "`[` y `]`"\n',
        encoding="utf-8",
    )
    _prepared(tmp_path, ["guide"])

    written = (tmp_path / f"{FRAGMENT_PREFIX}guide.md").read_text(encoding="utf-8")

    assert f"{BLOCK_OPEN}0{BLOCK_MID} `[` and `]` {BLOCK_CLOSE}" in written


def test_a_message_the_catalogue_does_not_place_is_recovered_where_the_file_has_one_answer(tmp_path: Path) -> None:
    """A wrapped paragraph that stands once keeps its own line break."""
    source = tmp_path / "guide.md"
    source.write_text("# a page\n\nA sentence that\nwraps once.\n", encoding="utf-8")
    path = tmp_path / "locales" / "es" / "LC_MESSAGES" / "guide.po"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'{_HEADER}\n#: ../../guide.md\nmsgid "A sentence that wraps once."\nmsgstr "Una frase."\n',
        encoding="utf-8",
    )
    _prepared(tmp_path, ["guide"])

    assert "A sentence that\nwraps once." in (tmp_path / f"{FRAGMENT_PREFIX}guide.md").read_text(encoding="utf-8")
