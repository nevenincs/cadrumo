"""The command index bridges vocabulary a token-overlap scorer cannot.

Proves the ADR ``mcp-progressive-discovery`` P2 discovery spine: the FTS5 index
recalls a command through Spanish stemming and diacritics folding where an exact
token-overlap match misses it, and the degraded (no-FTS5) mode still ranks by
term overlap so a minimal install keeps a working ``search``. Uses a small
synthetic corpus so the cross-vocabulary property is deterministic.
"""

from __future__ import annotations

import re

import pytest

from .._index import CommandDoc, CommandIndex, build_command_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORD_RE = re.compile(r"\w+", re.UNICODE)

_DOCS = (
    CommandDoc(
        command_key="modelo.work.calculate",
        tool_name="aeat_modelo_work_calculate",
        text="modelo work calculate calcula la autoliquidación de IVA y las declaraciones trimestrales",
    ),
    CommandDoc(
        command_key="ledger.add",
        tool_name="aeat_ledger_add",
        text="ledger add registra una transacción bancaria en el libro",
    ),
    CommandDoc(
        command_key="modelo.export",
        tool_name="aeat_modelo_export",
        text="modelo export genera el fichero para presentar la declaración",
    ),
)


def _token_overlap_only(docs: tuple[CommandDoc, ...], query: str) -> set[str]:
    """The keys a naive exact-token-overlap scorer would match (no stemming)."""
    wanted = set(_WORD_RE.findall(query.lower()))
    return {doc.command_key for doc in docs if wanted & set(_WORD_RE.findall(doc.text.lower()))}


def test_stemmed_recall_reaches_a_command_exact_overlap_misses() -> None:
    index = build_command_index(_DOCS)
    if index._connection is None:  # noqa: SLF001 - degraded env has no stemming to prove
        pytest.skip("FTS5 unavailable; stemming recall is exercised only in the FTS5 path")

    # "declaración" (singular, accented) vs the corpus token "declaraciones"
    # (plural): exact overlap misses it, the Spanish-stemmed column recalls it.
    query = "declaración trimestral"
    assert "modelo.work.calculate" not in _token_overlap_only(_DOCS, query)
    hits = index.search(query, limit=5)
    assert "modelo.work.calculate" in {hit.command_key for hit in hits}


def test_diacritics_fold_so_an_unaccented_query_matches_accented_text() -> None:
    index = build_command_index(_DOCS)
    if index._connection is None:  # noqa: SLF001
        pytest.skip("FTS5 unavailable; folding is exercised only in the FTS5 path")
    hits = index.search("transaccion bancaria", limit=5)
    assert "ledger.add" in {hit.command_key for hit in hits}


def test_ranks_the_named_command_first_for_a_direct_query() -> None:
    index = build_command_index(_DOCS)
    hits = index.search("calculate autoliquidacion IVA", limit=5)
    assert hits
    assert hits[0].command_key == "modelo.work.calculate"


def test_blank_or_termless_query_returns_no_hits() -> None:
    index = build_command_index(_DOCS)
    assert index.search("", limit=5) == ()
    assert index.search("   ", limit=5) == ()
    assert index.search("calculate", limit=0) == ()


def test_degraded_mode_ranks_by_term_overlap_without_fts5() -> None:
    # Force the degraded path by constructing an index whose FTS5 connection is
    # cleared, proving the pure-Python fallback still ranks and never raises.
    index = CommandIndex(_DOCS)
    index._connection = None  # noqa: SLF001 - simulate the no-FTS5 minimal install
    hits = index.search("ledger transaccion", limit=5)
    assert hits
    assert hits[0].command_key == "ledger.add"
