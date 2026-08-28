"""Censal effects, provenance, interactions and cleanup at the CLI seam.

The censo pull verb reaches the censal operation through one public driver,
which submits and starts it against the real composed operation services and
answers its review. These cases drive that same driver and then read the
durable profile record back through its production repository, so what is
asserted is what a later session would actually load.

Provenance is the part with no other home. Existing coverage establishes that
applying advances the record revision; nothing establishes that the adopted
values arrive carrying the censo source tag, which is the difference between a
value the operator typed and a value the tax authority asserted.

Filed-history is deliberately out of scope here. That operation has no
production caller on any frontend, so nothing about it can be proven end to
end from a frontend seam, and a green result here says nothing about it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS, CENSO_SOURCE_TAG
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.projections import record_to_effective_facts
from .._censal_review import _run as run_censal_review_through_services
from .test_registered_executor_conformance import _CloseWitness, _runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ACTOR = "operator:censal-sync-test"


def _decide(*, apply: bool):
    """Return a decision callback recording the projection it was shown."""
    seen: list[object] = []

    def decide(projection) -> bool:
        seen.append(projection)
        return apply

    return decide, seen


def test_applied_censal_review_lands_adopted_values_with_censo_provenance(tmp_path: Path) -> None:
    """Adopted values reach the durable record carrying the censo source tag."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / "censal-apply", cleanup=cleanup) as (driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        before_facts = record_to_effective_facts(before)
        decide, seen = _decide(apply=True)

        result = asyncio.run(
            run_censal_review_through_services(
                actor_ref=_ACTOR,
                decide=decide,
                services=driver.services,
            )
        )

        after = repository.load(profile_id)
        after_facts = record_to_effective_facts(after)

        assert result.applied is True
        assert len(seen) == 1

        # EFFECT: the durable record advanced, read back through the same
        # repository a later session would load it with.
        assert after.record_revision == before.record_revision + 1
        assert after.content_digest != before.content_digest

        adopted = {
            field.path: field.observed_value
            for field in result.projection.fields
            if field.observed_value is not None and field.path in set(CENSAL_ADOPTABLE_PATHS)
        }

        # The proof is only worth something if something was actually adopted
        # and it actually changed the record.
        assert adopted
        changed = {
            path
            for path, value in adopted.items()
            if (previous := before_facts.get(path)) is None or previous.value != value
        }
        assert changed

        # PROVENANCE: every adopted value arrives attributed to the tax
        # authority, not merely present.
        for path, value in adopted.items():
            landed = after_facts.get(path)
            assert landed is not None, path
            assert landed.value == value, path
            assert landed.source == CENSO_SOURCE_TAG, path

        # CLEANUP: the executor's owned acquisition resource was closed.
        assert cleanup.closed is True


def test_rejected_censal_review_leaves_the_record_and_its_provenance_untouched(tmp_path: Path) -> None:
    """A rejected review neither writes values nor stamps censo provenance."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / "censal-reject", cleanup=cleanup) as (driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        decide, seen = _decide(apply=False)

        result = asyncio.run(
            run_censal_review_through_services(
                actor_ref=_ACTOR,
                decide=decide,
                services=driver.services,
            )
        )

        after = repository.load(profile_id)

        assert result.applied is False
        assert len(seen) == 1
        assert after == before
        assert not any(fact.source == CENSO_SOURCE_TAG for fact in record_to_effective_facts(after).values())

        # Cleanup is owed on the rejected path exactly as on the applied one.
        assert cleanup.closed is True


def test_each_censal_acquisition_publishes_exactly_one_answerable_review(tmp_path: Path) -> None:
    """Two runs each review once; neither reuses the other's interaction."""
    first_cleanup = _CloseWitness()
    second_cleanup = _CloseWitness()

    with _runtime(tmp_path / "censal-first", cleanup=first_cleanup) as (driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        decide_first, first_seen = _decide(apply=True)
        first = asyncio.run(
            run_censal_review_through_services(
                actor_ref=_ACTOR,
                decide=decide_first,
                services=driver.services,
            )
        )
        after_first = repository.load(profile_id)

    with _runtime(tmp_path / "censal-second", cleanup=second_cleanup) as (driver, _registry, profile_id):
        decide_second, second_seen = _decide(apply=False)
        second = asyncio.run(
            run_censal_review_through_services(
                actor_ref=_ACTOR,
                decide=decide_second,
                services=driver.services,
            )
        )

    # INTERACTIONS: one review per acquisition, and the two operations are
    # distinct records rather than one interaction answered twice.
    assert len(first_seen) == 1
    assert len(second_seen) == 1
    assert first.operation_id != second.operation_id
    assert first.applied is True
    assert second.applied is False
    assert after_first.record_revision > 0
    assert first_cleanup.closed is True
    assert second_cleanup.closed is True
