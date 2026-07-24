"""Persistence-boundary coverage for the descendant repeating group.

Every scenario drives the real profile lifecycle authority through an
isolated encrypted storage root — descendant facts genuinely persist to
the secure-object store and are read back through the real repository,
never a mock. Three behaviours are pinned: the weaving of question facts
and descendant facts through the one checkpoint writer, the no-drop
survival of descendant facts across a re-persist that never re-answers
the group, and the count-shrink namespace replacement that clears the
orphaned instance rows so the on-record set can never carry an index
above the answered count.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.flows import FlowMode
from ....domain.user_profile import UserProfileFactValue, new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...flows import flow_definition_from_wizard_flow, resume_flow, run_scripted_flow
from ...user_profile import profile_storage_session, record_to_path_values
from ...workflow import workflow_state_repository
from .. import ProfileFactsCheckpointStore, checkpoint_answers_from_record, checkpoint_facts_from_answers
from .._catalogue import SETUP_FLOW
from .._commands import _SETUP_CHECKPOINT, _setup_flow_definition
from .._descendant_group import DESCENDANTS_GROUP_ID
from .test_setup_runtime import _scripted_answers_for_individual_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "12345678Z"

# Descendant answer keys layered onto the baseline walk. Instance 0 is a
# menor-3 in 2024 with guardería spend (so the reales aggregate is set);
# instance 1 is an older adopted child carrying a NIF.
_DESCENDANT_ANSWERS = {
    "descendientes-count": "2",
    "descendientes#0.birth-date": "2023-05-10",
    "descendientes#0.convivencia": "true",
    "descendientes#0.gastos-guarderia": "900",
    "descendientes#1.birth-date": "2015-03-01",
    "descendientes#1.adoption-date": "2016-06-01",
    "descendientes#1.convivencia": "true",
    "descendientes#1.nif": "00000000T",
}


@pytest.fixture
def _backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _baseline_answers() -> dict[str, str]:
    """A full valid individual-declaration walk (every required field set)."""
    definition = flow_definition_from_wizard_flow(SETUP_FLOW, checkpoint=dict(_SETUP_CHECKPOINT))
    tokens = list(_scripted_answers_for_individual_declaration())
    state, _projection = run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)
    return dict(state.answers)


def _baseline_with_two_descendants() -> dict[str, str]:
    return {**_baseline_answers(), **_DESCENDANT_ANSWERS}


def _store(profile_id: str) -> ProfileFactsCheckpointStore:
    return ProfileFactsCheckpointStore(SETUP_FLOW, profile_id=profile_id, profile_name="operator")


def _record_values(profile_id: str) -> dict[str, str]:
    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
    return record_to_path_values(record)


# ── (a) weaving: question + descendant facts co-emit ────────────────


def test_checkpoint_facts_weave_question_and_descendant_facts() -> None:
    facts = checkpoint_facts_from_answers(SETUP_FLOW, _baseline_with_two_descendants())
    paths = {fact.path: fact.value for fact in facts}

    # The question fact (top-level profile_key binding) rode through …
    assert paths["identity.tax_id"] == _TAX_ID
    # … alongside the derived descendant facts and aggregates (values are
    # type-coerced by the fact model, so compare rendered forms / membership).
    assert "renta_family.descendiente.0.birth_date" in paths
    assert paths["renta_family.descendiente.1.nif"] == "00000000T"
    assert str(paths["renta_family.descendientes_count"]) == "2"
    assert str(paths["renta_family.gastos_guarderia_reales_2024"]) == "900"


# ── (b) round-trip no-drop across a group-less re-persist ───────────


def test_descendant_facts_survive_a_repersist_without_reanswering_the_group(_backend: Path) -> None:
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _baseline_with_two_descendants())

    # A later re-persist that carries only a top-level edit and NO descendant
    # answers (the count page absent) must leave the descendant facts intact:
    # the projection contributes nothing, so nothing is cleared.
    store.persist({"tax-id": _TAX_ID, "notes": "later edit"})

    values = _record_values(profile_id)
    assert values["renta_family.descendiente.0.birth_date"] == "2023-05-10"
    assert values["renta_family.descendiente.1.birth_date"] == "2015-03-01"
    assert values["renta_family.descendiente.1.nif"] == "00000000T"
    assert values["renta_family.descendientes_count"] == "2"


# ── (c) count-shrink replaces the descendant namespace ──────────────


def test_count_shrink_clears_orphaned_instance_rows(_backend: Path) -> None:
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _baseline_with_two_descendants())

    before = _record_values(profile_id)
    assert before["renta_family.descendiente.1.birth_date"] == "2015-03-01"
    assert before["renta_family.gastos_guarderia_reales_2024"] == "900"

    # Resume answers a smaller count with one non-menor-3 instance; the
    # descendant namespace is replaced, so index 1 and the stale reales
    # aggregate go.
    store.persist(
        {
            "descendientes-count": "1",
            "descendientes#0.birth-date": "2019-04-04",
            "descendientes#0.convivencia": "true",
        },
    )

    after = _record_values(profile_id)
    assert after["renta_family.descendiente.0.birth_date"] == "2019-04-04"
    assert after["renta_family.descendientes_count"] == "1"
    assert not any(path.startswith("renta_family.descendiente.1.") for path in after)
    assert "renta_family.gastos_guarderia_reales_2024" not in after


def test_count_zero_clears_every_descendant_row(_backend: Path) -> None:
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _baseline_with_two_descendants())

    store.persist({"descendientes-count": "0"})

    after = _record_values(profile_id)
    assert not any(path.startswith("renta_family.descendiente.") for path in after)
    assert after["renta_family.descendientes_count"] == "0"


# ── (d) resume seeding: facts re-project, resume re-instantiates ────


def _descendant_facts(answers: dict[str, str]) -> dict[str, UserProfileFactValue]:
    """The descendant slice of a checkpoint fact projection, path -> value."""
    return {
        fact.path: fact.value
        for fact in checkpoint_facts_from_answers(SETUP_FLOW, answers)
        if fact.path.startswith("renta_family.descendiente")
    }


def test_resume_seeding_reinstantiates_the_group_and_round_trips(_backend: Path) -> None:
    """A saved create round-trips its descendants through resume seeding.

    Create two descendants, read the persisted record, re-project it to a
    page-keyed answer map, and prove the count page plus both instances
    reappear (the seed gap this closes). ``resume_flow`` re-walks that seed
    against the full descendant-bearing definition: the count answer commits
    first, revealing the instance pages the rest of the seed then fills, so
    the group is re-instantiated with no stale or orphaned answer. Completing
    from the resumed answers reconstructs an identical descendant fact set.
    Expected values are the specification (the saved answers), never a copy
    of the projection output.
    """
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _baseline_with_two_descendants())

    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
    seeded = checkpoint_answers_from_record(SETUP_FLOW, record)

    # The projection now carries the count page AND both instances.
    assert seeded["descendientes-count"] == "2"
    assert seeded["descendientes#0.birth-date"] == "2023-05-10"
    assert seeded["descendientes#0.gastos-guarderia"] == "900"
    assert seeded["descendientes#1.birth-date"] == "2015-03-01"
    assert seeded["descendientes#1.adoption-date"] == "2016-06-01"
    assert seeded["descendientes#1.nif"] == "00000000T"

    # resume_flow re-instantiates the group from the seed: the count commits
    # first, the instances seed against the current definition, none go stale.
    definition = _setup_flow_definition(SETUP_FLOW)
    state = resume_flow(definition, seeded, mode=FlowMode.CREATE)
    assert state.instance_counts.get(DESCENDANTS_GROUP_ID) == 2
    assert state.answers["descendientes#0.birth-date"] == "2023-05-10"
    assert state.answers["descendientes#1.adoption-date"] == "2016-06-01"
    assert not any(key.startswith("descendientes") for key in state.stale)

    # Completing from the resumed answers reconstructs an identical fact set.
    assert _descendant_facts(dict(state.answers)) == _descendant_facts(_baseline_with_two_descendants())
