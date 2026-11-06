"""Seeding a persona's profile below the entrypoints records what replaying it through the production operations does."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...adapters.persistence.profile.tests.ready_profile_support import seed_persona_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.user_profile.values import UserProfileFact
from ...tests.personas import persona_ids
from .persona_materialisation import (
    ReplayScope,
    load_profile_record,
    materialised_persona,
    persona_profile_id,
    scenario_instant,
    year_envelope,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _held(facts: tuple[UserProfileFact, ...]) -> set[tuple[str, object, str, object, object]]:
    return {(fact.path, fact.value, fact.source, fact.valid_from, fact.valid_to) for fact in facts}


@pytest.mark.parametrize("persona_id", persona_ids())
def test_seeding_a_persona_holds_the_facts_its_profile_replay_records(tmp_path: Path, persona_id: str) -> None:
    with materialised_persona(persona_id, tmp_path / "replay", ReplayScope.PROFILE, reuse=True) as replayed:
        replay_record = load_profile_record(replayed.world)
        complete = all(item.block != "setup" for item in replayed.not_loaded)
        with bundled_indexed_authority().operation() as operation:
            at = scenario_instant(replayed.persona, year_envelope(operation))
    bucket_id = str(persona_profile_id(persona_id))
    with isolated_runtime_profile(tmp_path=tmp_path / "seed", bucket_id=bucket_id):
        seed_persona_profile(persona_id, bucket_id=bucket_id, at=at, complete=complete)
        with bundled_indexed_authority().operation() as operation:
            seeded = ProfileRecordRepository.for_current_session(
                bucket_id, profile_decode_context=operation.profile_decode_context()
            ).load(bucket_id)

    assert _held(seeded.facts) == _held(replay_record.facts)
    assert seeded.setup_state is replay_record.setup_state
