"""Regression coverage for the generated legal-reference RST projection."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html import unescape
from io import StringIO
from pathlib import Path
from typing import TypedDict

import pytest
from bs4 import BeautifulSoup, Comment
from bs4.element import Tag
from docutils import nodes
from docutils.core import publish_doctree, publish_parts

from cadrumo.core.directory_scan import iter_directory, scan_directory
from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT
from dev.locales.signal_documentation_inventory import inventory_generated_document_file

from ..legal_catalogue import load_legal_provisions
from ..legal_page_rendering import _rst_escape
from ..legal_reference import generate_legal_reference, render_legal_reference
from ..legal_reference_models import LegalProvisionRecord, LegalReferenceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


#: Floor for the legal pages the live catalogue renders. Live it renders
#: 160 pages beside the index. Every live-corpus claim below reads a
#: population an empty catalogue empties, and the generator prunes before
#: it writes with the index always in its keep set -- so a render that
#: produced no page leaves exactly one file standing, which is what an
#: existence check accepts.
_MINIMUM_LEGAL_PAGES = 100

_REPO_ROOT = REPO_ROOT


_QUOTED_RE = re.compile(r'<blockquote lang="es">(?P<body>.*?)</blockquote>', re.DOTALL)


def _system_messages(rst: str) -> tuple[str, ...]:
    """Parse generated RST and return docutils diagnostics from its tree."""
    warning_stream = StringIO()
    doctree = publish_doctree(
        rst,
        settings_overrides={"report_level": 1, "warning_stream": warning_stream},
    )
    messages: list[str] = []
    for node in doctree.findall(nodes.system_message):
        message = node.astext()
        if not isinstance(message, str):
            raise AssertionError("docutils system message text must be a string")
        messages.append(message)
    return tuple(messages)


def _quoted_extracts(rst: str) -> list[str]:
    """The official-wording paragraphs the page emits, unescaped back to text.

    Read out of the emitted HTML because that is what reaches the reader. The
    surrounding ``lang="es"`` is required by the pattern, so a block that lost
    its language marking yields nothing and every extract assertion fails.
    """
    return [
        unescape(paragraph)
        for match in _QUOTED_RE.finditer(rst)
        for paragraph in re.findall(r"<p>(.*?)</p>", match.group("body"), re.DOTALL)
    ]


def _headings(rst: str) -> list[str]:
    """The provision headings on a page, read from their RST underlines."""
    lines = rst.splitlines()
    return [line for index, line in enumerate(lines) if index + 1 < len(lines) and set(lines[index + 1]) == {"-"}]


def test_required_text_trailing_whitespace_is_removed_only_from_rst_projection() -> None:
    """The rendered wording extract is trimmed without mutating the authored tuple."""
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-99",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-99.html#a99",
        permalink="https://www.boe.es/eli/es/l/1992/12/28/37",
        required_text=("first authoritative phrase ", "second authoritative phrase"),
    )

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]

    assert record.required_text == ("first authoritative phrase ", "second authoritative phrase")
    assert _quoted_extracts(page.rst) == ["first authoritative phrase", "second authoritative phrase"]
    assert _system_messages(page.rst) == ()


def test_each_authored_extract_renders_as_its_own_block() -> None:
    """Disjoint extracts stay disjoint; they never merge into continuous wording.

    ``required_text`` holds separate phrases lifted from different parts of a
    provision. Rendered into one paragraph they would read as one continuous
    piece of statutory wording that the provision does not contain, which is a
    legal misstatement made by presentation alone.
    """
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-98",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a98",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a98",
        article="98",
        required_text=("primera frase autoritativa", "segunda frase autoritativa"),
    )

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]

    assert _quoted_extracts(page.rst) == ["primera frase autoritativa", "segunda frase autoritativa"]


def test_an_extract_opening_with_a_subparagraph_marker_is_not_reparsed() -> None:
    """An extract beginning ``b)`` stays a quotation, never becomes a list item.

    Spanish provisions are written in lettered subparagraphs, so an authored
    extract routinely opens with one. Left unescaped, docutils reads it as an
    enumerated list and restructures the official wording; the rendered text
    must come back exactly as authored.
    """
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-97",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a97",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a97",
        article="97",
        required_text=("b) las facturas expedidas por el empresario",),
    )

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]
    doctree = publish_doctree(page.rst, settings_overrides={"report_level": 5})

    assert not list(doctree.findall(nodes.enumerated_list))
    assert _quoted_extracts(page.rst) == ["b) las facturas expedidas por el empresario"]
    assert _system_messages(page.rst) == ()


def test_official_wording_is_marked_spanish_and_the_note_is_not_the_summary() -> None:
    """The Spanish boundary is explicit, and the unlabelled note does not lead.

    Two rules meet on this entry. The official wording is Spanish that this
    layer may not translate, so it is marked ``lang="es"`` rather than left for
    the reader to infer. The authored ``notes`` field has no declared language
    at all -- it is Spanish on most rows and English on others -- so it may not
    occupy the summary position where a reader expects the answer; it belongs
    with the provenance.
    """
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-96",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a96",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a96",
        article="96",
        notes="una nota del catalogo sin idioma declarado",
        required_text=("no seran deducibles las cuotas soportadas",),
    )

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]

    assert _quoted_extracts(page.rst) == ["no seran deducibles las cuotas soportadas"]

    note_at = page.rst.index("una nota del catalogo sin idioma declarado")
    wording_at = page.rst.index("no seran deducibles las cuotas soportadas")
    record_panel_at = page.rst.index("cadrumo-legal-record")
    assert note_at > wording_at, "the undeclared-language note is leading the entry"
    assert note_at > record_panel_at, "the note is outside the provenance panel"


def test_generated_inventory_checks_wording_in_spanish_and_commentary_in_english(tmp_path: Path) -> None:
    """The language boundary survives the renderer and the spelling inventory together."""
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-96",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a96",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a96",
        article="96",
        notes="English curator commentary remains checked.",
        required_text=("no serán deducibles las cuotas soportadas",),
    )
    page = tmp_path / "docs/_generated/legal/example.rst"
    page.parent.mkdir(parents=True)
    page.write_text(render_legal_reference(_REPO_ROOT, records=(record,)).pages[0].rst, encoding="utf-8")
    values: dict[str, dict[str, str]] = {}
    findings: list[dict[str, object]] = []

    inventory_generated_document_file(page, tmp_path, Counter(), findings, values)

    assert not findings
    assert "no serán deducibles las cuotas soportadas" in values["es"].values()
    assert any("English curator commentary remains checked." in text for text in values["en"].values())
    assert all("no serán deducibles las cuotas soportadas" not in text for text in values["en"].values())


def test_mixed_catalogue_note_tags_only_source_verified_quote_and_keeps_english_checked(tmp_path: Path) -> None:
    quote = "La cuota tributaria se determinará aplicando el tipo correspondiente."
    source = tmp_path / "src/cadrumo/_data/corpus/normatives/html/example.html.extracted.md"
    source.parent.mkdir(parents=True)
    source.write_text(f"Excerpt: {quote}\n", encoding="utf-8")
    record = LegalProvisionRecord(
        legal_id="ley-example:art-1",
        kind="ley",
        document_id="BOE-A-2000-1",
        corpus_ref="corpus/normatives/html/example.html#art-1",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-1#art-1",
        article="1",
        notes=f"The old rule said: {quote} This neighboring English definately stays checked.",
        required_text=(quote,),
    )

    page = tmp_path / "docs/_generated/legal/example.rst"
    page.parent.mkdir(parents=True)
    page.write_text(render_legal_reference(tmp_path, records=(record,)).pages[0].rst, encoding="utf-8")
    values: dict[str, dict[str, str]] = {}
    findings: list[dict[str, object]] = []
    inventory_generated_document_file(page, tmp_path, Counter(), findings, values)

    assert f'<span lang="es">{quote}</span>' in page.read_text(encoding="utf-8")
    assert any("This neighboring English definately stays checked." in text for text in values["en"].values())
    assert any(quote in text for text in values["es"].values())
    assert all(quote not in text for text in values["en"].values())
    assert any("definately" in text for text in values["en"].values())


def test_tagged_note_changes_only_the_quote_language_span(tmp_path: Path) -> None:
    quote = "La cuota tributaria se determina según la ley."
    note = f"English note starts. {quote} English note ends."
    source = tmp_path / "src/cadrumo/_data/corpus/normatives/html/example.html.extracted.md"
    source.parent.mkdir(parents=True)
    source.write_text(quote, encoding="utf-8")
    record = LegalProvisionRecord(
        legal_id="ley-example:art-5",
        kind="ley",
        document_id="BOE-A-2000-6",
        corpus_ref="corpus/normatives/html/example.html#art-5",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-6#art-5",
        article="5",
        notes=note,
        required_text=(quote,),
    )

    tagged_rst = render_legal_reference(tmp_path, records=(record,), language=OutputLanguage.EN).pages[0].rst
    raw_note = re.search(
        r"   \.\. raw:: html\n\n      <dl class=\"field-list simple\">\n"
        r"        <dt>.*?</dt>.*?<!--cadrumo-legal-note-->.*?</dl>",
        tagged_rst,
        re.DOTALL,
    )
    assert raw_note is not None
    prior_rst = tagged_rst.replace(raw_note.group(), f"   :Cataloguer's note: {_rst_escape(note)}")

    before = publish_parts(prior_rst, writer_name="html5")["html_body"]
    after = publish_parts(tagged_rst, writer_name="html5")["html_body"]
    before_soup = BeautifulSoup(before, "html.parser")
    after_soup = BeautifulSoup(after, "html.parser")
    old_term = next(item for item in before_soup.find_all("dt") if "note" in item.get_text().casefold())
    new_term = next(item for item in after_soup.find_all("dt") if "note" in item.get_text().casefold())
    assert new_term.get_text() == old_term.get_text()

    def note_definition(soup: BeautifulSoup) -> Tag | None:
        term = next(item for item in soup.find_all("dt") if "note" in item.get_text().casefold())
        return term.find_next_sibling("dd")

    old_definition = note_definition(before_soup)
    new_definition = note_definition(after_soup)
    assert old_definition is not None
    assert new_definition is not None
    spanish_span = new_definition.find("span", attrs={"lang": "es"})
    assert isinstance(spanish_span, Tag)
    spanish_span.unwrap()
    for comment in new_definition.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()

    def structure(node: Tag) -> object:
        attributes = tuple(sorted(node.attrs.items()))
        direct_text = "".join(
            str(child) for child in node.children if not isinstance(child, Tag) and str(child).strip()
        )
        children = tuple(structure(child) for child in node.children if isinstance(child, Tag))
        return node.name, attributes, direct_text, children

    assert structure(new_definition) == structure(old_definition)
    assert new_definition.get_text(" ", strip=True) == note
    assert len(new_definition.find_all("p")) == 1
    assert new_definition.find_all("a") == old_definition.find_all("a")


def test_stale_or_ambiguous_note_quote_is_not_tagged(tmp_path: Path) -> None:
    source = tmp_path / "src/cadrumo/_data/corpus/normatives/html/example.html.extracted.md"
    source.parent.mkdir(parents=True)
    stale_quote = "Una frase que ya no está en la fuente."
    ambiguous_quote = "Una frase oficial repetida en la nota."
    source.write_text(f"The official text says a different thing. {ambiguous_quote}", encoding="utf-8")
    records = (
        LegalProvisionRecord(
            legal_id="ley-example:art-2",
            kind="ley",
            document_id="BOE-A-2000-2",
            corpus_ref="corpus/normatives/html/example.html#art-2",
            permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-2#art-2",
            article="2",
            notes=stale_quote,
            required_text=(stale_quote,),
        ),
        LegalProvisionRecord(
            legal_id="ley-example:art-3",
            kind="ley",
            document_id="BOE-A-2000-2",
            corpus_ref="corpus/normatives/html/example.html#art-3",
            permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-2#art-3",
            article="3",
            notes=f"{ambiguous_quote} {ambiguous_quote}",
            required_text=(ambiguous_quote,),
        ),
    )

    rst = render_legal_reference(tmp_path, records=records).pages[0].rst

    assert f'<span lang="es">{stale_quote}</span>' not in rst
    assert f'<span lang="es">{ambiguous_quote}</span>' not in rst


def test_link_like_note_keeps_its_existing_rst_projection(tmp_path: Path) -> None:
    quote = "Texto citado con fuente exacta."
    source = tmp_path / "src/cadrumo/_data/corpus/normatives/html/example.html.extracted.md"
    source.parent.mkdir(parents=True)
    source.write_text(quote, encoding="utf-8")
    note = f"{quote} See `official <https://example.test/law>`_ and keep this source text unchanged."
    record = LegalProvisionRecord(
        legal_id="ley-example:art-4",
        kind="ley",
        document_id="BOE-A-2000-4",
        corpus_ref="corpus/normatives/html/example.html#art-4",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-4#art-4",
        article="4",
        notes=note,
        required_text=(quote,),
    )

    rst = render_legal_reference(tmp_path, records=(record,)).pages[0].rst

    assert _rst_escape(note) in rst
    assert "https://example.test/law" in rst
    assert f'<span lang="es">{quote}</span>' not in rst
    rendered = BeautifulSoup(publish_parts(rst, writer_name="html5")["html_body"], "html.parser")
    term = next(item for item in rendered.find_all("dt") if "note" in item.get_text().casefold())
    definition = term.find_next_sibling("dd")
    assert definition is not None
    assert "official" in definition.get_text()
    assert "https://example.test/law" in definition.get_text()
    links = definition.find_all("a")
    assert len(links) == 1
    assert links[0]["href"] == "https://example.test/law"
    assert len(definition.find_all("p")) == 1


def test_shared_corpus_excerpt_is_read_once_per_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first_quote = "Primera frase exacta."
    second_quote = "Segunda frase exacta."
    source = tmp_path / "src/cadrumo/_data/corpus/normatives/html/example.html.extracted.md"
    source.parent.mkdir(parents=True)
    source.write_text(f"{first_quote} {second_quote}", encoding="utf-8")
    records = tuple(
        LegalProvisionRecord(
            legal_id=f"ley-example:art-{number}",
            kind="ley",
            document_id="BOE-A-2000-5",
            corpus_ref=f"corpus/normatives/html/example.html#art-{number}",
            permalink=f"https://www.boe.es/buscar/act.php?id=BOE-A-2000-5#art-{number}",
            article=str(number),
            notes=quote,
            required_text=(quote,),
        )
        for number, quote in ((1, first_quote), (2, second_quote))
    )
    original_read_text = Path.read_text
    source_reads = 0

    def counted_read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        nonlocal source_reads
        if path.resolve() == source.resolve():
            source_reads += 1
        return original_read_text(path, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", counted_read_text)

    result = render_legal_reference(tmp_path, records=records)

    assert source_reads == 1
    assert result.provision_count == 2


def test_provision_heading_leads_with_the_citation_not_the_catalogue_id() -> None:
    """A provision heading reads as a citation; the id is demoted, not dropped.

    The reader arrives on a fragment anchor with no page context above it, so
    the heading has to say which instrument and which article this is. The raw
    catalogue id is still rendered on the page, in the provenance block, so the
    grounding stays traceable.
    """
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-92",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a92",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a92",
        article="92",
    )

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]

    assert _headings(page.rst) == ["Ley 37/1992, art. 92"]
    assert page.instrument == "Ley 37/1992"
    assert "``ley-37-1992:art-92``" in page.rst


class _SharedProvisionFields(TypedDict):
    """The catalogue fields both consolidated versions of one article share."""

    kind: str
    document_id: str
    corpus_ref: str
    permalink: str
    article: str


def test_same_article_versions_get_distinct_headings_by_in_force_date() -> None:
    """Consolidated versions of one article are told apart by their in-force date.

    Several rows legitimately share an article number, one per filing-year
    version. A shared heading would leave a reader unable to tell which version
    governs their year, so the authored ``effective_from`` disambiguates.
    """
    common: _SharedProvisionFields = {
        "kind": "ley",
        "document_id": "BOE-A-2006-20764",
        "corpus_ref": "corpus/normatives/html/ley-35-2006.html#a52",
        "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a52",
        "article": "52",
    }
    records = (
        LegalProvisionRecord(legal_id="ley-35-2006:art-52", effective_from=date(2015, 1, 1), **common),
        LegalProvisionRecord(legal_id="ley-35-2006:art-52-2021", effective_from=date(2021, 1, 1), **common),
    )

    page = render_legal_reference(_REPO_ROOT, records=records).pages[0]
    headings = _headings(page.rst)

    assert len(headings) == len(set(headings)) == 2
    assert all(heading.startswith("Ley 35/2006, art. 52") for heading in headings)
    assert {"2015-01-01" in heading for heading in headings} == {True, False}
    assert {"2021-01-01" in heading for heading in headings} == {True, False}
    assert _system_messages(page.rst) == ()


def test_authoritative_legal_pages_are_docutils_clean() -> None:
    """The registry-backed legal pages contain no docutils warnings."""
    result = render_legal_reference(_REPO_ROOT)
    failures = [
        f"{page.output_relpath}: {messages}" for page in result.pages if (messages := _system_messages(page.rst))
    ]

    # The comprehension above ranges over the live catalogue, so an empty
    # one yields no failure and this absence claim holds over nothing.
    assert len(result.pages) >= _MINIMUM_LEGAL_PAGES, (
        f"the catalogue rendered only {len(result.pages)} pages, so the diagnostic claim "
        "below reads almost none of the legal reference"
    )
    assert not failures, "generated legal-reference RST has docutils diagnostics:\n" + "\n".join(failures)


def _generated_legal_dir(tmp_path: Path) -> Path:
    """Return a docs root prepared for the generator's validated output directory."""
    (tmp_path / "_generated").mkdir(parents=True)
    return tmp_path / "_generated" / "legal"


