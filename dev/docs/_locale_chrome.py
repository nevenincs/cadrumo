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

from collections.abc import Callable, Mapping

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import lookup_translation

from .compile_slots import Rendering, active

__all__ = ["DocsChromeError", "docs_chrome", "docs_fragment", "docs_line"]


class DocsChromeError(RuntimeError):
    """Raised when page chrome has no authored value in the build language."""


def docs_chrome(key: str, language: OutputLanguage, /, **values: object) -> str:
    """Return one chrome string in ``language``, or refuse.

    Under the one multilingual compile (:mod:`dev.docs.compile_slots`) there is
    no one language to return: the compile writes a mark here and records what
    every language reads, each language's own authored value filled with the
    same placeholders. ``language`` is still resolved and still refused when it
    has no authored value, so a build cannot pass by rendering the languages it
    can and marking the one it cannot.

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
    slots = active()
    if slots is not None:
        return slots.mark(
            Rendering.DOCUTILS,
            [
                _authored(
                    key,
                    OutputLanguage(carried),
                    {
                        name: slots.resolved(value, index) if isinstance(value, str) else value
                        for name, value in values.items()
                    },
                )
                for index, carried in enumerate(slots.languages)
            ],
        )
    return _authored(key, language, values)


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
