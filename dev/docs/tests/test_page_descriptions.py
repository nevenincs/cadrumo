"""A page's description comes from its own blocks of text, cut on a word boundary.

The doctrees are built by hand from docutils nodes, so what each test states is
the description one shape of page produces -- a heading and a paragraph, inline
markup, an aside, a body toctree -- rather than what a Sphinx build happened to
write. The cut is stated by hand as well: the length, the boundary it falls
back to, and the fact that nothing is escaped until after it.
"""

from __future__ import annotations

import html

import pytest
from docutils import nodes

from ..page_descriptions import description_content, description_source, with_description

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _document(*children: nodes.Node) -> nodes.document:
    """Return a document holding one section with *children* in it."""
    document = nodes.document(None, None)
    section = nodes.section()
    section.extend(children)
    document.append(section)
    return document


def _paragraph(*children: nodes.Node) -> nodes.paragraph:
    paragraph = nodes.paragraph()
    paragraph.extend(children)
    return paragraph


def _title(text: str) -> nodes.title:
    title = nodes.title()
    title.append(nodes.Text(text))
    return title


def test_the_pages_own_title_is_left_out_and_a_later_heading_is_not() -> None:
    """og:title carries the page's name, so the description starts at its text."""
    document = _document(
        _title("Filing calendar"),
        _paragraph(nodes.Text("When each return is due.")),
        _title("Quarterly returns"),
        _paragraph(nodes.Text("Four of them.")),
    )
    source = description_source(document, titles={"Filing calendar"})
    assert source == "When each return is due. Quarterly returns: Four of them."


def test_a_heading_that_is_not_the_pages_own_title_stays_in_the_description() -> None:
    """The first heading is only dropped where it is the title the page is named by."""
    document = _document(_title("Filing calendar"), _paragraph(nodes.Text("Due dates.")))
    assert description_source(document, titles={"Something else"}) == "Filing calendar: Due dates."


def test_inline_markup_keeps_the_whitespace_around_it() -> None:
    """The defect this module exists for: a block's own text already has the spaces.

    Joining the LEAF text instead strips each leaf and gives no space back
    before one that opens with punctuation, which published
    ``interface(CLI)``.
    """
    literal = nodes.literal()
    literal += nodes.Text("aeat")
    document = _document(
        _title("Reference"),
        _paragraph(nodes.Text("Its "), literal, nodes.Text(" command-line interface (CLI) reads.")),
    )
    source = description_source(document, titles={"Reference"})
    assert source == "Its aeat command-line interface (CLI) reads."


def test_an_aside_a_comment_and_a_literal_block_describe_nothing() -> None:
    """An admonition is an aside, a comment is not read, and a block is recorded output."""
    note = nodes.note()
    note += _paragraph(nodes.Text("Do not file twice."))
    block = nodes.literal_block()
    block += nodes.Text("aeat modelo 130 calculate")
    document = _document(
        _title("Modelo 130"),
        _paragraph(nodes.Text("The quarterly return.")),
        note,
        block,
        nodes.comment("", "internal"),
    )
    assert description_source(document, titles={"Modelo 130"}) == "The quarterly return."


def test_a_body_toctree_is_navigation_rather_than_what_the_page_is_about() -> None:
    """The titles of other pages stand in the sidebar of every page already."""
    entry = _paragraph(nodes.Text("Modelo 130"))
    listed = nodes.bullet_list()
    item = nodes.list_item()
    item += entry
    listed += item
    wrapper = nodes.compound(classes=["toctree-wrapper", "compound"])
    wrapper += listed
    document = _document(_title("Guides"), _paragraph(nodes.Text("Start here.")), wrapper)
    assert description_source(document, titles={"Guides"}) == "Start here."


def test_a_table_cell_and_a_definition_term_are_blocks_of_text() -> None:
    """Every outermost element that holds text describes the page, not paragraphs alone."""
    cell = nodes.entry()
    cell += _paragraph(nodes.Text("Fourth quarter"))
    row = nodes.row()
    row += cell
    body = nodes.tbody()
    body += row
    group = nodes.tgroup()
    group += body
    table = nodes.table()
    table += group
    term = nodes.term()
    term += nodes.Text("Prorrata")
    item = nodes.definition_list_item()
    item += term
    listed = nodes.definition_list()
    listed += item
    document = _document(_title("Terms"), table, listed)
    assert description_source(document, titles={"Terms"}) == "Fourth quarter Prorrata"


def test_a_wrapped_heading_and_a_wrapped_paragraph_read_as_one_line() -> None:
    """A source line break reaches a block's text, and a description is one line."""
    document = _document(
        _title("Filing\ncalendar"),
        _paragraph(nodes.Text("When each\n  return is due.")),
    )
    assert description_source(document, titles={"Filing calendar"}) == "When each return is due."


def test_a_description_within_the_length_is_escaped_and_not_cut() -> None:
    """A page shorter than the limit reads whole, with the markup characters escaped."""
    assert description_content('Ley 37/1992 & "IVA" <soportado>', length=180) == (
        "Ley 37/1992 &amp; &quot;IVA&quot; &lt;soportado&gt;"
    )


def test_a_longer_description_is_cut_back_to_a_word_boundary() -> None:
    """The cut never splits a word, and the ellipsis is counted in the length."""
    source = "Cadrumo prepares Spanish tax returns on your own machine and files nothing for you"
    cut = description_content(source, length=40)
    assert cut == "Cadrumo prepares Spanish tax returns…"
    assert len(cut) <= 40


def test_the_cut_is_made_before_the_escaping_so_it_cannot_split_a_reference() -> None:
    """``&amp;`` is five characters that mean one, and a cut inside it means nothing.

    The ampersand stands at the limit, so a cut made after escaping would land
    inside the reference it became. The limit counts the characters a reader
    sees, which is what the cut is made on; the escaped form is longer.
    """
    cut = description_content(f"{'word ' * 3}& and more words after it", length=20)
    assert cut == "word word word &amp;…"
    assert html.unescape(cut) == "word word word &…"
    assert len(html.unescape(cut)) <= 20


def test_an_empty_description_takes_the_tags_off_rather_than_emptying_them() -> None:
    """A page with no text of its own carries no description tag."""
    metatags = (
        '<meta property="og:title" content="Cadrumo" />\n'
        '<meta property="og:description" content="stale" />\n'
        '<meta name="description" content="stale" />\n'
    )
    assert with_description(metatags, "") == '<meta property="og:title" content="Cadrumo" />\n'


def test_the_description_replaces_whatever_wrote_one_before() -> None:
    """One authority for the page description: the extension's own is taken off."""
    metatags = (
        '<meta property="og:description" content="stale" />\n<meta property="og:url" content="u" />\n'
        '<meta name="description" content="stale" />\n'
    )
    written = with_description(metatags, "Due dates")
    assert written == (
        '<meta property="og:url" content="u" />\n'
        '<meta property="og:description" content="Due dates" />\n'
        '<meta name="description" content="Due dates" />\n'
    )


def test_a_page_that_carried_no_description_tag_is_given_both() -> None:
    """The tags are written rather than patched, so their absence is not a silence."""
    assert with_description('<meta name="viewport" content="x" />\n', "Due dates") == (
        '<meta name="viewport" content="x" />\n'
        '<meta property="og:description" content="Due dates" />\n'
        '<meta name="description" content="Due dates" />\n'
    )
