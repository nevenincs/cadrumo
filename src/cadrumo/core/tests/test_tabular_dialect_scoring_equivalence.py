"""Equivalence gates for the streamed delimiter scorer and the lazy header walk.

Delimiter choice used to materialize the whole file once per candidate and
header location used to copy the whole remaining table once per candidate row.
Neither cost bought anything: only the field-count histogram decides the
delimiter, and only the first non-blank row below a candidate decides the
header. Both were made lazy.

Both are FINANCIAL parse decisions — which delimiter wins fixes how a bank
statement's columns are cut, and which row is the header fixes which lines
become movements — so a "faster" version that picks differently on one messy
export is a silent misparse of somebody's return. That makes equivalence, not
speed, the thing under test here.

Every test below compares the shipped helper against an eager reference
computed in the test: the reference materializes exactly what the shipped code
now streams past, so agreement over the corpus is direct evidence that laziness
changed nothing. The corpus is every delimited fixture bundled with the project
plus the hand-built edge cases in :data:`_EDGE_CASES`, which pin the shapes
real operator exports actually break on — a tie between two delimiters, a
delimiter quoted inside a field, a newline inside a quoted field, CRLF, a BOM,
and the degenerate empty and all-blank sources.

See Also:
    :class:`~core.NormalizedTable`
        The record the equivalence is ultimately about.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from pathlib import Path

import pytest

from ...tests import FIXTURES_DIR
from ..tabular import (
    _HEADER_SEARCH_LIMIT,
    CANDIDATE_DELIMITERS,
    TabularSourceError,
    _best_delimiter,
    _header_score,
    _locate_header,
    _parse_with,
    _rectangle_score,
    _score_delimiter,
    normalize_tabular_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_QUOTECHAR = '"'

#: Hand-built sources covering the dialect shapes a real export breaks on, and
#: the degenerate ones a scorer can quietly divide by zero on. Each is a
#: ``(name, text)`` pair; the name is the assertion message, so a regression
#: names the shape it broke rather than an index.
_EDGE_CASES: tuple[tuple[str, str], ...] = (
    ("empty", ""),
    ("all-blank", "\n\n\n"),
    ("blank-with-whitespace", "   \n\t\n \n"),
    ("prose-no-rectangle", "just one line of prose\nand another\n"),
    ("single-column", "solo\nuna\ncolumna\n"),
    ("header-only", "Fecha;Concepto;Importe\n"),
    ("header-only-no-newline", "Fecha;Concepto;Importe"),
    (
        "semicolon-comma-tie",
        "Fecha;Concepto,Importe\n01/02/2026;Compra,-10\n02/02/2026;Venta,20\n",
    ),
    (
        "comma-outscores-semicolon",
        "a,b,c,d\n1,2,3,4\n5,6,7,8\nx;y\n",
    ),
    (
        "ragged-rows",
        "Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n02/02/2026;Corta\n03/02/2026;A;B;C\n",
    ),
    (
        "quoted-delimiter-inside-field",
        'Fecha;Concepto;Importe\n01/02/2026;"Compra; con punto y coma";-10,00\n',
    ),
    (
        "embedded-newline-in-quoted-field",
        'Fecha;Concepto;Importe\n01/02/2026;"Comida de trabajo\ncon cliente Berrocal";-10,00\n02/02/2026;Otra;-1,00\n',
    ),
    (
        "crlf",
        "Fecha;Concepto;Importe\r\n01/02/2026;Compra;-10,00\r\n02/02/2026;Venta;20,00\r\n",
    ),
    (
        "bom-prefixed-text",
        "﻿Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n",
    ),
    (
        "trailing-delimiter-empty-last-field",
        "Fecha;Concepto;Importe;\n01/02/2026;Compra;-10,00;\n02/02/2026;Venta;20,00;\n",
    ),
    (
        "preamble-and-summary",
        "Banco Peninsular, S.A.\nTitular;NORDESTE ESTUDIO CREATIVO SL\nIBAN;ES9121000418450200051332\n"
        "\nFecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n02/02/2026;Venta;20,00\nTOTAL;;10,00\n",
    ),
    ("tab-delimited", "Fecha\tConcepto\tImporte\n01/02/2026\tCompra\t-10,00\n02/02/2026\tVenta\t20,00\n"),
    ("pipe-delimited", "Fecha|Concepto|Importe\n01/02/2026|Compra|-10,00\n02/02/2026|Venta|20,00\n"),
    (
        "minority-width-is-not-the-rectangle",
        "a;b;c;d;e\n1;2;3\n4;5;6\n7;8;9\n10;11;12\n",
    ),
    (
        "blank-rows-interleaved",
        "Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n\n\n02/02/2026;Venta;20,00\n",
    ),
    # The one shape where the header walk's blank-row skipping decides the
    # answer rather than merely the score: judged against the literal next row
    # this header is followed by nothing data-like and loses to the first
    # movement row, moving the header a line down and eating a movement.
    (
        "blank-row-directly-below-the-header",
        "Fecha;Concepto;Importe\n\n01/02/2026;Compra;-10,00\n02/02/2026;Venta;20,00\n",
    ),
    (
        "header-below-the-search-limit",
        "".join(f"nota {index}\n" for index in range(25)) + "Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n",
    ),
)


def _fixture_sources() -> tuple[tuple[str, str], ...]:
    """Every delimited fixture bundled with the project, decoded permissively.

    Read as ``utf-8-sig`` with replacement rather than through the codec chain:
    the equivalence under test is about scoring already-decoded text, so a
    fixture's encoding must not be able to skip it out of the corpus.
    """
    root: Path = FIXTURES_DIR / "financial"
    sources: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
            continue
        sources.append((path.name, path.read_bytes().decode("utf-8-sig", errors="replace")))
    return tuple(sources)


def _corpus() -> tuple[tuple[str, str], ...]:
    return _fixture_sources() + _EDGE_CASES


def _eager_score(text: str, delimiter: str) -> tuple[int, int]:
    """Score a delimiter the eager way: materialize the parse, then histogram it."""
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar=_QUOTECHAR)
    parsed = [list(row) for row in reader]
    widths = Counter(len(cells) for cells in parsed if any(cell.strip() for cell in cells))
    return _rectangle_score(widths)


def _eager_best_delimiter(text: str) -> tuple[int, int, str] | None:
    """Choose a delimiter the eager way, holding every candidate's full parse."""
    best: tuple[int, int, str] | None = None
    for delimiter in CANDIDATE_DELIMITERS:
        score, width = _eager_score(text, delimiter)
        if score == 0:
            continue
        if best is None or score > best[0]:
            best = (score, width, delimiter)
    return best


