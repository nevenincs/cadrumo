"""Regression coverage for the generated legal-reference RST projection."""

from __future__ import annotations

import re
from datetime import date
from html import unescape
from io import StringIO
from pathlib import Path
from typing import TypedDict

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from cadrumo.core.directory_scan import iter_directory, scan_directory

from ..._paths import REPO_ROOT
from ..legal_reference import LegalProvisionRecord, generate_legal_reference, render_legal_reference

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT


_QUOTED_RE = re.compile(r'<blockquote lang="es">(?P<body>.*?)</blockquote>', re.DOTALL)


def _system_messages(rst: str) -> tuple[str, ...]:
    """Parse generated RST and return docutils diagnostics from its tree."""
    warning_stream = StringIO()
    doctree = publish_doctree(
        rst,
        settings_overrides={"report_level": 1, "warning_stream": warning_stream},
    )
    return tuple(node.astext() for node in doctree.findall(nodes.system_message))


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

    assert before, "the legal catalogue rendered no pages, so this proves nothing"
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
    assert any(iter_directory(out_dir, pattern="*.rst")), "the prune removed the pages it was meant to keep"
