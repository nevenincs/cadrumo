"""Pinned retrieval golden set over the REAL command surface.

Locks the ranking regressions the 2026-07-08 MCP console review found (audit
finding ``command-search-lexical-only-mis-ranks``): a cold agent searching
"import a bank statement" got the homonym
``modelo.review_package.import_feedback`` ranked ABOVE the correct
``ledger.import`` on the shared token "import", and the composite ``quickfile``
was invisible to outcome-phrased queries like "file my quarterly VAT". Both are
asserted here against the live descriptor set (``build_tool_descriptors()``), so
the retriever's ranking is a pinned contract, not a claim.

Per-column BM25 weighting plus the ``quickfile`` outcome aliases carry both
headline assertions on their own, which is what makes the shipped lexical-only
index sufficient. The module is deterministic and network-free on every host
because the index has no optional half to switch on: the shipped product loads
no embedding model at all, a boundary
``test_search_shippability.py::test_shipped_search_surface_imports_no_embedding_runtime``
pins by name.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.application.command_search.index import CommandIndex

# The ranking helpers live on this package's own ``_meta_tools`` module (they wrap
# the ``search`` meta-tool, not a public facade); the reach is intra-package.
from .._meta_tools import build_command_search_index, search_commands
from .._tools import McpToolDescriptor, build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(scope="module")
def _descriptors_and_index() -> tuple[tuple[McpToolDescriptor, ...], CommandIndex]:
    """Build the live descriptor set and its command index once."""
    descriptors = build_tool_descriptors()
    index = build_command_search_index(descriptors)
    return descriptors, index


@pytest.fixture(scope="module")
def ranker(_descriptors_and_index: tuple[tuple[McpToolDescriptor, ...], CommandIndex]) -> Callable[[str], list[str]]:
    """Rank against the module-scoped descriptor set and index."""
    descriptors, index = _descriptors_and_index

    def rank(query: str, *, limit: int = 8) -> list[str]:
        return [hit.command_key for hit in search_commands(query, descriptors=descriptors, index=index, limit=limit)]

    return rank


def test_import_a_bank_statement_ranks_ledger_import_first(ranker: Callable[[str], list[str]]) -> None:
    ranked = ranker("import a bank statement")
    assert ranked, "the query matched no commands"
    assert ranked[0] == "ledger.import", f"expected ledger.import first, got {ranked[:5]}"
    # The exact review regression: the homonym import_feedback must NOT be first.
    assert ranked[0] != "modelo.review_package.import_feedback"


def test_file_my_quarterly_iva_surfaces_quickfile_in_the_top_hits(ranker: Callable[[str], list[str]]) -> None:
    ranked = ranker("file my quarterly VAT")
    assert ranked, "the query matched no commands"
    assert "app.quickfile" in ranked[:5], f"expected app.quickfile in the top 5, got {ranked[:5]}"


def test_outcome_phrasing_reaches_the_composite_quickfile_chain(ranker: Callable[[str], list[str]]) -> None:
    # A second outcome-phrased homonym the lexical-only index missed: the literal
    # verb tokens of "do my taxes" appear in no command, yet the aliases route it
    # to the one-command filing chain.
    ranked = ranker("do my taxes")
    assert "app.quickfile" in ranked[:5], f"expected app.quickfile in the top 5, got {ranked[:5]}"


def test_no_retired_command_key_remains_searchable() -> None:
    """A retired verb must not survive in the surface an agent searches.

    Ranking correctness is not the only way this surface misleads. A command
    door removed from the CLI but left in the descriptor set stays discoverable:
    an agent searching by outcome finds it, is told it exists, and invokes
    something the tree no longer mounts. The ranking assertions above cannot
    catch that, because a retired key ranks perfectly well.

    The retired set is the hard-cutover list -- the duplicate and misleading
    doors removed in favour of a single spelling. Each is checked as an exact
    key and as a trailing segment, so a re-introduction under a different parent
    is caught too.
    """
    keys = {descriptor.command_key for descriptor in build_tool_descriptors()}
    # Anti-vacuity floor. Asserting the retired keys are ABSENT passes trivially
    # when the descriptor set is empty OR merely truncated: a handful of
    # descriptors makes every retired key absent while proving nothing. The live
    # surface carries ~292 command keys, so pin a plausible floor well below that
    # and far above a collapsed lazy walk, catching a truncated set that a bare
    # non-empty check would let slip through unnoticed.
    assert len(keys) >= 200, (
        f"descriptor set resolved only {len(keys)} keys, so this gate would pass while checking nothing"
    )

    retired = {
        "config.lock": "retired custody lock door",
        "config.rekey": "retired key-rotation door",
        "config.show_recovery": "retired recovery-status door",
        "config.verify_recovery": "retired recovery-verification door",
        "config.auth.clear": "broad ambiguous door, removed in favour of auth logout/reset",
        "config.profile.sandbox.use": "removed in favour of selecting a sandbox by canonical label",
        "modelo.audit.replay": "removed; audit check is the retained verb",
    }

    resurrected = sorted(key for key in retired if key in keys)
    assert not resurrected, (
        f"retired command keys are searchable again: {resurrected}. Each was removed as a duplicate or "
        "misleading door; re-registering one hands an agent a command the CLI does not mount"
    )

    # `config.auth.apoderado.clear` is a real, retained command whose leaf token
    # collides with the retired `auth clear`, so the suffix sweep matches on the
    # full retired path rather than the bare leaf.
    suffix_hits = sorted(
        key for key in keys for retired_key in retired if key != retired_key and key.endswith("." + retired_key)
    )
    assert not suffix_hits, f"retired command paths re-registered under a new parent: {suffix_hits}"
