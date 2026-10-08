"""Resolve generated-docs page chrome in the language the docs root is built for.

The generated reference surfaces render two kinds of text and must not confuse
them.  CONTENT is whatever the underlying authority holds -- an official
Spanish citation, a provision's wording, a curated per-language definition --
and this module never touches it.  CHROME is the page's own words: headings,
field labels, the link out to the BOE, the sentence explaining what a block is.
Chrome must be readable by whoever the root was built for, so it comes from the
four locale catalogues and from nowhere else.

Resolution is deliberately strict.  A missing key RAISES rather than falling
back to another language, because a silent fallback is precisely the defect
this surface was corrected for: it renders English chrome around Hungarian
content and nothing reports it.  A build that cannot say a word in the reader's
language should fail loudly while someone can still fix it.

The catalogues are reached through :func:`~cadrumo.core.i18n.lookup_translation`,
which takes an explicit locale.  ``tr()`` is deliberately not used: it resolves
against the ambient ``CADRUMO_OUTPUT_LANGUAGE``, which ``docs/conf.py`` pins to
English for the whole build process so that import-time CLI help strings stay
stable, and which therefore says nothing about the language of the page being
written.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import lookup_translation

from .compile_slots import CompileSlots, Rendering, active, in_language
from .section_anchors import heading_anchor, section_anchor_directive

__all__ = [
    "DocsChromeError",
    "chrome_anchor",
    "docs_chrome",
    "docs_fragment",
    "docs_line",
    "markup_page",
    "same_wording",
    "template_chrome",
    "toctree_title_chrome",
]


class DocsChromeError(RuntimeError):
    """Raised when page chrome has no authored value in the build language."""


def docs_chrome(key: str, language: OutputLanguage, /, **values: object) -> str:
    """Return one chrome string in ``language``, or refuse.

    Under the one multilingual compile (:mod:`dev.docs.compile_slots`) there is
    no one language to return: the compile writes a mark here and records what
    every language reads, each language's own authored value filled with the
    same placeholders. ``language`` is still resolved and still refused when it
    has no authored value, so a build cannot pass by rendering the languages it
    can and marking the one it cannot. Inside :func:`markup_page` the compile
    records what each language's string renders to on that page, which is what
    a string carrying inline markup or a role needs.

    Args:
        key: The dotted catalogue key holding the string.
        language: The language this docs root is being built for.
        values: Placeholder values interpolated into the authored string.

    Returns:
        The authored string for ``language``, with placeholders filled, or the
        mark standing for every language's string under a multilingual compile.

    Raises:
        DocsChromeError: If the catalogue carries no authored value for the
            key in that language, or the authored value's placeholders do not
            match the ones supplied.  Both are authoring faults that must
            surface at build time rather than reaching a reader.
    """
    return _chrome(Rendering.DOCUTILS, key, language, values)


def chrome_anchor(key: str, /, **values: object) -> str:
    """Return the directive naming the anchor of the chrome heading that follows.

    A heading resolved through :func:`docs_chrome` is written in the reader's
    language, so the anchor docutils would name its section is written there
    too (:mod:`dev.docs.section_anchors`). The anchor is derived here from the
    same key's English words, which is what the English roots have published
    all along, and the directive makes every language root publish it.

    Args:
        key: The dotted catalogue key holding the heading, as the heading's own
            :func:`docs_chrome` call names it.
        values: The same placeholder values that call supplies; a value that is
            itself a mark is read in the anchor's language.

    Returns:
        The directive to write immediately before the heading.

    Raises:
        DocsChromeError: As :func:`docs_chrome` raises it.
    """
    read = {
        name: in_language(value, OutputLanguage.EN.value) if isinstance(value, str) else value
        for name, value in values.items()
    }
    return section_anchor_directive(heading_anchor(_authored(key, OutputLanguage.EN, read)))


def template_chrome(key: str, language: OutputLanguage, /, **values: object) -> str:
    """Return one chrome string a Jinja template will write, or refuse.

    The site's own chrome does not reach the page through a docutils writer: it
    is handed to the theme's templates, which escape it as ``markupsafe`` does
    and never educate its typography. So the compile records it as the
    templates' own (:attr:`~dev.docs.compile_slots.Rendering.TEMPLATE`) rather
    than as a docutils writer's, which would publish a typographic apostrophe
    where every single-language build writes the authored one.

    Args:
        key: The dotted catalogue key holding the string.
        language: The language this docs root is being built for.
        values: Placeholder values interpolated into the authored string.

    Returns:
        The authored string for ``language``, with placeholders filled, or the
        mark standing for every language's string under a multilingual compile.

    Raises:
        DocsChromeError: As :func:`docs_chrome` raises it.
    """
    return _chrome(Rendering.TEMPLATE, key, language, values)


def toctree_title_chrome(key: str, language: OutputLanguage, /, **values: object) -> str:
    """Return one chrome string used as an explicit toctree entry title, or refuse.

    An explicit entry title is an attribute of the toctree node, so nothing
    parses it as markup and the smart-quotes transform never sees it: it
    reaches the navigation, a body toctree and the relation links as it was
    authored. The compile records it as that
    (:attr:`~dev.docs.compile_slots.Rendering.PLAIN`) rather than as a docutils
    writer's, which would publish a typographic apostrophe where every
    single-language build writes the authored one. The same string used as a
    page's own heading is :func:`docs_chrome` and is educated there, so the two
    uses are two marks.

    Args:
        key: The dotted catalogue key holding the string.
        language: The language this docs root is being built for.
        values: Placeholder values interpolated into the authored string.

    Returns:
        The authored string for ``language``, with placeholders filled, or the
        mark standing for every language's string under a multilingual compile.

    Raises:
        DocsChromeError: As :func:`docs_chrome` raises it.
    """
    return _chrome(Rendering.PLAIN, key, language, values)


# ── The page the chrome resolved inside it stands on ─────────────────────────
# A chrome string is authored as the markup of the page it lands on: it carries
# inline literals, links and roles, and a role resolves against that page. The
# page is known to the generator writing it and to nothing further down, so it
# is declared here for the stretch of work that renders one page.
_PAGE: str | None = None


@contextmanager
def markup_page(docname: str) -> Iterator[None]:
    """Declare that the chrome resolved inside stands as markup on *docname*.

    A single-language build parses each chrome string as part of the page's own
    source, so a string carrying ``aeat`` as a literal or a ``:doc:`` link
    reaches the reader rendered. The one compile writes a mark where the string
    goes, and a mark carries no markup for the parser to find -- so without the
    page, every such string would reach the reader as the RST it was authored
    as. Knowing the page, the compile renders each language's string on it
    instead (:func:`~dev.docs.message_marks.rendered_markup`).

    Only :func:`docs_chrome` is affected, because only its strings are a
    docutils writer's to render. A toctree entry title and a string a Jinja
    template writes are never parsed as markup wherever they stand.

    Outside the one multilingual compile this changes nothing: the generator
    writes the authored string into the page's source exactly as before.

    Args:
        docname: The page being written, as Sphinx names it.
    """
    global _PAGE
    outer = _PAGE
    _PAGE = docname
    try:
        yield
    finally:
        _PAGE = outer


def _chrome(rendering: Rendering, key: str, language: OutputLanguage, values: Mapping[str, object]) -> str:
    """Return one chrome string, or the mark recording every language's under the compile."""
    slots = active()
    if slots is None:
        return _authored(key, language, values)
    strings = _per_language(slots, key, values)
    if rendering is Rendering.DOCUTILS and _PAGE is not None:
        # Imported here because the fragment machinery subclasses Sphinx's own
        # transforms, and every generator that resolves a chrome string imports
        # this module -- including where no Sphinx build is running.
        from .message_marks import rendered_markup

        return rendered_markup(slots, _PAGE, strings)
    return slots.mark(rendering, strings)


