"""Quoted official headings: grounded on their cited line, total over the modelos they cover, translated.

Every page and section of a covered modelo either carries an official heading
or is listed as unheaded with a reason, so a part never falls back to a
technical name unnoticed. Each quote is re-read here from the corpus file its
source catalogues, independently of the generator's own check, and the
generator is shown refusing a quote that is not grounded or names no part.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace
from functools import cache

import pytest

from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormGridBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...compiler.loader import load_registry_tree
from ...record_design_labels import DATA_ROOT
from ..cli import REGISTRY_ROOT
from ..generator import generate_revision_layout
from ..official_headings import (
    QUOTE_LINE_SPAN,
    OfficialHeadingRefusedError,
    QuotedHeading,
    read_official_headings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_COVERED = ("100", "349")
_LOCALES = ("es", "en", "ca", "hu")


@cache
def _registry() -> tuple[Mapping[str, ModeloDefinition], Mapping[str, SourceReference]]:
    modelos, catalogues = load_registry_tree(REGISTRY_ROOT)
    return {str(modelo.id): modelo for modelo in modelos}, catalogues.sources


def _revisions(modelo: str) -> Iterator[tuple[str, ModeloRevision]]:
    for revision_id, revision in sorted(_registry()[0][modelo].revisions.items()):
        yield str(revision_id), revision


def _layout(modelo: str, revision: str) -> FormLayoutDefinition:
    return _registry()[0][modelo].revisions[revision].form_layouts[0]


def _parts(layout: FormLayoutDefinition) -> Iterator[tuple[str, str | None, str | None]]:
    """Yield every page and section as ``(page, section, official heading)``."""
    for page in layout.pages:
        yield page.id, None, page.official_heading
        for section in page.sections:
            yield page.id, section.id, section.official_heading


def _quoted_keys(layout: FormLayoutDefinition) -> Iterator[tuple[str, str]]:
    """Yield the heading key and official words of every part that carries an official heading."""
    for page in layout.pages:
        if page.official_heading:
            yield page.heading_key, page.official_heading
        for section in page.sections:
            if section.official_heading:
                yield section.heading_key, section.official_heading
            for block in section.blocks:
                if isinstance(block, (FormGridBlock, FormRepeatingGroupBlock)):
                    yield from (
                        (column.heading_key, column.official_heading)
                        for column in block.columns
                        if column.official_heading
                    )


@pytest.mark.parametrize("modelo", _COVERED)
def test_every_page_and_section_is_headed_or_listed_with_its_reason(modelo: str) -> None:
    unheaded = read_official_headings().unheaded
    unaccounted = [
        (revision_id, page, section)
        for revision_id, _revision in _revisions(modelo)
        for page, section, heading in _parts(_layout(modelo, revision_id))
        if heading is None and not any(entry.covers(modelo, revision_id, page, section) for entry in unheaded)
    ]
    assert unaccounted == []


@pytest.mark.parametrize("modelo", _COVERED)
def test_no_unheaded_entry_names_a_headed_or_missing_part(modelo: str) -> None:
    stale = []
    for entry in read_official_headings().unheaded:
        if entry.modelo != modelo:
            continue
        assert entry.revisions, f"{entry} names no revision"
        for revision_id in entry.revisions:
            parts = {(page, section): heading for page, section, heading in _parts(_layout(modelo, revision_id))}
            if parts.get((entry.page, entry.section), "absent") is not None:
                stale.append((revision_id, entry.page, entry.section))
    assert stale == []


def _corpus_lines(source: SourceReference) -> list[str]:
    """Read a source's text the plain way: the extracted text beside a binary, else the file, split on newlines."""
    binary = DATA_ROOT / source.corpus_path
    extracted = binary.with_name(binary.name + ".extracted.md")
    payload = (extracted if extracted.is_file() else binary).read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252")
    return text.replace("\r\n", "\n").split("\n")


def test_every_quote_stands_on_its_cited_line_of_a_source_its_revision_cites() -> None:
    _modelos, sources = _registry()
    quotes = read_official_headings().quotes
    assert quotes
    ungrounded = []
    for quote in quotes:
        revision = _registry()[0][quote.modelo].revisions[quote.revision]
        lines = _corpus_lines(sources[quote.source_ref])
        window = " ".join(lines[quote.line - 1 : quote.line - 1 + QUOTE_LINE_SPAN]).casefold()
        if quote.source_ref not in revision.source_refs or " ".join(quote.text.casefold().split()) not in " ".join(
            window.split()
        ):
            ungrounded.append(quote.describe())
    assert ungrounded == []


def test_every_quote_heads_its_part_in_the_committed_layout() -> None:
    missing = []
    for quote in read_official_headings().quotes:
        found = {(page, section): heading for page, section, heading in _parts(_layout(quote.modelo, quote.revision))}
        if quote.column is None and found.get((quote.page, quote.section)) != quote.text:
            missing.append(quote.describe())
    assert missing == []


