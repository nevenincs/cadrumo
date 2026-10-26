"""The command index bridges vocabulary a token-overlap scorer cannot.

Proves the FTS5 discovery spine: the index
recalls a command through Spanish stemming and diacritics folding where an exact
token-overlap match misses it; per-column BM25 weighting ranks a key-tier hit
above the same token buried in the help tier; and the degraded (no-FTS5) mode
still ranks by term overlap so a minimal install keeps a working ``search``. Uses
a small synthetic corpus so the properties are deterministic. The index has one
shape on every install - it loads no model and reaches no network - so nothing
here needs an environment-dependent seam.
"""

from __future__ import annotations

import pytest

from ....core.spanish_stemming import spanish_word_tokens
from ..index import CommandDoc, CommandIndex, build_command_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DOCS = (
    CommandDoc(
        command_key="modelo.work.calculate",
        tool_name="aeat_modelo_work_calculate",
        key_and_name="modelo.work.calculate modelo work calculate aeat_modelo_work_calculate",
        description="Run `aeat app modelo work calculate`.",
        help="calcula la autoliquidación de IVA y las declaraciones trimestrales",
    ),
    CommandDoc(
        command_key="ledger.add",
        tool_name="aeat_ledger_add",
        key_and_name="ledger.add ledger add aeat_ledger_add",
        description="Run `aeat app ledger add`.",
        help="registra una transacción bancaria en el libro",
    ),
    CommandDoc(
        command_key="modelo.export",
        tool_name="aeat_modelo_export",
        key_and_name="modelo.export modelo export aeat_modelo_export",
        description="Run `aeat app modelo export`.",
        help="genera el fichero para presentar la declaración",
    ),
)


def _index(docs: tuple[CommandDoc, ...] = _DOCS) -> CommandIndex:
    """Build the index over a fixture corpus."""
    return build_command_index(docs)


def _token_overlap_only(docs: tuple[CommandDoc, ...], query: str) -> set[str]:
    """The keys a naive exact-token-overlap scorer would match (no stemming)."""
    wanted = set(spanish_word_tokens(query))
    return {doc.command_key for doc in docs if wanted & set(spanish_word_tokens(doc.combined_text))}


def test_stemmed_recall_reaches_a_command_exact_overlap_misses() -> None:
    index = _index()
    # FTS5 is a bundled capability of the sqlite3 every supported platform ships;
    # the stemming property lives only in the FTS5 path, so require it here (a hard
    # precondition, never a silent skip) — the degraded path is proven separately.
    assert index._connection is not None

    # "declaración" (singular, accented) vs the corpus token "declaraciones"
    # (plural): exact overlap misses it, the Spanish-stemmed column recalls it.
    query = "declaración trimestral"
    assert "modelo.work.calculate" not in _token_overlap_only(_DOCS, query)
    hits = index.search(query, limit=5)
    assert "modelo.work.calculate" in {hit.command_key for hit in hits}


def test_diacritics_fold_so_an_unaccented_query_matches_accented_text() -> None:
    index = _index()
    # Diacritics folding is an FTS5-path property; FTS5 is always present on the
    # supported sqlite3, so require it rather than skip.
    assert index._connection is not None
    hits = index.search("transaccion bancaria", limit=5)
    assert "ledger.add" in {hit.command_key for hit in hits}


def test_ranks_the_named_command_first_for_a_direct_query() -> None:
    index = _index()
    hits = index.search("calculate autoliquidacion IVA", limit=5)
    assert hits
    assert hits[0].command_key == "modelo.work.calculate"


def test_key_tier_outranks_the_same_token_in_the_help_tier() -> None:
    # Per-column BM25 weighting: a shared token that lands in a
    # command's KEY tier must outrank the same token buried in another command's
    # HELP tier, so a homonym in a low-value column no longer wins.
    docs = (
        CommandDoc(
            command_key="widget.run",
            tool_name="aeat_widget_run",
            key_and_name="widget.run widget run aeat_widget_run",
            description="Run `aeat app widget run`.",
            help="ejecuta la operación principal",
        ),
        CommandDoc(
            command_key="other.thing",
            tool_name="aeat_other_thing",
            key_and_name="other.thing other thing aeat_other_thing",
            description="Run `aeat app other thing`.",
            help="menciona un widget de pasada en la ayuda",
        ),
    )
    index = _index(docs)
    # Per-column BM25 weighting is an FTS5-path property; FTS5 is always present,
    # so require it rather than skip.
    assert index._connection is not None
    hits = index.search("widget", limit=5)
    assert hits
    assert hits[0].command_key == "widget.run"


def test_blank_or_termless_query_returns_no_hits() -> None:
    index = _index()
    assert index.search("", limit=5) == ()
    assert index.search("   ", limit=5) == ()
    assert index.search("calculate", limit=0) == ()


def test_degraded_mode_ranks_by_term_overlap_without_fts5() -> None:
    # Force the degraded path by constructing an index whose FTS5 connection is
    # cleared, proving the pure-Python fallback still ranks and never raises.
    index = _index()
    index._connection = None
    hits = index.search("ledger transaccion", limit=5)
    assert hits
    assert hits[0].command_key == "ledger.add"
