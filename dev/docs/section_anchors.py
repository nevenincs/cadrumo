"""Publish a generated page's heading under an anchor that no language owns.

docutils names a section by slugging the words of its own heading, so a
generated page whose heading is written in the reader's language carries a
different anchor in every language root: ``#global-flags`` where English reads
it, ``#indicadores-globales`` where Spanish does. Those anchors are what the
page's permalinks and its local contents point at, and what the search
projection's deep links target, so an anchor that moves with the language is a
link whose target depends on which root the reader happens to stand in. One
compile carrying four languages publishes ONE structure, which cannot hold four
spellings of the same id at all.

So a generated heading names its own anchor: the ``cadrumo-section-anchor``
directive stands immediately before the heading and the section that follows is
published under the name it carries. Each generator derives that name from the
page's English wording, which is the anchor the English roots already shipped,
and every other language root now shares it.

An explicit hyperlink target cannot do this on its own. docutils does propagate
``.. _global-flags:`` onto the section that follows it, but it APPENDS the id to
the ones the section already has, and the implicit slug of the heading stays
first -- and the first is the id the section element carries and the permalink
points at. The target's name would also become a label of the whole project,
and two generated pages carrying the same heading (``Direct commands``, on each
command family's landing page) would then be a duplicate label a strict build
refuses. This directive names an id and nothing else: no label is registered,
and nothing resolves against it other than the anchor itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.transforms import Transform

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = [
    "SECTION_ANCHOR_DIRECTIVE",
    "AdoptSectionAnchors",
    "SectionAnchorDirective",
    "SectionAnchorError",
    "heading_anchor",
    "register",
    "section_anchor",
    "section_anchor_directive",
]

#: The directive's name in a generated page's source.
SECTION_ANCHOR_DIRECTIVE = "cadrumo-section-anchor"


class SectionAnchorError(RuntimeError):
    """Raised when a declared anchor cannot name the section it stands before."""


class section_anchor(nodes.Special, nodes.Invisible, nodes.Element):  # noqa: N801 - a docutils node is lower case
    """The anchor the section standing after this node is published under.

    Invisible, as a hyperlink target is: the node reaches no reader and no
    writer, because :class:`AdoptSectionAnchors` takes it back out of the tree
    once it has named its section.
    """


class SectionAnchorDirective(Directive):
    """The ``cadrumo-section-anchor`` directive: one argument, the anchor name.

    Written immediately before the heading it names, with nothing but hyperlink
    targets and comments between the two.
    """

    required_arguments = 1
    optional_arguments = 0
    has_content = False

    @override
    def run(self) -> list[nodes.Node]:
        """Return the node carrying the declared anchor."""
        return [section_anchor("", anchor=self.arguments[0])]


class AdoptSectionAnchors(Transform):
    """Publish each declared section under its own anchor rather than its slug.

    The section keeps every other id it has, including one an explicit
    hyperlink target propagated onto it, so a label written for an older
    anchor keeps resolving. What changes is which id comes first, because that
    is the one the section element carries.
    """

    #: After docutils' ``PropagateTargets`` (260), which is what puts an
    #: explicit target's own id onto the section, so this decides the order of
    #: a complete set rather than of a set still being added to.
    default_priority = 300

    @override
    def apply(self, **kwargs: object) -> None:
        """Rename each declared section's leading id, then drop the declaration."""
        for declaration in list(self.document.findall(section_anchor)):
            section = _section_after(declaration)
            _publish_under(self.document, section, str(declaration["anchor"]))
            declaration.parent.remove(declaration)


def section_anchor_directive(anchor: str) -> str:
    """Return the directive text naming the anchor of the heading that follows.

    Args:
        anchor: The anchor name, which must already be a docutils id.

    Returns:
        The directive and the blank line separating it from what follows.
    """
    return f".. {SECTION_ANCHOR_DIRECTIVE}:: {anchor}\n\n"


def heading_anchor(heading: str) -> str:
    """Return the anchor a heading reading *heading* is published under.

    The slug is docutils' own (:func:`docutils.nodes.make_id`), so a heading
    already written in the source language keeps the anchor its own build
    published before any of this.

    Args:
        heading: The heading's plain text in the source language.

    Returns:
        The anchor name.

    Raises:
        SectionAnchorError: If the text slugs to nothing, which would leave the
            section with no anchor at all.
    """
    anchor = str(nodes.make_id(heading))
    if not anchor:
        raise SectionAnchorError(f"heading {heading!r} slugs to no anchor at all")
    return anchor


def _section_after(declaration: section_anchor) -> nodes.section:
    """Return the section the declaration stands before.

    The search is docutils' own for a hyperlink target standing before a
    heading: the next node in reading order, ascending out of the section the
    declaration is the last child of. A heading of the same depth as the one
    before it opens a sibling section, and the declaration written before it is
    body content of the section that closes there.

    Hyperlink targets and comments may stand between the declaration and the
    heading: a heading can carry both a declared anchor and a target naming an
    older label, and the declaration is written first so that the target still
    propagates onto the section rather than onto the declaration.
    """
    for following in declaration.findall(include_self=False, descend=False, siblings=True, ascend=True):
        if isinstance(following, nodes.section):
            return following
        if not isinstance(following, nodes.Invisible):
            break
    raise SectionAnchorError(
        f"anchor {declaration['anchor']!r} must stand immediately before a heading; "
        f"it stands before nothing it can name",
    )


def _publish_under(document: nodes.document, section: nodes.section, anchor: str) -> None:
    """Make *anchor* the id the section element carries."""
    if nodes.make_id(anchor) != anchor:
        raise SectionAnchorError(f"anchor {anchor!r} is not a docutils id; it would reach the page altered")
    slug = section["ids"][0]
    if slug == anchor:
        return
    standing = document.ids.get(anchor)
    if standing is not None and standing is not section:
        raise SectionAnchorError(f"anchor {anchor!r} is already published on this page by another element")
    section["ids"][0] = anchor
    if document.ids.get(slug) is section:
        del document.ids[slug]
    document.ids[anchor] = section
    # A name resolves to an id, and the heading's own words are one of this
    # section's names: left alone, a reference written to the heading would
    # resolve to the id the section no longer carries.
    for name, resolves_to in document.nameids.items():
        if resolves_to == slug:
            document.nameids[name] = anchor


def register(app: Sphinx) -> None:
    """Register the directive and the transform that applies it.

    Args:
        app: The Sphinx application instance.
    """
    app.add_directive(SECTION_ANCHOR_DIRECTIVE, SectionAnchorDirective)
    app.add_transform(AdoptSectionAnchors)
