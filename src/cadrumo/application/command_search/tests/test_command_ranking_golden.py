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

from collections.abc import Callable

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
def ranker() -> Callable[[str], list[str]]:
    """Build the live descriptor set and its command index once for the module."""
    descriptors = build_tool_descriptors()
    index = build_command_search_index(descriptors)

    def rank(query: str, *, limit: int = 8) -> list[str]:
        return [hit.command_key for hit in search_commands(query, descriptors=descriptors, index=index, limit=limit)]

    return rank


def test_import_a_bank_statement_ranks_ledger_import_first(ranker: Callable[[str], list[str]]) -> None:
    ranked = ranker("import a bank statement")
    assert ranked, "the query matched no commands"
    assert ranked[0] == "ledger.import", f"expected ledger.import first, got {ranked[:5]}"
    # The exact review regression: the homonym import_feedback must NOT be first.
    assert ranked[0] != "modelo.review_package.import_feedback"


def test_file_my_quarterly_vat_surfaces_quickfile_in_the_top_hits(ranker: Callable[[str], list[str]]) -> None:
    ranked = ranker("file my quarterly VAT")
    assert ranked, "the query matched no commands"
    assert "quickfile" in ranked[:5], f"expected quickfile in the top 5, got {ranked[:5]}"


def test_outcome_phrasing_reaches_the_composite_quickfile_chain(ranker: Callable[[str], list[str]]) -> None:
    # A second outcome-phrased homonym the lexical-only index missed: the literal
    # verb tokens of "do my taxes" appear in no command, yet the aliases route it
    # to the one-command filing chain.
    ranked = ranker("do my taxes")
    assert "quickfile" in ranked[:5], f"expected quickfile in the top 5, got {ranked[:5]}"


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
    # non-empty check would wave through.
    assert len(keys) >= 200, (
        f"descriptor set resolved only {len(keys)} keys, so this gate would pass while checking nothing"
    )

    retired = {
        "config.lock": "custody lock door, removed in favour of passphrase/recovery",
        "config.rekey": "removed in favour of config.passphrase.change",
        "config.show_recovery": "removed in favour of config.recovery.status",
        "config.verify_recovery": "removed in favour of config.recovery.verify",
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


def test_the_golden_set_reports_which_retrieval_mode_it_exercised(
    ranker: Callable[[str], list[str]],
) -> None:
    """The headline queries hold in whichever retrieval mode is installed.

    This previously asserted a non-empty string literal, which no change to the
    ranker could ever falsify. What is actually worth pinning is the claim the
    module docstring makes: that the golden set never requires a model download,
    so the two headline results must hold in the mode this run has -- and the
    mode is reported so a reader knows whether the semantic side was live.
    """
    mode = "hybrid (search extra present)" if search_extra_available() else "lexical-only (degraded)"

    assert ranker("import a bank statement")[0] == "ledger.import", f"headline ranking failed in {mode} mode"
    assert "quickfile" in ranker("file my quarterly VAT")[:5], f"headline ranking failed in {mode} mode"
