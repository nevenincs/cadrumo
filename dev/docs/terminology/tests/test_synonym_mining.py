"""Real-behaviour gates for synonym mining and ratification."""

from __future__ import annotations

from datetime import date

import pytest
from typer.testing import CliRunner

from cadrumo.core.external_constants import OutputLanguage

from ...terminology_handbook.loader import load_terminology_handbook
from .._sweep import enumerate_query_vocabulary
from .._synonym_cli import app
from .._synonym_mining import (
    RatificationAction,
    RatificationStatus,
    SynonymCandidateEntry,
    SynonymCandidateObservation,
    SynonymRatificationQueue,
    load_synonym_ratification_queue,
    mine_synonym_candidates,
    validate_ratification_queue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_mining_uses_relative_cosine_and_skips_existing_vocabulary() -> None:
    observations = (
        SynonymCandidateObservation(
            concept_id="prorrata",
            source_term="pro rata",
            candidate="pro-rata",
            language=OutputLanguage.EN,
            action=RatificationAction.ADMITTED_TERM,
            cosine=0.88,
            nearest_competing_cosine=0.72,
            competing_concept_id="prorrata-especial",
        ),
        SynonymCandidateObservation(
            concept_id="prorrata",
            source_term="prorrata",
            candidate="prorrata",
            language=OutputLanguage.ES,
            action=RatificationAction.ADMITTED_TERM,
            cosine=0.99,
            nearest_competing_cosine=0.70,
            competing_concept_id="prorrata-especial",
        ),
        SynonymCandidateObservation(
            concept_id="prorrata",
            source_term="regla de prorrata",
            candidate="deducible",
            language=OutputLanguage.ES,
            action=RatificationAction.ADMITTED_TERM,
            cosine=0.80,
            nearest_competing_cosine=0.78,
            competing_concept_id="iva",
        ),
    )

    queue = mine_synonym_candidates(observations)

    assert [entry.candidate for entry in queue.entries] == ["pro-rata"]
    assert queue.entries[0].status is RatificationStatus.PROPOSED


def test_committed_synonym_ratification_queue_is_clean() -> None:
    queue = load_synonym_ratification_queue()
    result = validate_ratification_queue(queue)

    assert result.passed
    assert any(entry.status is RatificationStatus.RATIFIED for entry in queue.entries)
    assert any(entry.status is RatificationStatus.PROPOSED for entry in queue.entries)
    assert any(entry.status is RatificationStatus.REJECTED for entry in queue.entries)


def test_unratified_candidates_are_absent_from_shipped_query_vocabulary() -> None:
    queue = load_synonym_ratification_queue()
    shipped = {(query.concept_id, query.query.casefold()) for query in enumerate_query_vocabulary()}

    unratified = [entry for entry in queue.entries if entry.status is not RatificationStatus.RATIFIED]
    assert unratified, (
        "the queue holds no unratified candidate, so the exclusion below would be "
        "asserted zero times and this test would report clean having checked nothing"
    )

    for entry in unratified:
        assert (entry.concept_id, entry.candidate.casefold()) not in shipped


def test_ratified_candidate_must_land_in_handbook() -> None:
    queue = SynonymRatificationQueue(
        generated_by="test",
        entries=(
            SynonymCandidateEntry(
                concept_id="prorrata",
                source_term="pro rata",
                candidate="pro-rata",
                language=OutputLanguage.EN,
                action=RatificationAction.ADMITTED_TERM,
                cosine=0.88,
                nearest_competing_cosine=0.72,
                competing_concept_id="prorrata-especial",
                status=RatificationStatus.RATIFIED,
                review_reason="Reviewer accepted this candidate for the test queue.",
                reviewed_at=date(2026, 6, 10),
            ),
        ),
    )

    result = validate_ratification_queue(queue, handbook=load_terminology_handbook())

    assert not result.passed
    reasons = {violation.reason for violation in result.violations}
    assert "ratified admitted_term has not landed in the Handbook" in reasons
    assert "ratified candidate is absent from the shipped query vocabulary" in reasons


def test_unratified_candidate_reaching_vocabulary_is_rejected() -> None:
    queue = SynonymRatificationQueue(
        generated_by="test",
        entries=(
            SynonymCandidateEntry(
                concept_id="prorrata",
                source_term="regla de prorrata",
                candidate="prorrateo",
                language=OutputLanguage.ES,
                action=RatificationAction.ADMITTED_TERM,
                cosine=0.91,
                nearest_competing_cosine=0.74,
                competing_concept_id="prorrata-especial",
                status=RatificationStatus.PROPOSED,
            ),
        ),
    )

    result = validate_ratification_queue(queue, handbook=load_terminology_handbook())

    assert not result.passed
    assert result.violations[0].reason == "unratified candidate is present in the shipped query vocabulary"


def test_synonym_validation_cli_reports_clean_queue() -> None:
    result = CliRunner().invoke(app, ["validate"])

    assert result.exit_code == 0
    assert "synonyms: clean" in result.stdout
