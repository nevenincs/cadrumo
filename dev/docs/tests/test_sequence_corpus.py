"""Whole-corpus sequence proofs run outside every outer pytest worker pool.

The existing verification harness owns this module. Its bounded child pools
use the standalone lane budget; ordinary docs tests keep their small fixtures
and mutation controls in the parallel population.
"""

from __future__ import annotations

import pytest

from dev.ci.sequence_goldens_gate import DEFAULT_JOBS, check_committed_goldens

from ..sequences.checks import check_page_coherence_in_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


class TestCommittedGoldensCleanGate:
    """The pytest and CLI surfaces share the committed corpus's cached verdict."""

    def test_every_committed_golden_matches_live_execution(self) -> None:
        """Every enrolled sequence matches its golden under identical proven inputs."""
        problems = check_committed_goldens(jobs=DEFAULT_JOBS)
        assert problems == (), "cli-sequence goldens diverge from live execution:\n" + "\n".join(problems)


class TestPageCoherenceGate:
    """Each committed page's sequences must hold in cumulative narrative order."""

    def test_every_enrolled_page_is_coherent_top_to_bottom(self) -> None:
        """Pages shard across the standalone pool with one fresh sandbox per page."""
        problems = check_page_coherence_in_subprocess(jobs=DEFAULT_JOBS)
        assert problems == (), "enrolled pages are not coherent under cumulative execution:\n" + "\n".join(problems)