def test_regenerating_an_unchanged_catalogue_leaves_every_page_untouched(tmp_path: Path) -> None:
    """A second render rewrites nothing, so Sphinx has no reason to re-read the tree.

    The generator prunes before writing. While that prune deleted every page
    unconditionally, the write-if-changed comparison downstream always saw a
    missing file, so all 141 pages were recreated with fresh mtimes on every
    build and the whole legal tree was re-read and re-written for free.
    """
    out_dir = _generated_legal_dir(tmp_path)
    generate_legal_reference(tmp_path, repo_root=_REPO_ROOT)
    before = {path.name: path.stat().st_mtime_ns for path in scan_directory(out_dir, pattern="*.rst")}

    generate_legal_reference(tmp_path, repo_root=_REPO_ROOT)
    after = {path.name: path.stat().st_mtime_ns for path in scan_directory(out_dir, pattern="*.rst")}

    # A count, not a truthiness test: the prune keeps the index
    # unconditionally, so a collapsed catalogue leaves ``before`` holding
    # index.rst alone and both assertions here hold over one file.
    assert len(before) >= _MINIMUM_LEGAL_PAGES, (
        f"the catalogue rendered only {len(before)} files, so the mtime comparison "
        "below proves nothing about the pages it was meant to leave untouched"
    )
    assert after == before


