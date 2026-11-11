"""The ``--ascendiente`` grammar and the ``--none`` request rules, through their real owners."""

from __future__ import annotations

import pytest

from cadrumo_client.commands.errors import CliRefusedBoundaryError

from .....application.user_profile.family_rows import ProfileFamilyGroupState, ProfileViewFamilyGroupItem
from ..ascendiente_flag import parse_ascendiente_flag
from ..operation_household import require_group_open_to_none, require_rows_or_none

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _leaves(raw: str) -> dict[str, str]:
    return {fact.field_key: fact.value for fact in parse_ascendiente_flag(raw).facts}


def test_each_key_maps_to_exactly_one_stored_leaf() -> None:
    assert _leaves("nacimiento=1948-03-04, NIF=12345678Z ,Fallecimiento=2025-02-01,CONVIVIENTES=2") == {
        "birth_date": "1948-03-04",
        "nif": "12345678Z",
        "fallecimiento": "2025-02-01",
        "convivientes": "2",
    }


def test_the_grammar_leaves_the_required_birth_date_to_the_operation() -> None:
    assert _leaves("NACIMIENTO=1948-03-04") == {"birth_date": "1948-03-04"}
    assert _leaves("NIF=12345678Z") == {"nif": "12345678Z"}


@pytest.mark.parametrize(
    ("raw", "named_key"),
    [
        ("NACIMIENTO=1948-03-04,NOMBRE=Ana", None),
        ("NACIMIENTO=1948-03-04,NACIMIENTO=1950-01-01", "NACIMIENTO"),
        ("NACIMIENTO=1948-03-04,NIF=", "NIF"),
        ("NACIMIENTO=1948-03-04,NIF", "NIF"),
        ("", None),
    ],
)
def test_an_unreadable_row_is_refused_naming_the_key_never_the_value(raw: str, named_key: str | None) -> None:
    with pytest.raises(CliRefusedBoundaryError) as refused:
        parse_ascendiente_flag(raw)
    assert refused.value.translated_message == "cli.config.profile.ascendiente.invalid_row"
    assert refused.value.context == ({"key": named_key} if named_key is not None else {})


def test_a_request_names_rows_or_none_but_not_both_and_not_neither() -> None:
    require_rows_or_none(flag="--ascendiente", supplied=2, none=False)
    require_rows_or_none(flag="--ascendiente", supplied=0, none=True)
    with pytest.raises(CliRefusedBoundaryError) as both:
        require_rows_or_none(flag="--ascendiente", supplied=1, none=True)
    assert both.value.translated_message == "cli.config.profile.household.none_conflicts_with_rows"
    with pytest.raises(CliRefusedBoundaryError) as neither:
        require_rows_or_none(flag="--ascendiente", supplied=0, none=False)
    assert neither.value.translated_message == "cli.config.profile.household.rows_or_none_required"
    assert neither.value.context == {"flag": "--ascendiente", "none": "--none"}


def _group(state: ProfileFamilyGroupState, *, rows: int, stated: str | None) -> ProfileViewFamilyGroupItem:
    return ProfileViewFamilyGroupItem(
        group_key="renta_family.ascendiente", label="group", state=state, stated_count=stated, row_count=rows
    )


@pytest.mark.parametrize(
    ("state", "rows", "stated"),
    [(ProfileFamilyGroupState.UNKNOWN, 0, None), (ProfileFamilyGroupState.NONE_DECLARED, 0, "0")],
)
def test_none_may_answer_an_unasked_group_and_repeat_on_a_stated_empty_one(
    state: ProfileFamilyGroupState, rows: int, stated: str | None
) -> None:
    require_group_open_to_none(_group(state, rows=rows, stated=stated))


@pytest.mark.parametrize(
    ("state", "rows", "stated"),
    [
        (ProfileFamilyGroupState.ROWS, 2, "2"),
        (ProfileFamilyGroupState.INCOMPLETE, 1, "3"),
        (ProfileFamilyGroupState.INCOMPLETE, 0, "3"),
    ],
)
def test_none_never_overwrites_stored_people_or_a_stated_count(
    state: ProfileFamilyGroupState, rows: int, stated: str | None
) -> None:
    with pytest.raises(CliRefusedBoundaryError) as refused:
        require_group_open_to_none(_group(state, rows=rows, stated=stated))
    assert refused.value.translated_message == "cli.config.profile.household.none_with_stored_rows"
    assert refused.value.context == {"state": state.value, "rows": str(rows), "stated_count": stated}
