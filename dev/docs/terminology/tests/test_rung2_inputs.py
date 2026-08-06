"""Real-behaviour tests for the Rung-2 authority/input boundary."""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OutputLanguage
from dev.docs.terminology._miss_rate import load_committed_relevance
from dev.docs.terminology._rung2_inputs import (
    Rung2InputError,
    _require_current_handbook_vocabulary,
)
from dev.docs.terminology._rung2_query_authority import (
    QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION,
    Rung2QueryAliasEntry,
    load_query_alias_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_committed_relevance_matches_the_combined_current_authority() -> None:
    """The committed sweep is checked against the Handbook-plus-alias union."""
    authority = load_query_alias_authority()
    relevance = load_committed_relevance()

    _require_current_handbook_vocabulary(relevance, authority)

    assert authority.schema_version == QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION
    assert relevance.query_count == len(relevance.mappings)


def test_unmapped_ratified_alias_fails_closed_before_compilation() -> None:
    """An admitted alias cannot silently widen inputs without its own mapping."""
    authority = load_query_alias_authority()
    alias = Rung2QueryAliasEntry(
        concept_id="prorrata",
        language=OutputLanguage.ES,
        query="reparto proporcional",
        canonical_query="prorrata",
        status="ratified",
        review_reason="RAG-grounded project wording reviewed for the closed vocabulary.",
        reviewed_at="2026-08-06",
    )
    expanded = authority.model_copy(update={"entries": (alias,)})

    with pytest.raises(Rung2InputError, match="missing"):
        _require_current_handbook_vocabulary(load_committed_relevance(), expanded)
