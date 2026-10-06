"""One structure and each language's strings give every language's page back exactly.

The pages here are written by hand in the shapes the built roots take: the same
markup with different text and attribute values, a language that carries markup
the others lack, and a label that recurs. Each expected result is stated
directly, so nothing is compared with what the code under test produced.
"""

from __future__ import annotations

import pytest

from ..shared_structure import (
    SLOT_CLOSE,
    SLOT_OPEN,
    SharedStructureError,
    compose_page,
    factor_page,
    factor_pages,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_ENGLISH = (
    '<html lang="en"><body><nav><a href="a.html" title="Legal basis">Legal basis</a></nav>'
    '<article id="c-01"><h3>Tax base</h3><p>You enter this</p>'
    '<dl><dt>Legal basis</dt><dd><a href="law.html#art-1" title="ley:art-1">art. 1</a></dd></dl></article>'
    "</body></html>"
)
_SPANISH = (
    '<html lang="es"><body><nav><a href="a.html" title="Base legal">Base legal</a></nav>'
    '<article id="c-01"><h3>Base imponible</h3><p>Lo introduces <em>tú</em></p>'
    '<dl><dt>Base legal</dt><dd><a href="law.html#art-1" title="ley:art-1">art. 1</a></dd></dl></article>'
    '<script src="translations.js"></script></body></html>'
)
_CATALAN = (
    '<html lang="ca"><body><nav><a href="a.html" title="Base legal">Base legal</a></nav>'
    '<article id="c-01"><h3>Base imposable</h3><p>Ho introdueixes tu</p>'
    '<dl><dt>Base legal</dt><dd><a href="law.html#art-1" title="ley:art-1">art. 1</a></dd></dl></article>'
    '<script src="translations.js"></script></body></html>'
)
_LANGUAGES = ("en", "es", "ca")
_PAGES = (_ENGLISH, _SPANISH, _CATALAN)


def test_every_language_page_is_recovered_byte_for_byte() -> None:
    structures, text = factor_pages({"c.html": _PAGES}, _LANGUAGES)
    for language, page in zip(_LANGUAGES, _PAGES, strict=True):
        assert compose_page(structures["c.html"], text.strings[language]) == page


def test_the_structure_holds_what_the_languages_share_and_none_of_their_text() -> None:
    structures, _ = factor_pages({"c.html": _PAGES}, _LANGUAGES)
    structure = structures["c.html"]
    for shared in ('<article id="c-01">', 'href="law.html#art-1" title="ley:art-1">art. 1</a>', "</body></html>"):
        assert shared in structure
    for translated in ("Legal basis", "Base legal", "Tax base", "Base imponible", "Ho introdueixes tu", 'lang="es"'):
        assert translated not in structure


def test_a_string_is_the_translated_text_itself_and_a_recurring_one_is_stored_once() -> None:
    _, text = factor_pages({"c.html": _PAGES}, _LANGUAGES)
    assert text.strings["es"].count("Base legal") == 1
    assert text.strings["en"].count("Legal basis") == 1
    assert "Base imponible" in text.strings["es"]
    assert "Base imposable" in text.strings["ca"]
    assert {len(strings) for strings in text.strings.values()} == {len(text.strings["en"])}


def test_markup_only_some_languages_carry_becomes_a_slot_the_others_leave_empty() -> None:
    _, text = factor_pages({"c.html": _PAGES}, _LANGUAGES)
    script = '<script src="translations.js"></script>'
    number = text.strings["es"].index(script)
    assert text.strings["ca"][number] == script
    assert text.strings["en"][number] == ""
    emphasized = next(value for value in text.strings["es"] if "<em>tú</em>" in value)
    assert emphasized == "Lo introduces <em>tú</em>"


def test_slots_are_numbered_across_pages_so_one_label_serves_them_all() -> None:
    second = tuple(page.replace("c-01", "c-02") for page in _PAGES)
    structures, text = factor_pages({"c.html": _PAGES, "d.html": second}, _LANGUAGES)
    assert text.strings["es"].count("Base legal") == 1
    for language, page in zip(_LANGUAGES, second, strict=True):
        assert compose_page(structures["d.html"], text.strings[language]) == page


def test_pages_that_do_not_line_up_at_all_are_still_recovered() -> None:
    pages = ("<p>one</p>", "<table><tr><td>uno</td></tr></table><p>dos</p><ul><li>tres</li></ul>", "")
    factored = factor_page(pages)
    structures, text = factor_pages({"x.html": pages}, _LANGUAGES)
    assert any(isinstance(part, tuple) for part in factored)
    for language, page in zip(_LANGUAGES, pages, strict=True):
        assert compose_page(structures["x.html"], text.strings[language]) == page


def test_identical_pages_need_no_slot() -> None:
    structures, text = factor_pages({"same.html": (_ENGLISH, _ENGLISH, _ENGLISH)}, _LANGUAGES)
    assert structures["same.html"] == _ENGLISH
    assert text.strings == {"en": [], "es": [], "ca": []}


@pytest.mark.parametrize("delimiter", [SLOT_OPEN, SLOT_CLOSE])
def test_a_page_that_already_holds_a_slot_delimiter_is_refused(delimiter: str) -> None:
    with pytest.raises(SharedStructureError, match="reserved for slot delimiters"):
        factor_page((_ENGLISH, _SPANISH.replace("Base imponible", f"Base{delimiter}imponible")))


def test_the_format_is_the_one_the_desktop_host_composes() -> None:
    """The same vector is replayed by the documentation scheme's own composer."""
    structure = f"<p>{SLOT_OPEN}0{SLOT_CLOSE}</p><i>{SLOT_OPEN}a{SLOT_CLOSE}</i>"
    strings = ["uno", *[""] * 9, "dos & tres"]
    assert compose_page(structure, strings) == "<p>uno</p><i>dos & tres</i>"


def test_a_structure_naming_a_slot_the_language_lacks_is_refused() -> None:
    structures, text = factor_pages({"c.html": _PAGES}, _LANGUAGES)
    with pytest.raises(SharedStructureError, match="past the language's"):
        compose_page(structures["c.html"], text.strings["es"][:1])