def same_wording(value: str, language: OutputLanguage, /, *, as_source: Callable[[str], str] = str) -> str:
    """Return one wording no language changes, as each language's own build writes it.

    A value a generator reads rather than translates is data: a cataloguer's
    note on a legal provision, a CLI command's own help sentence, a setting's
    description. Every language's page reads the same words. What those words
    LOOK like is not the same: the smart-quotes transform runs in the language
    of the build, so an apostrophe closes as ``'`` where English reads the page
    and as ``"`` where Spanish does, and one compile has one Sphinx language to
    educate it in.

    So the value is recorded as the same string for every language, and each
    language's own reading of it is what the composed page carries. Inside
    :func:`markup_page` that reading is the string rendered as markup of that
    page, which is what a value carrying an inline literal or a role needs:
    recorded as plain text it would reach the reader as the markup it was
    written as.

    The value reaches the page through the generator's own markup, where it is
    escaped as that markup requires and the parser takes the escaping back off.
    What is recorded is therefore the value itself.

    Args:
        value: The wording, as its own authority holds it.
        language: The language a single-language build renders.
        as_source: Escapes the value as the generator's own markup requires,
            and defaults to writing it as it stands where nothing escapes it.

    Returns:
        The escaped value, or the mark standing for every language's reading.
    """
    slots = active()
    # A value carrying a paragraph break is a BLOCK of markup -- one CLI help
    # sentence carries a blockquote and a definition list -- where a recorded
    # rendering is one inline run. Such a value stands as the generator wrote
    # it, which is what every language's build has always read on that page.
    if slots is None or "\n\n" in value:
        return as_source(value)
    strings = [value] * len(slots.languages)
    if _PAGE is not None:
        from .message_marks import rendered_markup

        return rendered_markup(slots, _PAGE, strings)
    return slots.mark(Rendering.DOCUTILS, strings)


