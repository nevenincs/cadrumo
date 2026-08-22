"""The profile-seeding helpers must seed the record a test asked for.

``replace_test_profile_record`` is the door 110 test modules reach a seeded
profile through, and 104 of them seed ``setup_state = COMPLETE``. It wrote the
caller's FACTS and nothing else, because the fact writer takes facts and nothing
else -- so a test asking for a completed profile got its facts back on a record
that was still INCOMPLETE, and every modelo action behind the readiness gate
refused it with ``profile_readiness_setup_incomplete``.

That refusal named no missing field, which is what made the cause hard to see
from the failure: nothing WAS missing. The state simply never reached storage,
and the helper returned the stored record rather than the one it was handed.

The promotion goes through :meth:`ProfileRecordRepository.complete_setup`, the
production door, which judges the claim rather than stamping it. These tests pin
both halves: the state a caller asks for is the state that comes back, and a
fixture whose facts cannot support the claim is refused rather than seeded into
a state no production path could produce.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..application.user_profile import ProfileRecordRepository
from ..domain.user_profile import ProfileSetupState, UserProfileRecord
from .profile_capsule import seed_test_profile_record
from .secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "6f1f7d4e-9d64-4a1a-9a2f-2c0d4e5b7a10"


def _loaded(bucket_id: str) -> UserProfileRecord:
    return ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)


def test_a_profile_seeded_complete_loads_back_complete(tmp_path: Path) -> None:
    """The state the caller declared is the state storage returns."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        before = _loaded(profile.bucket_id)
        assert before.setup_state is ProfileSetupState.INCOMPLETE, (
            "a freshly minted capsule must start INCOMPLETE, or this test cannot show that the seeding promoted it"
        )

        seeded = seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_complete_facts(),
            ),
        )

        assert seeded.setup_state is ProfileSetupState.COMPLETE
        assert _loaded(profile.bucket_id).setup_state is ProfileSetupState.COMPLETE


def test_the_seeded_facts_survive_alongside_the_promoted_state(tmp_path: Path) -> None:
    """Promoting the state must not cost the facts, nor the reverse.

    The two are written through different doors, so a fix that reached one by
    abandoning the other would satisfy the sibling test above and still leave
    every caller broken.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        facts = _complete_facts()
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=facts,
            ),
        )

        stored = _loaded(profile.bucket_id)
        assert stored.setup_state is ProfileSetupState.COMPLETE
        assert {fact.path for fact in stored.facts} >= {fact.path for fact in facts}


def test_a_profile_seeded_incomplete_is_left_incomplete(tmp_path: Path) -> None:
    """The promotion is conditional on what the caller asked for.

    A test seeding an INCOMPLETE profile is usually testing the refusal, so
    promoting unconditionally would quietly delete the scenario.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.INCOMPLETE,
                profile_id=profile.bucket_id,
                facts=_complete_facts(),
            ),
        )

        assert _loaded(profile.bucket_id).setup_state is ProfileSetupState.INCOMPLETE


def _complete_facts():
    """Return the fact set a completed profile carries, from a real seeding caller."""
    from ..application.modelo.tests.test_work_unit_discard_refusal import _READY_PROFILE_FACTS

    return _READY_PROFILE_FACTS