def _tail_copying_locate_header(
    parsed: list[tuple[int, list[str]]],
    *,
    column_count: int,
) -> int | None:
    """Locate the header the tail-copying way, slicing the remainder per candidate."""
    best_index: int | None = None
    best_score = 0
    for index, (_, cells) in enumerate(parsed[:_HEADER_SEARCH_LIMIT]):
        if len(cells) != column_count:
            continue
        next_row = next((row for _, row in parsed[index + 1 :] if any(cell.strip() for cell in row)), None)
        score = _header_score(cells, next_row=next_row)
        if best_index is None or score > best_score:
            best_index = index
            best_score = score
    return best_index


def _decimal_separator_or_none(text: str) -> str | None:
    """Return the convention ``text`` normalizes under, or ``None`` when it is refused."""
    try:
        return normalize_tabular_text(text, encoding="utf-8").dialect.decimal_separator
    except TabularSourceError:
        return None


def test_corpus_covers_every_candidate_delimiter_and_both_decimal_conventions() -> None:
    """Anti-vacuity: an equivalence corpus that exercises one dialect proves one dialect.

    Every test below is a comparison over :func:`_corpus`, so a corpus that had
    silently shrunk — a fixture directory moved, an edge case dropped — would
    keep passing while testing far less. This pins the corpus's reach instead.
    """
    corpus = _corpus()
    assert len(corpus) >= 30, len(corpus)
    winners = {best[2] for _, text in corpus if (best := _best_delimiter(text, _QUOTECHAR)) is not None}
    assert winners == set(CANDIDATE_DELIMITERS), sorted(winners)
    refused = [name for name, text in corpus if _best_delimiter(text, _QUOTECHAR) is None]
    assert refused, "no corpus entry exercises the no-rectangle refusal"
    separators = {digest for _, text in corpus if (digest := _decimal_separator_or_none(text)) is not None}
    assert separators == {",", "."}, sorted(separators)


@pytest.mark.parametrize("delimiter", CANDIDATE_DELIMITERS, ids=("semicolon", "comma", "tab", "pipe"))
def test_streamed_score_matches_a_materialised_parse(delimiter: str) -> None:
    """Streaming the width histogram must score exactly what materializing it did.

    This is the whole safety claim of the lazy scorer: the rows counted are the
    same rows, so the ``(score, column_count)`` pair — and therefore the
    delimiter it elects — cannot move. A sampled scorer would fail here on the
    preamble-bearing and summary-bearing entries.
    """
    for name, text in _corpus():
        assert _score_delimiter(text, delimiter, _QUOTECHAR) == _eager_score(text, delimiter), name


def test_winning_delimiter_matches_an_eager_selector() -> None:
    """The elected delimiter, its score and its column count must all be unchanged.

    Asserting the whole triple rather than the delimiter alone catches a
    tie-break that lands on the right separator for the wrong reason, which
    would move the rectangle's width and cut the columns differently.
    """
    for name, text in _corpus():
        assert _best_delimiter(text, _QUOTECHAR) == _eager_best_delimiter(text), name


def test_header_location_matches_a_tail_copying_selector() -> None:
    """The lazy header walk must stop on the row the tail-copying walk stopped on."""
    for name, text in _corpus():
        best = _best_delimiter(text, _QUOTECHAR)
        if best is None:
            continue
        _, column_count, delimiter = best
        parsed = _parse_with(text, delimiter, _QUOTECHAR)
        expected = _tail_copying_locate_header(parsed, column_count=column_count)
        assert _locate_header(parsed, column_count=column_count) == expected, name