def _per_language(slots: CompileSlots, key: str, values: Mapping[str, object]) -> list[str]:
    """Return one language's authored string per language, each value's marks read in it."""
    return [
        _authored(
            key,
            OutputLanguage(carried),
            {name: slots.resolved(value, index) if isinstance(value, str) else value for name, value in values.items()},
        )
        for index, carried in enumerate(slots.languages)
    ]


def docs_fragment(render: Callable[[OutputLanguage], str], language: OutputLanguage, /) -> str:
    """Return one language's rendering of a fragment whose MARKUP depends on the language.

    A label a language does not carry is not a shorter label, it is a heading
    the page does not have, so the difference between two languages is markup
    and not a string. Only the writer of that markup can say what each language
    reads, so the fragment is rendered once per language and recorded whole.
    The rendering runs ordinarily inside, which is what keeps a generator's own
    escaping, joining and conditionals correct without a slot-aware copy of each.

    Outside the one multilingual compile this is the fragment in ``language``
    and nothing else, so a single-language build is unchanged.

    Args:
        render: Renders the fragment in one language.
        language: The language a single-language build renders.

    Returns:
        The fragment, or the mark standing for every language's fragment.
    """
    slots = active()
    if slots is None:
        return render(language)
    return slots.mark(
        Rendering.VERBATIM,
        [slots.resolved(render(OutputLanguage(carried)), index) for index, carried in enumerate(slots.languages)],
    )


def docs_line(render: Callable[[OutputLanguage], str | None], language: OutputLanguage, /) -> str:
    """Return a line break and an element for each language that has one, nothing for the rest.

    An element some languages carry and others do not cannot be a line of its
    own: the generated pages assemble raw HTML as a list of lines that
    :func:`~dev.docs.casilla_markup._raw_html` indents into an RST block, so an
    element that is sometimes empty would leave an empty line where the page has
    no line at all, and a mark spanning two lines would break the block's
    indentation.

    So the mark owns its own line break and is written at the END of the
    preceding line. A language with the element reads a newline and the element;
    a language without it reads nothing, and composes to no line. The mark stays
    on one line, the indentation rule is untouched, and what is stored is the
    element rather than the lines around it.

    Args:
        render: Returns the element in one language, or None where that
            language has no such element.
        language: The language a single-language build renders.

    Returns:
        The line break and element, empty where the language has neither.
    """

    # A line break is a line feed on either side of the compile: in RST source,
    # where the HTML writer gives the page its own terminator, and in a recorded
    # string, which stands in a page stored without the terminators of the
    # platform that wrote it (:func:`~dev.docs.language_roots.compose_root`).
    def line(carried: OutputLanguage) -> str:
        element = render(carried)
        return f"\n{element}" if element else ""

    return docs_fragment(line, language)


def _authored(key: str, language: OutputLanguage, values: Mapping[str, object]) -> str:
    """Return one language's authored string for *key*, placeholders filled."""
    authored = lookup_translation(key, locale=language.value)
    if authored is None:
        raise DocsChromeError(
            f"locale key {key!r} has no authored value in {language.value!r}; "
            f"author it with `python -m dev.locales set {language.value} {key} <value>`",
        )
    if not values:
        return authored
    try:
        return authored.format(**values)
    except (IndexError, KeyError) as exc:
        raise DocsChromeError(
            f"locale key {key!r} in {language.value!r} does not accept the supplied placeholders {sorted(values)}",
        ) from exc
