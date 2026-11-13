"""The letting start of a property: unstated, a stated date or never let, and its order against the leases."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..inmueble_facts import inmueble_from_row, inmueble_row_values
from ..inmueble_record import require_letting_start_before_leases

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

YEAR = filing_year_envelope().horizon
_BASE = {"situacion": "5"}
_START = date(YEAR - 2, 6, 1)


def _leaf(error: ProfileAnswerTypeError) -> object:
    return (error.context or {}).get("key")


def test_an_unstated_start_is_neither_a_date_nor_never_let() -> None:
    record = inmueble_from_row(0, _BASE)

    assert record.arrendado_desde is None
    assert record.sin_arrendar is False
    assert "arrendado_desde" not in inmueble_row_values(record)
    assert "sin_arrendar" not in inmueble_row_values(record)


def test_a_stated_date_round_trips() -> None:
    record = inmueble_from_row(0, _BASE | {"arrendado_desde": _START.isoformat()})

    assert record.arrendado_desde == _START
    assert inmueble_row_values(record)["arrendado_desde"] == _START.isoformat()
    assert inmueble_from_row(0, inmueble_row_values(record)) == record


def test_never_let_is_stored_only_as_true_and_false_is_the_unstated_state() -> None:
    never = inmueble_from_row(0, _BASE | {"sin_arrendar": "true"})
    assert never.sin_arrendar is True
    assert inmueble_row_values(never)["sin_arrendar"] == "true"

    unstated = inmueble_from_row(0, _BASE | {"sin_arrendar": "false"})
    assert unstated.sin_arrendar is False
    assert "sin_arrendar" not in inmueble_row_values(unstated)


def test_a_date_and_never_let_together_are_refused() -> None:
    with pytest.raises(ProfileAnswerTypeError) as refusal:
        inmueble_from_row(0, _BASE | {"arrendado_desde": _START.isoformat(), "sin_arrendar": "true"})
    assert _leaf(refusal.value) == "arrendado_desde"


def test_a_badly_written_date_is_refused_naming_the_leaf() -> None:
    with pytest.raises(ProfileAnswerTypeError) as refusal:
        inmueble_from_row(0, _BASE | {"arrendado_desde": "June 2023"})
    assert _leaf(refusal.value) == "arrendado_desde"


def test_a_start_not_later_than_every_lease_start_is_accepted() -> None:
    record = inmueble_from_row(0, _BASE | {"arrendado_desde": _START.isoformat()})

    require_letting_start_before_leases(record, (_START, date(YEAR - 1, 1, 1)))
    require_letting_start_before_leases(record, ())


def test_a_start_later_than_any_one_lease_start_is_refused() -> None:
    record = inmueble_from_row(0, _BASE | {"arrendado_desde": _START.isoformat()})

    with pytest.raises(ProfileAnswerTypeError) as refusal:
        require_letting_start_before_leases(record, (date(YEAR - 1, 1, 1), date(YEAR - 3, 1, 1)))
    assert _leaf(refusal.value) == "arrendado_desde"


def test_the_earliest_lease_start_does_not_stand_in_for_an_unstated_start() -> None:
    record = inmueble_from_row(0, _BASE)

    require_letting_start_before_leases(record, (_START,))
    assert record.arrendado_desde is None


def test_a_lease_of_a_property_stated_never_let_is_refused() -> None:
    record = inmueble_from_row(0, _BASE | {"sin_arrendar": "true"})

    with pytest.raises(ProfileAnswerTypeError) as refusal:
        require_letting_start_before_leases(record, (_START,))
    assert _leaf(refusal.value) == "sin_arrendar"
