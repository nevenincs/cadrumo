"""Derive one page's description from its own blocks of text.

A published page carries a description twice: ``og:description`` for a site
that previews its link, and ``<meta name="description">`` for a search engine.
``sphinxext.opengraph`` derives both by walking the page's doctree for LEAF
text and cutting the joined result at a character count, and that is wrong here
for two reasons.

The first is the one compile. Wherever a string depends on the language the
pages carry a mark of four characters standing for a sentence of any length
(:mod:`dev.docs.compile_slots`), so a cut that counts marks counts nothing a
reader will see: it cut 262 of the 326 described pages at the wrong place, and
on 43 of them it cut THROUGH a mark and published half a delimiter.

The second holds for a single-language build as well. Joining leaf text drops
the whitespace around inline markup, because each leaf is stripped and a leaf
opening with punctuation is not given a space back: ``interface (CLI)`` reaches
the published description as ``interface(CLI)``.

So the description is derived here instead, from each BLOCK's own text, and the
two are separate steps for the one compile's sake:
:func:`description_source` reads the doctree once, marks and all, and
:func:`description_content` is given one language's resolved text and returns
what that language's tag carries. A single-language build runs both in one go;
the compile runs the first while the page is written and the second once every
mark has its strings, which is why the cut never lands inside one.
"""

from __future__ import annotations

import html
import re
from collections.abc import Collection, Iterator
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from docutils import nodes

#: What ends a description that was cut, and is counted in its length.
_ELLIPSIS: Final[str] = "…"

#: The class Sphinx wraps a toctree written in a page's body in. Its text is
#: the titles of other pages -- navigation that the theme also puts in the
#: sidebar of every page -- so it is not part of what this page is about.
_NAVIGATION: Final[str] = "toctree-wrapper"

#: The description tags this module owns, whichever of the two wrote them. They
#: are taken off before ours are written, so a page carries one authority for
#: its description rather than two that a cut disagrees about.
_DESCRIPTION_TAG: Final[re.Pattern[str]] = re.compile(
    r'[ \t]*<meta (?:property="og:description"|name="description") content="[^"]*"\s*/?>\n?'
)


def _skipped(node: nodes.Element) -> bool:
    """Return whether one element contributes nothing to its page's description.

    Comments and targets carry no reader-facing text; an admonition is an
    aside; raw markup and a literal block are code and recorded output rather
    than prose. The first three are what ``sphinxext.opengraph`` skips as well,
    so a description stays what it was apart from the two defects this module
    exists for.
    """
    from docutils import nodes

    invisible = (nodes.Invisible, nodes.Admonition, nodes.raw, nodes.literal_block, nodes.system_message)
    return isinstance(node, invisible) or _NAVIGATION in node.get("classes", ())


def _folded(node: nodes.Element) -> str:
    """Return one element's own text with every run of whitespace folded to a space.

    A block wrapped across source lines carries the break into its text, where
    the description it stands in is one line.
    """
    return " ".join(str(node.astext()).split())


def _blocks(doctree: nodes.document, titles: Collection[str]) -> Iterator[str]:
    """Yield each block of one page's own text, in reading order.

    A block is the outermost element that holds text: a paragraph, a table
    cell's paragraph, a definition's term, a caption, a section heading. Taking
    the whole block's text rather than each of its leaves is what keeps the
    whitespace around inline markup, because the block's own text already has
    it.

    The page's own title is left out where it is one of *titles*: the tag it
    would open stands beside ``og:title``, which carries it already.
    """
    from docutils import nodes

    first_title = True

    def walk(node: nodes.Element) -> Iterator[str]:
        nonlocal first_title
        if _skipped(node):
            return
        if isinstance(node, nodes.title):
            own, first_title = first_title, False
            heading = _folded(node)
            if own and heading in titles:
                return
            # A heading introduces what follows it, as the extension's own
            # colon said; the sections of a page read as one description.
            yield f"{heading}:"
            return
        if isinstance(node, nodes.TextElement):
            yield _folded(node)
            return
        for child in node.children:
            if isinstance(child, nodes.Element):
                yield from walk(child)

    yield from walk(doctree)


def description_source(doctree: nodes.document, *, titles: Collection[str]) -> str:
    """Return one page's own text, joined and uncut, as the doctree holds it.

    Uncut because under the one compile the text still holds marks, and what
    each of them reads is longer than the mark: the cut belongs to
    :func:`description_content`, which is given one language's resolved text.

    Args:
        doctree: The page's resolved doctree.
        titles: The page's own title, in the forms it may read as, which is
            left out of its description.

    Returns:
        The page's blocks of text joined by single spaces, whitespace folded.
    """
    return " ".join(block for block in _blocks(doctree, titles) if block)


def description_content(source: str, *, length: int) -> str:
    """Return what one language's description tag carries for *source*.

    The text is cut at a word boundary rather than mid-word, and escaped
    afterwards, so a cut can never land inside an HTML character reference: the
    reference does not exist yet when the cut is made.

    Args:
        source: The page's own text in one language, as
            :func:`description_source` joins it.
        length: The most characters the description may read as.

    Returns:
        The description as the ``content`` attribute of a meta tag holds it,
        empty where the page has no text of its own.
    """
    text = " ".join(source.split())
    if len(text) > length:
        cut = text[: length - len(_ELLIPSIS)].rstrip()
        boundary = cut.rfind(" ")
        text = f"{cut[:boundary] if boundary > 0 else cut}{_ELLIPSIS}"
    return html.escape(text, quote=True)


def with_description(metatags: str, content: str) -> str:
    """Return one page's meta tags carrying *content* as its description.

    Whatever wrote a description tag before, it is taken off and ours is
    written: a page with no text of its own carries no description tag rather
    than an empty one.

    Args:
        metatags: The page's meta tags, as the HTML template writes them.
        content: The description, as :func:`description_content` returns it.

    Returns:
        The meta tags with exactly this module's description in them.
    """
    tags = _DESCRIPTION_TAG.sub("", metatags)
    if not content:
        return tags
    if tags and not tags.endswith("\n"):
        tags += "\n"
    return (
        f'{tags}<meta property="og:description" content="{content}" />\n'
        f'<meta name="description" content="{content}" />\n'
    )