def test_physical_line_numbers_survive_the_winning_parse() -> None:
    """A row's reported line must still be the physical line it started on.

    Line numbers are what an operator is given to find the row a notice is
    about, and a rewrite that reparses only the winner is exactly where the
    ``reader.line_num`` bookkeeping goes missing. The embedded-newline entry is
    the one that would expose it: its second data row starts two physical lines
    after the row before it.
    """
    text = dict(_EDGE_CASES)["embedded-newline-in-quoted-field"]
    table = normalize_tabular_text(text, encoding="utf-8")
    assert table.dialect.header_line_number == 1
    assert [row.source_line_number for row in table.rows] == [2, 4]
    assert "\n" in table.rows[0].cells[1]


#: ``sha256`` of each edge case's normalized table, recorded from the eager
#: implementation before delimiter scoring and header location were made lazy.
#: The digest covers the whole :class:`~core.NormalizedTable` — dialect, header
#: cells, every row verbatim, preamble, summary rows and notices — so any
#: divergence in what the file parses to, not merely in which delimiter won,
#: reds this. ``None`` records that the source is refused outright.
_RECORDED_NORMALIZATION_DIGESTS: dict[str, str | None] = {
    "empty": None,
    "all-blank": None,
    "blank-with-whitespace": None,
    "prose-no-rectangle": None,
    "single-column": None,
    "header-only": "739414d13ca1d4cb411ca73fa1c091be7a7fdbabee85bde6272ebb3bf1111840",
    "header-only-no-newline": "739414d13ca1d4cb411ca73fa1c091be7a7fdbabee85bde6272ebb3bf1111840",
    "semicolon-comma-tie": "17a9e8b0715fbd59e98e70c5f1461c8be489ab4b7aebd2151511decc92460280",
    "comma-outscores-semicolon": "a8864a0b877718cfead57d4216a8bd4c1471ade7d2dfa21b2930e0e88f4c6cee",
    "ragged-rows": "204c2be57a4ffb7c034ae62f0a2a10b2a4e3b9f7f58596c09dec1ed0f144d287",
    "quoted-delimiter-inside-field": "c24583392558a4c17d726a760b02cd5a718a6c2ea584a3130ffcfa03620031f8",
    "embedded-newline-in-quoted-field": "2e65f107434320809a2e3accbbe2222f7c85e9b8d3f568bd3d053abdcbaddbab",
    "crlf": "b03e062917ed2ff95fb3dca0a129f44cf1a2a9f23f5062a27b7437ff0cfe08d8",
    "bom-prefixed-text": "d7c72643188840fb54a02ee12b0d95c87c478766d78cb17926e82c22e23ad895",
    "trailing-delimiter-empty-last-field": "8fddffd92338f3f3b99e67fde6f93fa386857a7029d8f0dd305db9da33041323",
    "preamble-and-summary": "dea9a81d6f22f66a702580d303253bf1033f3981decacee3455da80c3216d9ab",
    "tab-delimited": "a9759da9935391701dbf23360204d3e4cc9176307020c5d3d260ba4710650d58",
    "pipe-delimited": "ba2ea2c453161a69dde005e2353af7e019a068231488e56fe482ca86e2a99d17",
    "minority-width-is-not-the-rectangle": "3e4dd2ea17773a47a17ed6a657afe7aa9ae0789d4da48aa388458841a1e4e42e",
    "blank-rows-interleaved": "a6a19c2ba67e77c062a334c28e31f62efdd075860465a21dc7c44f85e5f963bb",
    "blank-row-directly-below-the-header": "3320d35b3ed9267c99e2b4ce59962c026ecc1b36f8cd9375c284a2a2c49d1ab0",
    "header-below-the-search-limit": None,
}


def _normalization_digest(text: str) -> str | None:
    """Return the digest of ``text``'s normalized table, or ``None`` when refused."""
    try:
        table = normalize_tabular_text(text, encoding="utf-8")
    except TabularSourceError:
        return None
    return hashlib.sha256(table.model_dump_json().encode("utf-8")).hexdigest()


def test_recorded_edge_case_normalizations_are_unchanged() -> None:
    """Each edge case must still normalize to the byte-identical table it did before.

    The oracle comparisons above prove the two changed helpers agree with their
    eager forms; this closes the loop end to end, pinning the full typed output
    rather than the helpers' return values. The digests are a characterization
    record of the pre-change behaviour: a red here means the parse moved, and
    the correct response is to explain the move, never to re-record the digest.
    """
    assert set(_RECORDED_NORMALIZATION_DIGESTS) == {name for name, _ in _EDGE_CASES}
    for name, text in _EDGE_CASES:
        assert _normalization_digest(text) == _RECORDED_NORMALIZATION_DIGESTS[name], name
