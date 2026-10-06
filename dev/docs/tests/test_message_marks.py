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
    MARK,
    MARK_CLOSE,
    MARK_OPEN,
    CompileSlots,
    CompileSlotsError,
    Rendering,
    factor_page,
)
from ..message_marks import (
    BLOCK_CLOSE,
    BLOCK_MID,
    BLOCK_OPEN,
    FRAGMENT_PREFIX,
    PSEUDO_LOCALE_DIR,
    MessageMarksError,
    MessagePlan,
    fragment_docname,
    harvest,
    prepare,
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
