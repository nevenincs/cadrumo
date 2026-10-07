"""Render the header language switcher for one page, in one language.

The switcher is the piece of site chrome that varies the most between language
roots. Three facts change at once: the current language is a span where every
other language is a link, the path from a page to the shared base holding every
language root is one level deeper for every directory this root sits in, and the
closed state shows the current language's own code. A template cannot carry one
mark through all three (:mod:`dev.docs.compile_slots`), because the page's own
path sits between them and belongs to no language.

Where each root sits is the LAYOUT's own fact and not the language's, so it is
read from one authority, :func:`dev.docs.build_paths.docs_site_prefixes`: the
desktop package serves one language at its apex and the rest under their own
code, while the published site serves every language under its own code and
nothing at the apex. A switcher that assumed the first layout wrote, from the
published English root, a Spanish link relative to the English root rather than
to the base above it.

So the element is built here instead, from the facts rather than from a Jinja
template, and the one compile records each language's whole element. A
single-language build renders exactly the same bytes, which is what keeps the
two forms of the site comparable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from cadrumo.core.external_constants import OutputLanguage

from ._locale_chrome import docs_fragment

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
    prefixes: Mapping[str, str],
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
        prefixes: Each language's own path inside the served site, as
            :func:`dev.docs.build_paths.docs_site_prefixes` returns them: empty
            for a root at the site's apex, and one segment ending in ``/`` for
            a root in a directory of its own.
        root_uri: The path from this page back to its own language root, empty
            for a page at the root itself.
        pagename: This page's docname, which is its path inside every root.
        aria_label: The summary's accessible name, in the page's language.
        newline: The line terminator the page being written uses.

    Returns:
        The element, from its ``<details>`` to its ``</details>`` and no
        surrounding whitespace.

    Raises:
        KeyError: If a published language has no prefix, since the layout then
            does not say where that root is served and no link to it could be
            written.
    """
    # The base every language root is a peer under: this page's own root, then
    # back out of each directory the root itself sits in. A root at the apex
    # sits in none, which is the one case where the base is the root.
    base = root_uri + "../" * prefixes[build_language].count("/")
    items: list[str] = []
    for entry in languages:
        code, label = entry["code"], entry["label"]
        if code == build_language:
            items.append(
                f'<li><span class="cadrumo-header-lang-item is-current" aria-current="true" '
                f'lang="{code}">{label}</span></li>'
            )
            continue
        directory = prefixes[code]
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
    prefixes: Mapping[str, str],
    root_uri: str,
    pagename: str,
    aria_label: str,
) -> str:
    """Return the switcher for one page, or the mark standing for every language's.

    Args:
        languages: Every language root the site publishes, as
            :func:`switcher_markup` takes them.
        language: The language a single-language build renders.
        prefixes: Each language's own path inside the served site, as
            :func:`switcher_markup` takes them. One compile and a
            single-language build read the same layout, so both write the same
            element for the same page.
        root_uri: The path from this page back to its own language root.
        pagename: This page's docname.
        aria_label: The summary's accessible name. Under the one compile this
            is itself a mark, which the recording resolves per language.

    Returns:
        The element, or the mark standing for every language's element.
    """

    # A line terminator is a line feed on either side of the compile: handed to
    # a template, where the writer gives the page its own, and in a recorded
    # string, which stands in a page stored without the terminators of the
    # platform that wrote it (:func:`~dev.docs.language_roots.compose_root`).
    def render(carried: OutputLanguage) -> str:
        return switcher_markup(
            languages,
            build_language=carried.value,
            prefixes=prefixes,
            root_uri=root_uri,
            pagename=pagename,
            aria_label=aria_label,
            newline="\n",
        )

    return docs_fragment(render, language)


def register(app: Sphinx) -> None:
    """Build the switcher into every page's template context.

    The element needs the page's own path, which only exists once the page is
    about to be written, so it is built then rather than once per build.

    Args:
        app: The Sphinx application, whose ``html_context`` carries the
            languages, where each of their roots is served in this layout, and
            this root's resolved chrome.
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
            prefixes=declared["cadrumo_docs_site_prefixes"],
            root_uri=f"{root.rsplit('/', 1)[0]}/" if "/" in root else "",
            pagename=pagename,
            aria_label=declared["cadrumo_chrome"]["aria_language"],
        )

    app.connect("html-page-context", render)