@pytest.mark.parametrize("modelo", _COVERED)
@pytest.mark.parametrize("locale", _LOCALES)
def test_every_official_heading_is_translated(modelo: str, locale: str) -> None:
    keys = {
        key for revision_id, _revision in _revisions(modelo) for key, _ in _quoted_keys(_layout(modelo, revision_id))
    }
    assert keys
    assert sorted(key for key in keys if not lookup_translation(key, locale=locale)) == []


@pytest.mark.parametrize("modelo", _COVERED)
def test_spanish_headings_are_the_official_words_and_english_ones_translate_them(modelo: str) -> None:
    pairs = {
        key: official
        for revision_id, _revision in _revisions(modelo)
        for key, official in _quoted_keys(_layout(modelo, revision_id))
    }
    not_official = {key for key, official in pairs.items() if lookup_translation(key, locale="es") != official}
    echoed = {key for key in pairs if lookup_translation(key, locale="en") == lookup_translation(key, locale="es")}
    assert not_official == set()
    assert echoed == set()


def _generate(modelo: str, revision_id: str, *quotes: QuotedHeading) -> FormLayoutDefinition | None:
    modelos, sources = _registry()
    revision = modelos[modelo].revisions[revision_id]
    return generate_revision_layout(modelo, revision, sources=sources, data_root=DATA_ROOT, headings=quotes).layout


_RENTA_PAGE = "datoseconomicos-tomadatosampliada"


_RENTA_QUOTE = QuotedHeading(
    modelo="100",
    revision="2025",
    page=_RENTA_PAGE,
    section="gpacciones",
    column=None,
    text="Transmisión de acciones negociadas",
    source_ref="aeat-dr-100-2025-input-dictionary",
    line=951,
)


def test_a_grounded_quote_heads_its_section_and_pins_its_source() -> None:
    layout = _generate("100", "2025", _RENTA_QUOTE)
    assert layout is not None
    section = next(
        section
        for page in layout.pages
        if page.id == _RENTA_PAGE
        for section in page.sections
        if section.id == "gpacciones"
    )
    assert section.official_heading == "Transmisión de acciones negociadas"
    assert section.heading_key == "modelo.schema.100.form.section.transmision-de-acciones-negociadas.heading"
    assert "aeat-dr-100-2025-input-dictionary" in {source.source_ref for source in layout.design_sources}


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        pytest.param({"line": 930}, "does not stand on line", id="words-not-on-the-line"),
        pytest.param({"text": "Transmisión de acciones cotizadas"}, "does not stand on line", id="altered-words"),
        pytest.param(
            {"source_ref": "aeat-dr-100-2024-input-dictionary", "line": 928},
            "does not cite",
            id="another-editions-source",
        ),
        pytest.param({"section": "no-such-section"}, "does not have", id="missing-section"),
        pytest.param({"line": 999_999}, "has no line", id="line-past-the-end"),
    ],
)
def test_an_ungrounded_or_misplaced_quote_is_refused(changes: dict[str, object], reason: str) -> None:
    with pytest.raises(OfficialHeadingRefusedError, match=reason):
        _generate("100", "2025", replace(_RENTA_QUOTE, **changes))


def test_a_quote_for_a_part_the_design_already_names_is_refused() -> None:
    layout = _layout("130", "2019-y-siguientes")
    page = layout.pages[0]
    section = page.sections[0]
    assert section.official_heading is not None
    source = layout.design_sources[0].source_ref
    words = section.official_heading.casefold()
    line = next(
        number
        for number, text in enumerate(_corpus_lines(_registry()[1][source]), start=1)
        if words in " ".join(text.casefold().split())
    )
    quote = QuotedHeading("130", "2019-y-siguientes", page.id, section.id, None, section.official_heading, source, line)
    with pytest.raises(OfficialHeadingRefusedError, match="already names"):
        _generate("130", "2019-y-siguientes", quote)


def test_a_quote_for_a_column_the_block_does_not_have_is_refused() -> None:
    quote = QuotedHeading(
        "349",
        "2020-y-siguientes",
        "modelo-349-operador",
        "general",
        "no-such-column",
        "Clave de operación",
        "aeat-dr-349-2020-current",
        317,
    )
    with pytest.raises(OfficialHeadingRefusedError, match="no column"):
        _generate("349", "2020-y-siguientes", quote)


def test_349_columns_carry_the_designs_field_names() -> None:
    layout = _layout("349", "2020-y-siguientes")
    columns = {
        column.key: column.official_heading
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
        for column in block.columns
    }
    assert columns
    assert [key for key, heading in columns.items() if heading is None] == []
