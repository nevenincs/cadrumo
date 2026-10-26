"""The declared anchor of a generated heading, through the real parser.

A generated page's heading is written in the reader's language, so the slug
docutils would name its section after moves with the language and the one
compile cannot publish it at all. The heading declares its anchor instead
(:mod:`dev.docs.section_anchors`).

Every case here parses real RST with the real directive registered and runs the
real transform as a reader's transform, because what is under test is what
docutils does with the declaration and not what the directive returns: the
defect the directive exists for is precisely that an explicit hyperlink target,
which docutils does accept before a heading, leaves the heading's own slug as
the id the section element carries.
"""

from __future__ import annotations

from typing import override

import pytest
from docutils import nodes
from docutils.core import publish_doctree
from docutils.parsers.rst import directives
from docutils.readers import standalone
from docutils.transforms import Transform
from docutils.utils import SystemMessage

from ..section_anchors import (
    SECTION_ANCHOR_DIRECTIVE,
    AdoptSectionAnchors,
    SectionAnchorDirective,
    SectionAnchorError,
    heading_anchor,
    section_anchor_directive,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


class _Reader(standalone.Reader):
    """The standalone reader with the anchor transform Sphinx registers."""

    @override
    def get_transforms(self) -> list[type[Transform]]:
        """Return the standard transforms plus the one under test."""
        return [*super().get_transforms(), AdoptSectionAnchors]


def _parsed(source: str) -> nodes.document:
    """Return the doctree docutils reads from *source*, anchors applied.

    ``doctitle_xform`` is off because Sphinx reads with it off: a page's own
    heading stays a section rather than being promoted to the document, which
    is the node the anchor has to name.
    """
    directives.register_directive(SECTION_ANCHOR_DIRECTIVE, SectionAnchorDirective)
    document = publish_doctree(
        source,
        reader=_Reader(),
        settings_overrides={"doctitle_xform": False, "report_level": 5, "halt_level": 5},
    )
    assert isinstance(document, nodes.document)
    return document


def _sections(document: nodes.document) -> list[nodes.section]:
    return list(document.findall(nodes.section))


def test_the_declared_anchor_is_the_id_the_section_carries() -> None:
    """A declaring heading's section is published under the declared anchor.

    The heading's own words are Spanish, so the slug docutils named the section
    after was ``indicadores-globales``; the declaration publishes it under the
    English anchor every language root shares.
    """
    document = _parsed(
        f"{section_anchor_directive('global-flags')}Indicadores globales\n====================\n\nTexto.\n",
    )
    section = _sections(document)[0]
    assert section["ids"][0] == "global-flags"
    assert "indicadores-globales" not in document.ids


def test_the_heading_s_own_words_still_resolve_to_it() -> None:
    """A reference written to the heading reaches the section's new id.

    The heading's words stay a name of the section, so a reference written to
    them has to resolve to the id the section now carries rather than to the
    slug it no longer has.
    """
    document = _parsed(
        f"{section_anchor_directive('global-flags')}Indicadores globales\n====================\n\nTexto.\n",
    )
    assert document.nameids["indicadores globales"] == "global-flags"


def test_an_explicit_target_before_the_heading_keeps_resolving() -> None:
    """An older label on the same heading stays an id of the section.

    The generated reference publishes ``cli-reference-exit-codes`` as a label
    of a heading that now declares an anchor as well. The declaration is
    written first so the target still propagates onto the section: the section
    carries the declared anchor, and the label's id after it.
    """
    document = _parsed(
        f"{section_anchor_directive('exit-codes')}"
        ".. _cli-reference-exit-codes:\n\n"
        "Códigos de salida\n"
        "=================\n\n"
        "Texto.\n",
    )
    section = _sections(document)[0]
    assert section["ids"][0] == "exit-codes"
    assert "cli-reference-exit-codes" in section["ids"]
    assert document.nameids["cli-reference-exit-codes"] == "cli-reference-exit-codes"


def test_a_heading_written_in_the_source_language_is_unchanged() -> None:
    """Declaring the slug the heading already had changes no id.

    This is the English roots' case, and it is why they keep the anchors they
    have published all along.
    """
    document = _parsed(f"{section_anchor_directive('global-flags')}Global flags\n============\n\nText.\n")
    assert _sections(document)[0]["ids"] == ["global-flags"]


def test_an_anchor_standing_before_no_heading_refuses() -> None:
    """A declaration that names nothing is an authoring fault, not a silent pass."""
    with pytest.raises(SectionAnchorError, match="immediately before a heading"):
        _parsed(f"{section_anchor_directive('global-flags')}Just a paragraph.\n")


def test_a_heading_of_the_same_depth_is_the_one_named() -> None:
    """A declaration before a sibling heading names that heading's section.

    A heading of the same depth closes the section before it, so the
    declaration written for it is the last body child of that earlier section
    rather than a sibling of the section it names. This is the shape the CLI
    index page has, where several headings of one depth follow each other.
    """
    document = _parsed(
        f"{section_anchor_directive('cli-reference')}Referencia\n==========\n\n"
        f"{section_anchor_directive('global-flags')}Indicadores globales\n--------------------\n\n"
        f"{section_anchor_directive('where-to-go-next')}Adónde ir después\n-----------------\n\nTexto.\n",
    )
    assert [section["ids"][0] for section in _sections(document)] == [
        "cli-reference",
        "global-flags",
        "where-to-go-next",
    ]


def test_two_headings_declaring_one_anchor_refuse() -> None:
    """One page cannot publish two sections under the same anchor."""
    source = (
        f"{section_anchor_directive('global-flags')}Primera\n=======\n\n"
        f"{section_anchor_directive('global-flags')}Segunda\n=======\n"
    )
    with pytest.raises(SectionAnchorError, match="already published on this page"):
        _parsed(source)


def test_an_anchor_that_is_not_an_id_refuses() -> None:
    """A declared anchor docutils would alter never reaches a page altered."""
    with pytest.raises(SectionAnchorError, match="not a docutils id"):
        _parsed(f"{section_anchor_directive('Global_Flags')}Global flags\n============\n")


def test_the_directive_takes_exactly_one_argument() -> None:
    """A declaration with no anchor is a parse error rather than a nameless section."""
    directives.register_directive(SECTION_ANCHOR_DIRECTIVE, SectionAnchorDirective)
    with pytest.raises(SystemMessage):
        publish_doctree(
            f".. {SECTION_ANCHOR_DIRECTIVE}::\n\nGlobal flags\n============\n",
            reader=_Reader(),
            settings_overrides={"doctitle_xform": False, "report_level": 5, "halt_level": 2},
        )


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        ("Global flags", "global-flags"),
        ("Where to go next", "where-to-go-next"),
        (
            "Modelo 036: Register of entrepreneurs, professionals and withholders",
            "modelo-036-register-of-entrepreneurs-professionals-and-withholders",
        ),
    ],
)
def test_the_anchor_of_a_heading_is_docutils_own_slug(heading: str, anchor: str) -> None:
    """The anchor derived for a heading is the one its own build published.

    The expected values are the ids the English roots shipped before any
    heading declared an anchor, written out here rather than taken from the
    slugger, so a change to how the anchor is derived is a failure.
    """
    assert heading_anchor(heading) == anchor


def test_a_heading_that_slugs_to_nothing_refuses() -> None:
    """A heading with no sluggable character cannot be given an anchor silently."""
    with pytest.raises(SectionAnchorError, match="slugs to no anchor"):
        heading_anchor("---")
