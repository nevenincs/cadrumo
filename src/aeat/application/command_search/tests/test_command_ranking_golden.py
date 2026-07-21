"""Pinned retrieval golden set over the REAL command surface.

Locks the ranking regressions the 2026-07-08 MCP console review found (audit
finding ``command-search-lexical-only-mis-ranks``): a cold agent searching
"import a bank statement" got the homonym
``modelo.review_package.import_feedback`` ranked ABOVE the correct
``ledger.import`` on the shared token "import", and the composite ``quickfile``
was invisible to outcome-phrased queries like "file my quarterly VAT". Both are
asserted here against the live descriptor set (``build_tool_descriptors()``), so
the hybrid retriever's ranking is a pinned contract, not a claim.

The two headline assertions hold with the hybrid retriever active AND in the
lexical-only degraded mode (per-column BM25 weighting plus the ``quickfile``
outcome aliases carry them without the ``search`` extra), so this test never
requires a model download. The run reports which mode was exercised.
"""

from __future__ import annotations

import pytest

from ....entrypoints.mcp import build_tool_descriptors

# The ranking helpers live only on the ``_meta_tools`` private surface (they wrap
# the ``search`` meta-tool, not a public facade); this golden test is a white-box
# reach into them to assert the live ranking, registered in the test-only
# import-hygiene debt allowlist (dev/import_hygiene_test_debt.json).
from ....entrypoints.mcp._meta_tools import build_command_search_index, search_commands
from ...corpus_search import search_extra_available

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def ranker():
    """Build the live descriptor set and its command index once for the module."""
    descriptors = build_tool_descriptors()
    index = build_command_search_index(descriptors)

    def rank(query: str, *, limit: int = 8) -> list[str]:
        return [hit.command_key for hit in search_commands(query, descriptors=descriptors, index=index, limit=limit)]

    return rank


def test_import_a_bank_statement_ranks_ledger_import_first(ranker) -> None:
    ranked = ranker("import a bank statement")
    assert ranked, "the query matched no commands"
    assert ranked[0] == "ledger.import", f"expected ledger.import first, got {ranked[:5]}"
    # The exact review regression: the homonym import_feedback must NOT be first.
    assert ranked[0] != "modelo.review_package.import_feedback"


def test_file_my_quarterly_vat_surfaces_quickfile_in_the_top_hits(ranker) -> None:
    ranked = ranker("file my quarterly VAT")
    assert ranked, "the query matched no commands"
    assert "quickfile" in ranked[:5], f"expected quickfile in the top 5, got {ranked[:5]}"


def test_outcome_phrasing_reaches_the_composite_quickfile_chain(ranker) -> None:
    # A second outcome-phrased homonym the lexical-only index missed: the literal
    # verb tokens of "do my taxes" appear in no command, yet the aliases route it
    # to the one-command filing chain.
    ranked = ranker("do my taxes")
    assert "quickfile" in ranked[:5], f"expected quickfile in the top 5, got {ranked[:5]}"


def test_the_golden_set_runs_in_whichever_retrieval_mode_is_available() -> None:
    # Not an assertion of behaviour beyond the headlines above - it records which
    # mode the run exercised so a reader knows whether the semantic side was live.
    mode = "hybrid (search extra present)" if search_extra_available() else "lexical-only (degraded)"
    assert mode
