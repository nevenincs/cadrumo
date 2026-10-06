"""Typeset a generator-owned page in the language it is authored in.

A build typesets its text in the language it builds: docutils educates
quotation marks, dashes and ellipses with that language's own characters, so
the same English sentence reaches ``'Mis expedientes'`` as "Mis expedientes"
in English and as “Mis expedientes” in Spanish.

A page that declares itself generator-owned is English-only by policy: it is
excluded from the localized surface, nobody translates it, and every language's
build reads the same English prose (:func:`dev.docs.i18n._is_generated_page`
says why). The only thing a language then changes about such a page is that
typesetting. Educating English prose with Spanish quotation marks is not a
translation; it is one page typeset four ways for no reader's benefit, and it
is one more thing the one compile would have to carry a string per language for
(:mod:`dev.docs.compile_once`).

So a generator-owned page is typeset in the language it is authored in, in the
one compile and in each language's own build alike. The language of a text
block is docutils' own mechanism -- the ``language-<tag>`` class, which it
reads from the block itself and from nowhere else -- so the class is put on
every text block of such a page before the education runs and taken back off
the blocks that took it once the education has run, which leaves the published
markup untouched.

Which pages those are is settled when the configuration is read, before the
build's own generators write theirs into the source tree: a page generated
during the build carries its own language's strings from its generator (the one
compile carries every language's, through
:func:`dev.docs.message_marks.rendered_markup`), so it is translated prose and
is typeset in each language, while a committed generated artefact is not.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, override

from docutils import nodes
from docutils.transforms.universal import SmartQuotes
from sphinx.transforms import SphinxTransform

from .i18n import _DOC_SUFFIXES, DEFAULT_SOURCE_LANGUAGE, _is_generated_page

if TYPE_CHECKING:
    from sphinx.application import Sphinx

#: The class docutils reads a text block's language from.
_LANGUAGE_CLASS: Final[str] = f"language-{DEFAULT_SOURCE_LANGUAGE}"

#: The configuration value naming the pages typeset in the source language.
PAGES_SETTING: Final[str] = "cadrumo_source_language_pages"


def source_language_pages(docs_root: Path) -> tuple[str, ...]:
    """Return the docnames of the committed pages that declare themselves generated.

    Read from the artefacts, which is the same signal the localized surface is
    derived from (:func:`dev.docs.i18n.user_scope_source_pages`), so a page
    joins and leaves this set the moment its banner does and there is no second
    registry to fall out of step.

    Args:
        docs_root: The documentation source root being built.

    Returns:
        The docnames, sorted.
    """
    pages: list[str] = []
    for source in sorted(docs_root.rglob("*")):
        if source.suffix not in _DOC_SUFFIXES or not source.is_file():
            continue
        if _is_generated_page(source):
            pages.append(source.relative_to(docs_root).with_suffix("").as_posix())
    return tuple(pages)


# ── The blocks one document's pin was put on ─────────────────────────────────
# The pin and the unpin are two transforms because the education runs between
# them, so what one did has to reach the other. It is an attribute of the
# document, which is the unit both run on: the unpin takes the class off the
# blocks that took it and leaves a block that declared the same language itself
# alone.
_PINNED: Final[str] = "cadrumo_source_language_blocks"


def _text_blocks(document: nodes.document) -> Iterator[nodes.TextElement]:
    """Yield the text blocks docutils educates, which is the selection it makes itself.

    Mirroring that selection is what keeps the pin and the education about the
    same nodes; the skipped types are docutils' own declaration of the blocks
    it leaves alone.
    """
    found = cast(Iterator[nodes.TextElement], document.findall(nodes.TextElement))
    for node in found:
        if isinstance(node, SmartQuotes.nodes_to_skip) or isinstance(node.parent, nodes.TextElement):
            continue
        yield node


class PinSourceLanguageTypesetting(SphinxTransform):
    """Declare a generator-owned page's text blocks to be in the language they are authored in."""

    #: Before the education this exists for, and beside the class a fragment
    #: document's own paragraphs take (:mod:`dev.docs.message_marks`); a block
    #: that declares its own language keeps it, because that is the language
    #: its own text is in.
    default_priority = 701

    @override
    def apply(self, **kwargs: object) -> None:
        """Class every text block of this page with the source language, if nobody translates it."""
        if self.env.docname not in set(getattr(self.config, PAGES_SETTING, ())):
            return
        pinned: list[nodes.TextElement] = []
        for block in _text_blocks(self.document):
            if block.get_language_code():
                continue
            block["classes"].append(_LANGUAGE_CLASS)
            pinned.append(block)
        setattr(self.document, _PINNED, pinned)


class UnpinSourceLanguageTypesetting(SphinxTransform):
    """Take the declared language back off, so the published markup is unchanged."""

    #: After the education, which Sphinx runs at 750.
    default_priority = 760

    @override
    def apply(self, **kwargs: object) -> None:
        """Remove the class :class:`PinSourceLanguageTypesetting` put on this page's blocks."""
        pinned = cast(list[nodes.TextElement], getattr(self.document, _PINNED, []))
        for block in pinned:
            block["classes"].remove(_LANGUAGE_CLASS)
        setattr(self.document, _PINNED, [])


def register(app: Sphinx) -> None:
    """Add both transforms and the setting naming the pages they apply to."""
    app.add_config_value(PAGES_SETTING, (), "env")
    app.add_transform(PinSourceLanguageTypesetting)
    app.add_transform(UnpinSourceLanguageTypesetting)
