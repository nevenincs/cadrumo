"""Real-behavior tests: adding one row to a repeatable profile section.

The load-bearing case is the implicit unindexed row. The setup wizard
writes ``activities.description`` with no index, so a taxpayer who
completed setup already holds an activity that lives under the ``""`` row
key. Numbering the next row ``0`` would sit an explicitly numbered row
beside that implicit one, and would merge the two outright if the implicit
spelling were ever normalised to ``activities.0.*`` -- an activity would
disappear from a filing without anything failing. That is the defect these
tests exist to prevent, and it is silent in every direction: no gate fires,
the count simply reads one instead of two.

The other half is that assembling a row must not weaken the rule the write
door enforces. A row is all-or-nothing there, so a partial row assembled
here must still be refused; the refusal test is what proves the assembly is
a convenience over the door rather than a way around it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....domain.user_profile import (
    ProfileSchemaValidationError,
    UserProfileFact,
    load_user_profile_schema,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow import workflow_state_repository
from .. import (
    ProfileRepository,
    build_profile_overview,
    next_section_row_index,
    profile_create_storage_span,
    section_row_facts,
    set_active_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_ACTIVITIES = "activities"
_SOCIOS = "attribution_entity_socios"


def _section(key: str):
    return next(section for section in load_user_profile_schema().sections if section.key == key)


def _register_active() -> None:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name="row-operator",
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )


def _write(*facts: UserProfileFact) -> None:
    workflow_state_repository().update(lambda state: set_active_fields(state, facts))


def _present() -> frozenset[str]:
    """Present paths as the manager's own page decides them."""
    record = ProfileRepository().load(_BUCKET_ID).record
    overview = build_profile_overview(record)
    return frozenset(view.path for section in overview.sections for view in section.fields if view.present)


def _rows(section_key: str) -> list[str | None]:
    record = ProfileRepository().load(_BUCKET_ID).record
    overview = build_profile_overview(record)
    section = next(view for view in overview.sections if view.key == section_key)
    return sorted({view.row_index for view in section.fields if view.present}, key=lambda row: (row is not None, row))


# ── index allocation ───────────────────────────────────────────────


def test_a_wizard_shaped_profile_numbers_the_next_activity_one() -> None:
    """The implicit unindexed row occupies slot zero, so the next row is one.

    This is the whole point of the reservation. The wizard writes
    ``activities.description`` unindexed; allocating ``0`` would put a
    numbered row beside it and collide with it the moment the implicit
    spelling is normalised.
    """
    _register_active()
    _write(UserProfileFact(path=f"{_ACTIVITIES}.description", value="Consultoria"))

    assert next_section_row_index(_ACTIVITIES, _present()) == 1


def test_adding_to_a_wizard_shaped_profile_yields_two_activities() -> None:
    """The end an operator sees: they had one activity, now they have two.

    Asserted on the rendered rows rather than on the index, because the
    failure this guards against is not a wrong number -- it is an activity
    that silently is not there.
    """
    _register_active()
    _write(UserProfileFact(path=f"{_ACTIVITIES}.description", value="Consultoria"))

    section = _section(_ACTIVITIES)
    index = next_section_row_index(_ACTIVITIES, _present())
    _write(*section_row_facts(section, row_index=index, values={"description": "Formacion"}))

    # The implicit row first, then the numbered one: it is the occupant of
    # slot zero, and TWO entries is the property under test -- one would mean
    # the new activity had merged into the row the wizard wrote.
    assert _rows(_ACTIVITIES) == [None, "1"]


def test_a_section_holding_nothing_starts_at_zero() -> None:
    """No implicit row, no numbered row: the first row is row zero."""
    assert next_section_row_index(_ACTIVITIES, frozenset()) == 0


def test_the_next_index_clears_the_highest_row_in_use() -> None:
    """Numbering follows the highest index, not the count of rows.

    Numerically rather than lexicographically, or row 10 would be treated
    as lower than row 2 and the new row would land on one already taken.
    """
    present = frozenset({f"{_ACTIVITIES}.2.description", f"{_ACTIVITIES}.10.description"})

    assert next_section_row_index(_ACTIVITIES, present) == 11


def test_a_gap_left_by_a_blanked_row_is_not_reused() -> None:
    """A freed index stays free rather than being handed to a new row.

    Reusing it would give the new row an identity a reader may still be
    holding from the row that was removed.
    """
    present = frozenset({f"{_ACTIVITIES}.1.description"})

    assert next_section_row_index(_ACTIVITIES, present) == 2


# ── fact projection ────────────────────────────────────────────────


def test_row_facts_address_the_chosen_row_and_drop_blanks() -> None:
    """Values land at ``section.INDEX.field``; a blank answer writes nothing.

    A blank yields no fact rather than a fact carrying ``None``: on a new
    row there is nothing to clear, and a null would make an unanswered
    optional field look deliberately emptied.
    """
    facts = section_row_facts(
        _section(_SOCIOS),
        row_index=3,
        values={"nif": "B12345678", "name": " Socio Uno ", "share_pct": "  ", "role": ""},
    )

    assert [(fact.path, fact.value) for fact in facts] == [
        (f"{_SOCIOS}.3.nif", "B12345678"),
        (f"{_SOCIOS}.3.name", "Socio Uno"),
    ]


def test_row_facts_ignore_keys_naming_no_declared_field() -> None:
    """A surface's own bookkeeping entries are not persisted as facts.

    The row page carries a section chooser alongside the answers; it is not
    a field of the row and must not reach the record.
    """
    facts = section_row_facts(
        _section(_ACTIVITIES),
        row_index=0,
        values={"description": "Consultoria", "__row_section": _ACTIVITIES},
    )

    assert [fact.path for fact in facts] == [f"{_ACTIVITIES}.0.description"]


# ── the door still decides what a complete row is ──────────────────


def test_a_row_assembled_here_satisfies_the_write_door() -> None:
    """A complete row assembled from the schema is accepted and renders as a row."""
    _register_active()
    section = _section(_SOCIOS)
    facts = section_row_facts(
        section,
        row_index=next_section_row_index(_SOCIOS, _present()),
        values={
            "nif": "B12345678",
            "name": "Socio Uno",
            "share_pct": "50",
            "base_imponible_assigned": "1000",
        },
    )

    _write(*facts)

    assert _rows(_SOCIOS) == ["0"]
    record = ProfileRepository().load(_BUCKET_ID).record
    assert build_profile_overview(record).missing_required == ()


def test_a_partial_row_assembled_here_is_still_refused() -> None:
    """Assembly is a convenience over the door, never a way around it.

    Without this, a helper that builds paths for a caller could quietly
    become the surface through which a half-filled socio reaches a filing.
    """
    _register_active()
    facts = section_row_facts(_section(_SOCIOS), row_index=0, values={"nif": "B12345678"})

    with pytest.raises(ProfileSchemaValidationError):
        _write(*facts)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield
