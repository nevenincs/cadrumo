"""Render the header language switcher for one page, in one language.

The switcher is the piece of site chrome that varies the most between language
roots. Three facts change at once: the current language is a span where every
other language is a link, the path from a page to the shared base holding every
language root is one level deeper when the root is not the apex, and the closed
state shows the current language's own code. A template cannot carry one mark
through all three (:mod:`dev.docs.compile_slots`), because the page's own path
sits between them and belongs to no language.

So the element is built here instead, from the facts rather than from a Jinja
template, and the one compile records each language's whole element. A
single-language build renders exactly the same bytes, which is what keeps the
two forms of the site comparable.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from cadrumo.core.external_constants import OutputLanguage

from ._locale_chrome import docs_fragment
from .compile_slots import active

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = ["register", "switcher_markup", "switcher_of_page"]

#: The disclosure caret, which no fact of the page or the language reaches.
_CARET: Final[str] = (
    '<svg class="cadrumo-header-lang-caret" viewBox="0 0 16 16" aria-hidden="true">'
    '<path fill="currentColor" d="M3.2 5.5a.75.75 0 0 1 1.06 0L8 9.24l3.74-3.74a.75.75 0 1 1 '
    '1.06 1.06l-4.27 4.27a.75.75 0 0 1-1.06 0L3.2 6.56a.75.75 0 0 1 0-1.06Z"/></svg>'
)


def switcher_markup(
    languages: Sequence[Mapping[str, str]],
    *,
    build_language: str,
    default_language: str,
    root_uri: str,
    pagename: str,
    aria_label: str,
    newline: str,
) -> str:
    """Return the switcher element one page of one language root carries.

    Args:
        languages: Every language root the site publishes, in display order,
            each as its ``code`` and the ``label`` it reads in itself.
        build_language: The language of the root this page belongs to.
        default_language: The language served at the shared base, whose root
            carries no directory of its own.
        root_uri: The path from this page back to its own language root, empty
            for a page at the root itself.
        pagename: This page's docname, which is its path inside every root.
        aria_label: The summary's accessible name, in the page's language.
        newline: The line terminator the page being written uses.

    Returns:
        The element, from its ``<details>`` to its ``</details>`` and no
        surrounding whitespace.
    """
    base = root_uri if build_language == default_language else f"{root_uri}../"
    items: list[str] = []
    for entry in languages:
        code, label = entry["code"], entry["label"]
        if code == build_language:
            items.append(
                f'<li><span class="cadrumo-header-lang-item is-current" aria-current="true" '
                f'lang="{code}">{label}</span></li>'
            )
            continue
        directory = "" if code == default_language else f"{code}/"
        items.append(
            f'<li><a class="cadrumo-header-lang-item" href="{base}{directory}{pagename}.html" '
            f'lang="{code}" hreflang="{code}">{label}</a></li>'
        )
    return newline.join(
        [
            '<details class="cadrumo-header-lang" data-cadrumo-lang>',
            f'  <summary class="cadrumo-header-lang-summary" aria-label="{aria_label}">',
            f'    <span class="cadrumo-header-lang-code" lang="{build_language}">{build_language.upper()}</span>',
            f"    {_CARET}",
            "  </summary>",
            f'  <ul class="cadrumo-header-lang-menu">{"".join(items)}</ul>',
            "</details>",
        ]
    )


def switcher_of_page(
    languages: Sequence[Mapping[str, str]],
    *,
    language: OutputLanguage,
    default_language: str,
    root_uri: str,
    pagename: str,
    aria_label: str,
) -> str:
    """Return the switcher for one page, or the mark standing for every language's.

    Args:
        languages: Every language root the site publishes, as
            :func:`switcher_markup` takes them.
        language: The language a single-language build renders.
        default_language: The language served at the shared base.
        root_uri: The path from this page back to its own language root.
        pagename: This page's docname.
        aria_label: The summary's accessible name. Under the one compile this
            is itself a mark, which the recording resolves per language.

    Returns:
        The element, or the mark standing for every language's element.
    """
    # The two line terminators are not the same terminator. A single-language
    # build hands this to a template and the writer gives the page its own; a
    # recorded string is put straight into a finished page, so it has to carry
    # the one that page already uses.
    terminator = "\n" if active() is None else os.linesep

    def render(carried: OutputLanguage) -> str:
        return switcher_markup(
            languages,
            build_language=carried.value,
            default_language=default_language,
            root_uri=root_uri,
            pagename=pagename,
            aria_label=aria_label,
            newline=terminator,
        )

    return docs_fragment(render, language)


def register(app: Sphinx) -> None:
    """Build the switcher into every page's template context.

    The element needs the page's own path, which only exists once the page is
    about to be written, so it is built then rather than once per build.

    Args:
        app: The Sphinx application, whose ``html_context`` carries the
            languages, the apex language and this root's resolved chrome.
    """

    def render(
        app: Sphinx,
        pagename: str,
        templatename: str,
        context: dict[str, object],
        doctree: object,
    ) -> None:
        declared = app.config.html_context
        pathto = context["pathto"]
        if not callable(pathto):
            raise TypeError("the page context carries no pathto resolver")
        root = str(pathto(app.config.root_doc))
        context["cadrumo_language_switcher"] = switcher_of_page(
            declared["cadrumo_docs_languages"],
            language=OutputLanguage(app.config.language),
            default_language=declared["cadrumo_docs_default_language"],
            root_uri=f"{root.rsplit('/', 1)[0]}/" if "/" in root else "",
            pagename=pagename,
            aria_label=declared["cadrumo_chrome"]["aria_language"],
        )

    app.connect("html-page-context", render)