def test_a_page_the_catalogue_no_longer_produces_is_still_pruned(tmp_path: Path) -> None:
    """Narrowing the prune to unrendered files must not cost it its purpose.

    A dropped legal document leaves a page behind that Sphinx would keep
    reading; the sweep exists to remove exactly that.
    """
    out_dir = _generated_legal_dir(tmp_path)
    generate_legal_reference(tmp_path, repo_root=_REPO_ROOT)
    stale = out_dir / "retired-document.rst"
    stale.write_text("Stale\n=====\n", encoding="utf-8", newline="\n")

    generate_legal_reference(tmp_path, repo_root=_REPO_ROOT)

    assert not stale.exists()
    # ``any(...)`` was satisfied by index.rst alone, which the sweep keeps
    # whatever the catalogue produced; count the survivors instead.
    survivors = list(iter_directory(out_dir, pattern="*.rst"))
    assert len(survivors) >= _MINIMUM_LEGAL_PAGES, (
        f"the prune left only {len(survivors)} page(s); it was meant to keep the whole "
        "rendered catalogue and remove just the unowned page"
    )


def _windowed_record(*, effective_from: date | None, effective_to: date | None) -> LegalProvisionRecord:
    """One catalogue row carrying only the declared effectivity window."""
    return LegalProvisionRecord(
        legal_id="ley-37-1992:art-96",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a96",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a96",
        article="96",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_an_effectivity_window_that_closes_before_it_opens_is_refused() -> None:
    """The rendered in-force sentence must not assert a span that runs backwards.

    Both endpoints are authored catalogue data, so each corroborates the
    other: a closing date earlier than the opening one is self-refuting on
    the record's own evidence, and the page would otherwise publish it as a
    legal-force claim about BOE authority.
    """
    record = _windowed_record(effective_from=date(2020, 1, 1), effective_to=date(2018, 1, 1))

    with pytest.raises(LegalReferenceError, match="closes before it opens"):
        render_legal_reference(_REPO_ROOT, records=(record,))


def test_a_well_ordered_effectivity_window_still_renders_its_span() -> None:
    """The refusal must not cost the surface a legitimately bounded provision."""
    record = _windowed_record(effective_from=date(2018, 1, 1), effective_to=date(2020, 1, 1))

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]

    assert "2018-01-01" in page.rst
    assert "2020-01-01" in page.rst


