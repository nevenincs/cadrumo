"""The paged descendant door: real seed, real commit, real read-back.

Every scenario drives the profile lifecycle authority through an isolated
encrypted storage root — the descendant facts genuinely persist and are read
back through the real repository, never a mock. The door adopts the setup
flow's own count page and repeating group, so these tests also lock the
adoption of those building blocks (the count page's ``entity-type`` visibility
gate stripped, the adoption cross-field validator carried onto the door).

Structural assertions read persisted fact paths and reconstructed
:class:`~cadrumo.domain.contribuyente.DescendantInfo` rows; no localized prose
is asserted.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path

import pytest

from ....core.flows import REPEATING_INSTANCE_SEPARATOR, FlowMode
from ....domain.contribuyente import (
    DescendantInfo,
    descendant_facts_from_list,
    descendant_list_from_facts,
)
from ....domain.user_profile import new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...flows import FlowSubmitError, run_scripted_flow
from ...user_profile import (
    profile_create_storage_span,
    profile_storage_session,
    record_to_path_values,
)
from ...workflow import workflow_state_repository
from .. import build_descendant_door, persist_descendant_door_answers
from .._descendant_door import DESCENDANT_DOOR_FLOW_ID, build_descendant_door_definition
from .._descendant_group import DESCENDANT_ADOPTION_VALIDATOR_ID, DESCENDANTS_COUNT_PAGE_ID, DESCENDANTS_GROUP_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INSTANCE = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}"
# A non-descendant fact register_minimal_profile always writes, used to prove the
# door commit never reaches outside the renta_family.descendiente.* namespace.
_UNTOUCHED_PATH = "identity.name"
_UNTOUCHED_VALUE = "Test Operator"

_D0 = DescendantInfo(birth_date=date(2015, 6, 1), convive_con_contribuyente=True)
_D1 = DescendantInfo(birth_date=date(2018, 9, 20), convive_con_contribuyente=True)


@pytest.fixture
def _backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _seed_profile(descendants: Sequence[DescendantInfo]) -> str:
    """Register a schema-valid active profile carrying ``descendants``."""
    profile_id = new_profile_id()
    overrides = {path: value for path, value in descendant_facts_from_list(descendants)}
    with profile_create_storage_span(profile_id):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=profile_id,
                display_name="operator",
                overrides=overrides,
            ),
        )
    return profile_id


def _instance_key(index: int, page_id: str) -> str:
    return f"{_INSTANCE}{index}.{page_id}"


def _door_tokens(count: int, *, adoption: str = "") -> list[str]:
    """Ordered canonical tokens for a scripted door walk declaring ``count`` rows."""
    tokens = [str(count)]
    for offset in range(count):
        birth = date(2015 + offset, 6, 1).isoformat()
        tokens.extend([birth, adoption, "0", "true", "false", "", "", ""])
    return tokens


# ── definition: the group is adopted, the entity-type gate stripped ──


def test_door_definition_adopts_the_group_and_carries_the_adoption_validator() -> None:
    definition = build_descendant_door_definition()
    assert definition.id == DESCENDANT_DOOR_FLOW_ID
    (section,) = definition.sections
    count_page, group = section.items
    assert count_page.id == DESCENDANTS_COUNT_PAGE_ID
    # The entity-type visibility gate is stripped: the door has no entity-type
    # page, and a dangling gate would fail the definition's earlier-page check.
    assert count_page.visible_when is None
    assert group.id == DESCENDANTS_GROUP_ID
    assert DESCENDANT_ADOPTION_VALIDATOR_ID in definition.flow_validator_ids


# ── seed: existing descendants re-instantiate the group ──────────────


def test_door_seeds_existing_descendants_from_the_record(_backend: Path) -> None:
    profile_id = _seed_profile([_D0, _D1])
    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        _definition, resume_state = build_descendant_door(record)

    assert resume_state.answers[DESCENDANTS_COUNT_PAGE_ID] == "2"
    # The count answer re-instantiated the repeating group to two instances, and
    # each instance's persisted fields seeded back onto its pages.
    assert resume_state.instance_counts[DESCENDANTS_GROUP_ID] == 2
    assert resume_state.answers[_instance_key(0, "birth-date")] == _D0.birth_date.isoformat()
    assert resume_state.answers[_instance_key(1, "birth-date")] == _D1.birth_date.isoformat()
    assert resume_state.answers[_instance_key(0, "convivencia")] == "true"
    assert resume_state.answers[_instance_key(1, "convivencia")] == "true"


# ── commit: count-shrink clears the orphaned higher index ────────────


def test_door_commit_count_shrink_clears_the_orphaned_index(_backend: Path) -> None:
    profile_id = _seed_profile([_D0, _D1])
    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        _definition, resume_state = build_descendant_door(record)

        # The operator edits index 0's birth date and shrinks the count to one,
        # dropping index 1 — exactly the committed answer map a frontend yields.
        answers = dict(resume_state.answers)
        answers[DESCENDANTS_COUNT_PAGE_ID] = "1"
        answers[_instance_key(0, "birth-date")] = "2016-03-03"
        answers = {key: value for key, value in answers.items() if not key.startswith(f"{_INSTANCE}1.")}

        persist_descendant_door_answers(answers)
        after = workflow_state_repository().load().active_profile_record()

    values = record_to_path_values(after)
    remaining = descendant_list_from_facts(values)
    assert len(remaining) == 1
    assert remaining[0].birth_date == date(2016, 3, 3)
    # No orphaned index-1 row survives the shrink.
    assert not any(key.startswith("renta_family.descendiente.1.") for key in values)
    assert values["renta_family.descendientes_count"] == "1"


# ── commit: the descendant namespace is the ONLY namespace touched ───


def test_door_commit_leaves_non_descendant_facts_untouched(_backend: Path) -> None:
    profile_id = _seed_profile([_D0, _D1])
    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        _definition, resume_state = build_descendant_door(record)

        answers = dict(resume_state.answers)
        answers[DESCENDANTS_COUNT_PAGE_ID] = "1"
        answers = {key: value for key, value in answers.items() if not key.startswith(f"{_INSTANCE}1.")}
        persist_descendant_door_answers(answers)
        after = workflow_state_repository().load().active_profile_record()

    values = record_to_path_values(after)
    assert values[_UNTOUCHED_PATH] == _UNTOUCHED_VALUE


# ── commit: a childless record writes no descendant fact ─────────────


def test_childless_record_seeds_empty_and_commits_no_descendant_fact(_backend: Path) -> None:
    profile_id = _seed_profile([])
    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        _definition, resume_state = build_descendant_door(record)
        assert resume_state.answers.get(DESCENDANTS_COUNT_PAGE_ID, "0") in {"", "0"}

        persist_descendant_door_answers({DESCENDANTS_COUNT_PAGE_ID: "0"})
        after = workflow_state_repository().load().active_profile_record()

    values = record_to_path_values(after)
    assert not any(key.startswith("renta_family.descendiente.") for key in values)
    assert values[_UNTOUCHED_PATH] == _UNTOUCHED_VALUE


# ── review gate: the adoption cross-field rule is live on the door ───


def test_adoption_before_birth_is_refused_on_the_door() -> None:
    definition = build_descendant_door_definition()
    # Adoption predates birth: committed per-page (DATE-shape valid) but blocked
    # by the flow-scope adoption validator carried onto the door at submit.
    tokens = _door_tokens(1, adoption="2010-01-01")
    with pytest.raises(FlowSubmitError):
        run_scripted_flow(definition, tokens, mode=FlowMode.MODIFY)


def test_valid_adoption_after_birth_submits_on_the_door() -> None:
    definition = build_descendant_door_definition()
    tokens = _door_tokens(1, adoption="2016-01-01")
    state, projection = run_scripted_flow(definition, tokens, mode=FlowMode.MODIFY)
    assert projection.submit_eligible
    assert state.answers[DESCENDANTS_COUNT_PAGE_ID] == "1"
