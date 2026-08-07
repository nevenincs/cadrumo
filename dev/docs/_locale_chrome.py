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

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n import lookup_translation

__all__ = ["DocsChromeError", "docs_chrome"]


class DocsChromeError(RuntimeError):
    """Raised when page chrome has no authored value in the build language."""


def docs_chrome(key: str, language: OutputLanguage, /, **values: object) -> str:
    """Return one chrome string in ``language``, or refuse.

    Args:
        key: The dotted catalogue key holding the string.
        language: The language this docs root is being built for.
        values: Placeholder values interpolated into the authored string.

    Returns:
        The authored string for ``language``, with placeholders filled.

    Raises:
        DocsChromeError: If the catalogue carries no authored value for the
            key in that language, or the authored value's placeholders do not
            match the ones supplied.  Both are authoring faults that must
            surface at build time rather than reaching a reader.
    """
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
