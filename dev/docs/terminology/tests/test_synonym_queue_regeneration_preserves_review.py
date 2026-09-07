"""Regenerating the ratification queue must not write off its review decisions.

``dev/docs/terminology/ratification/synonym-candidates.json`` declares
``generated_by`` and reads, to anyone opening it, as a generator's output. It is
not. Three of its fields - ``status``, ``review_reason``, ``reviewed_at`` - are
written by a human reviewer, and :func:`mine_synonym_candidates` structurally
cannot emit them: every mined row is born ``proposed``, and the entry validator
*forbids* a proposed row from carrying review fields at all.

The blast radius was the CLI default. ``synonyms mine`` took ``--out`` defaulting
to the committed queue, so the documented invocation overwrote the artifact that
held the decisions. Feeding the committed queue's own rows back through the miner
returned one entry where three went in: the ratified row was skipped because
ratified *means* it landed in the Handbook and the miner skips shipped
vocabulary, and the rejected row went with it. Exit code 0. ``synonyms validate``
then reported "clean" on the survivor, because it only ever iterates the rows the
queue still has - so the loss was invisible from both ends.

The sibling CLI in the same package, ``sweep --out``, defaults to ``None`` and
writes nothing unless pointed somewhere. Same package, same idiom, opposite blast
radius, and the destructive default was the one guarding hand-authored evidence.

The remedy is both halves: decisions whose rows the miner still produces are
carried forward, and a mine that would still drop one is refused whole with the
entire loss set computed before the first byte is written.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .._synonym_cli import app
from .._synonym_mining import (
    RatificationStatus,
    SynonymCandidateEntry,
    SynonymCandidateObservation,
    SynonymRatificationQueue,
    carry_forward_review_state,
    load_synonym_ratification_queue,
    mine_synonym_candidates,
    reviewed_decisions_dropped,
    synonym_ratification_queue_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REVIEW_FIELDS = ("status", "review_reason", "reviewed_at")


def _committed_queue() -> SynonymRatificationQueue:
    return load_synonym_ratification_queue()


def _observations_from(queue: SynonymRatificationQueue) -> tuple[SynonymCandidateObservation, ...]:
    """Re-derive the raw mining observations the committed rows came from.

    This is what a re-mine of the same embedding run looks like: the mined
    columns, with every hand-authored column stripped.
    """
    return tuple(
        SynonymCandidateObservation(
            concept_id=entry.concept_id,
            source_term=entry.source_term,
            candidate=entry.candidate,
            language=entry.language,
            action=entry.action,
            cosine=entry.cosine,
            nearest_competing_cosine=entry.nearest_competing_cosine,
            competing_concept_id=entry.competing_concept_id,
        )
        for entry in queue.entries
    )


def _reviewed(queue: SynonymRatificationQueue) -> tuple[SynonymCandidateEntry, ...]:
    return tuple(entry for entry in queue.entries if entry.status is not RatificationStatus.PROPOSED)


def _write_queue(destination: Path, queue: SynonymRatificationQueue) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(queue.model_dump_json(indent=2) + chr(10), encoding="utf-8", newline="")


def _observation_payload(queue: SynonymRatificationQueue) -> list[dict[str, object]]:
    return [
        {key: value for key, value in json.loads(entry.model_dump_json()).items() if key not in _REVIEW_FIELDS}
        for entry in queue.entries
    ]


def test_the_committed_queue_still_holds_decisions_worth_protecting() -> None:
    """Re-derived from the live artifact, so the premise cannot rot silently.

    If every reviewed decision is one day retired, this gate stops claiming to
    protect something that is no longer there instead of passing vacuously.
    """
    queue = _committed_queue()
    reviewed = _reviewed(queue)
    assert reviewed, (
        "the committed queue holds no reviewed decision, so every assertion below "
        "would measure an empty set; retire this gate or restore the decisions"
    )
    for entry in reviewed:
        assert entry.review_reason is not None
        assert entry.reviewed_at is not None


def test_a_re_mine_cannot_reproduce_the_committed_review_decisions() -> None:
    """The defect proof: the real miner, the real Handbook, the real queue.

    Not a claim about provenance in the abstract. These exact rows, fed back
    through the exact function the CLI calls, come back stripped.
    """
    queue = _committed_queue()
    remined = mine_synonym_candidates(_observations_from(queue))
    assert all(entry.status is RatificationStatus.PROPOSED for entry in remined.entries), (
        "the miner emitted a reviewed row, which its own entry validator forbids"
    )
    lost = reviewed_decisions_dropped(remined, queue)
    assert lost, "a bare re-mine now preserves the decisions; the bound below is measuring nothing"
    ratified = {entry.candidate for entry in _reviewed(queue) if entry.status is RatificationStatus.RATIFIED}
    assert ratified <= {entry.candidate for entry in lost}, (
        "every ratified row must appear in the loss set: ratified means shipped, "
        "and the miner skips shipped vocabulary by design"
    )


def test_carry_forward_reattaches_a_decision_whose_row_the_miner_still_produces() -> None:
    """The rescue half. A rejected row is not shipped, so the miner keeps it."""
    queue = _committed_queue()
    survivors = mine_synonym_candidates(_observations_from(queue)).entries
    assert survivors, "the miner produced nothing, so carry-forward has no row to act on"
    target = survivors[0]
    decision = SynonymCandidateEntry(
        concept_id=target.concept_id,
        source_term=target.source_term,
        candidate=target.candidate,
        language=target.language,
        action=target.action,
        cosine=target.cosine,
        nearest_competing_cosine=target.nearest_competing_cosine,
        competing_concept_id=target.competing_concept_id,
        status=RatificationStatus.REJECTED,
        review_reason="Rejected in review as a near-duplicate of an admitted term.",
        reviewed_at=date(2026, 9, 7),
    )
    prior = SynonymRatificationQueue(generated_by="test", entries=(decision,))
    carried = carry_forward_review_state(mine_synonym_candidates(_observations_from(queue)), prior)
    landed = {entry.candidate: entry for entry in carried.entries}
    assert landed[target.candidate].status is RatificationStatus.REJECTED
    assert landed[target.candidate].reviewed_at == date(2026, 9, 7)
    assert not reviewed_decisions_dropped(carried, prior)


def test_the_cli_refuses_the_losing_mine_and_leaves_the_queue_byte_identical(tmp_path: Path) -> None:
    """A refusal is atomic: the whole loss set is computed before any write."""
    committed = _committed_queue()
    queue_path = tmp_path / "ratification" / "synonym-candidates.json"
    _write_queue(queue_path, committed)
    before = hashlib.sha256(queue_path.read_bytes()).hexdigest()

    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps(_observation_payload(committed)), encoding="utf-8", newline="")

    result = CliRunner().invoke(app, ["mine", str(observations), "--out", str(queue_path)])

    assert result.exit_code == 1, result.output
    assert "refusing to write" in result.output
    for entry in _reviewed(committed):
        if entry.status is RatificationStatus.RATIFIED:
            assert entry.candidate in result.output, "the refusal must name each decision it protects"
    assert hashlib.sha256(queue_path.read_bytes()).hexdigest() == before, (
        "the refusal wrote to the queue before giving up, so it is not atomic"
    )


def test_drop_reviewed_is_the_explicit_opt_in_that_retires_them(tmp_path: Path) -> None:
    """The bound is a refusal, not a prohibition: retiring a decision stays possible."""
    committed = _committed_queue()
    queue_path = tmp_path / "ratification" / "synonym-candidates.json"
    _write_queue(queue_path, committed)
    before = hashlib.sha256(queue_path.read_bytes()).hexdigest()

    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps(_observation_payload(committed)), encoding="utf-8", newline="")

    result = CliRunner().invoke(app, ["mine", str(observations), "--out", str(queue_path), "--drop-reviewed"])

    assert result.exit_code == 0, result.output
    assert hashlib.sha256(queue_path.read_bytes()).hexdigest() != before
    rewritten = load_synonym_ratification_queue(queue_path)
    assert len(rewritten.entries) < len(committed.entries)


def test_the_committed_queue_is_the_default_write_target() -> None:
    """The reason this gate exists: the destructive path is the documented one.

    If the default is ever changed to a scratch path or to ``None``, the bound
    stops being load-bearing and this assertion says so.
    """
    default = synonym_ratification_queue_path()
    assert default.is_file()
    assert default == Path(__file__).resolve().parents[1] / "ratification" / "synonym-candidates.json"
