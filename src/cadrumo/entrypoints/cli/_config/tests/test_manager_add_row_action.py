"""What the manager's add-row page offers, and what it writes.

A repeatable section's row is all-or-nothing at the write door, so the
manager cannot create one by editing a cell: the first write would be
refused for the fields not yet supplied. This action is the gesture that
closes that -- collect the whole row, commit once.

Two properties carry it. The page has to ask about a section the schema
actually declares repeatable, and it has to ask for that section's own
fields, so picking a different section replaces them rather than adding to
them. And the commit has to reach the encrypted record through the same
batch door every other multi-field write uses, carrying no trace of the
page's own bookkeeping.

Rendered prose is never asserted: it is locale data, and pinning it would
test the catalogue rather than the page. The section chooser is pinned by
its stored key, which no choice of words can satisfy by accident.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from .....adapters.inbound.tui import FormPage, presenting_forms_through
from .....application.user_profile import ProfileRecordRepository, profile_create_storage_span
from .....application.workflow import workflow_state_repository
from .....core import require_active_bucket_id
from .....domain.user_profile import load_user_profile_schema
from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_minimal_profile
from .._manager_actions import _ROW_SECTION_KEY, _row_page, _run_add_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_SOCIOS = "attribution_entity_socios"
_ACTIVITIES = "activities"


def _repeatable():
    return tuple(section for section in load_user_profile_schema().sections if section.repeatable)


def _run(answer: Mapping[str, str] | None):
    """Run the action with the page answered by ``answer``.

    Routed through the shipped presenter seam rather than by calling the
    commit helper directly, so these cases exercise the path the running
    manager takes.
    """

    def _present(page: FormPage, rebuild: object = None) -> Mapping[str, str] | None:
        return answer

    with presenting_forms_through(_present):
        return _run_add_row()


def _facts(prefix: str) -> dict[str, object]:
    profile_id = require_active_bucket_id()
    record = ProfileRecordRepository(bucket_id=profile_id).load(profile_id)
    return {fact.path: fact.value for fact in record.facts if fact.path.startswith(prefix)}


# ── the page ───────────────────────────────────────────────────────


def test_the_chooser_offers_every_repeatable_section_and_nothing_else() -> None:
    """A section that holds no rows must not be offered as one that does."""
    page = _row_page(_repeatable(), {})
    chooser = next(field for field in page.fields if field.key == _ROW_SECTION_KEY)

    assert [choice.value for choice in chooser.choices] == [section.key for section in _repeatable()]


def test_the_page_asks_for_the_chosen_section_s_own_fields() -> None:
    """Picking a section replaces the fields below the chooser.

    Pinned as an inequality between two sections rather than as a literal
    field list, so the case keeps meaning if the schema gains a field.
    """
    activities = _row_page(_repeatable(), {_ROW_SECTION_KEY: _ACTIVITIES})
    socios = _row_page(_repeatable(), {_ROW_SECTION_KEY: _SOCIOS})

    def _keys(page: FormPage) -> list[str]:
        return [field.key for field in page.fields if field.key != _ROW_SECTION_KEY]

    section = next(item for item in _repeatable() if item.key == _ACTIVITIES)
    assert _keys(activities) == [field.key for field in section.fields]
    assert _keys(activities) != _keys(socios)


def test_a_required_field_refuses_when_left_blank() -> None:
    """Caught where it was typed rather than as a refusal naming paths.

    The form re-checks every field on submit, including ones never opened,
    so this is what stops an incomplete row reaching the door at all.
    """
    page = _row_page(_repeatable(), {_ROW_SECTION_KEY: _ACTIVITIES})
    description = next(field for field in page.fields if field.key == "description")

    assert description.validate is not None
    assert description.validate("  ") is not None
    assert description.validate("Consultoria") is None


def test_an_enum_field_is_offered_as_its_declared_tokens() -> None:
    """A value outside the closed set is not typeable rather than validated."""
    page = _row_page(_repeatable(), {_ROW_SECTION_KEY: _SOCIOS})
    role = next(field for field in page.fields if field.key == "role")
    declared = next(item for item in _repeatable() if item.key == _SOCIOS)
    tokens = next(field for field in declared.fields if field.key == "role").enum_values

    assert [choice.value for choice in role.choices] == list(tokens)


# ── the commit ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("active_profile")
def test_committing_writes_the_row_into_the_encrypted_profile() -> None:
    """The row lands at ``section.INDEX.field`` and the page is handed back.

    The rebuilt overview is what makes the new row visible without the
    operator reopening the manager.
    """
    answer = {
        "nif": "B12345678",
        "name": "Socio Uno",
        "share_pct": "50",
        "base_imponible_assigned": "1000",
        "participe_clave": "1",
    }

    outcome = _run({_ROW_SECTION_KEY: _SOCIOS, **answer})

    # Compared as text because the persistence boundary restores the types
    # JSON cannot carry: a numeric-shaped string is read back as a Decimal,
    # by a shape rule that belongs to the fact carrier rather than to this
    # page. The property here is that what was typed is what the row holds,
    # so the expectation is built from the submitted answer rather than
    # restated beside it.
    assert {path: str(value) for path, value in _facts(f"{_SOCIOS}.0.").items()} == {
        f"{_SOCIOS}.0.{key}": value for key, value in answer.items()
    }
    assert outcome.overview is not None


@pytest.mark.usefixtures("active_profile")
def test_the_chooser_is_not_persisted_as_a_fact() -> None:
    """The page's bookkeeping key names no schema field and must not be stored."""
    _run({_ROW_SECTION_KEY: _ACTIVITIES, "description": "Consultoria"})

    assert all(_ROW_SECTION_KEY not in path for path in _facts(_ACTIVITIES))


@pytest.mark.usefixtures("active_profile")
def test_abandoning_the_page_writes_nothing() -> None:
    """Leaving without committing is "make no change", never an error."""
    outcome = _run(None)

    assert _facts(_SOCIOS) == {}
    assert outcome.overview is None


@pytest.mark.usefixtures("active_profile")
def test_an_entirely_blank_row_adds_nothing() -> None:
    """A section declaring no required field must not store an empty row.

    ``properties`` has no required field, so nothing refuses a page left
    untouched; without this the action would write a row carrying no facts
    and the operator would gain a phantom entry.
    """
    outcome = _run({_ROW_SECTION_KEY: "properties"})

    assert _facts("properties") == {}
    assert outcome.overview is None


@pytest.fixture(name="active_profile")
def _active_profile(tmp_path: Path) -> Iterator[None]:
    """Stand up a real encrypted profile bucket for the commit cases."""
    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(_PROFILE_ID):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID),
        )
        yield