def test_a_window_closing_on_the_day_it_opens_is_admitted() -> None:
    """A provision in force for a single day is bounded, not contradictory."""
    record = _windowed_record(effective_from=date(2019, 6, 1), effective_to=date(2019, 6, 1))

    assert render_legal_reference(_REPO_ROOT, records=(record,)).pages


def test_a_record_declaring_no_closing_date_is_admitted_unchanged() -> None:
    """Records the check cannot speak to keep their existing behaviour.

    Most of the live catalogue declares an opening date and no closing one;
    an open-ended provision carries no second endpoint to contradict the
    first, so the window check must stay silent rather than invent one.
    """
    assert render_legal_reference(
        _REPO_ROOT, records=(_windowed_record(effective_from=date(2020, 1, 1), effective_to=None),)
    ).pages
    assert render_legal_reference(_REPO_ROOT, records=(_windowed_record(effective_from=None, effective_to=None),)).pages


def test_the_live_catalogue_declares_no_inverted_effectivity_window() -> None:
    """The live corpus passes the check, over a population that makes it mean something."""
    records = load_legal_provisions(_REPO_ROOT)
    bounded = [
        (record.legal_id, record.effective_from, record.effective_to)
        for record in records
        if record.effective_from is not None and record.effective_to is not None
    ]

    # Without a floor this passes vacuously on a catalogue that declares no
    # closing dates at all; the check only speaks to two-endpoint records.
    assert len(bounded) >= 20, (
        f"only {len(bounded)} of {len(records)} provisions declare both endpoints, so the "
        "assertion below would prove almost nothing about the live catalogue"
    )
    inverted = [legal_id for legal_id, opens, closes in bounded if closes < opens]
    assert inverted == []
