"""The Assets fixtures' scenario register is what the real register answers for its steps.

The producer ``native/desktop/frontend/scripts/assets_register.py`` records the replay
into the build tree; these tests replay the committed scenario directly.
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from typing import Any

import pytest

from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from .register_recording_support import committed_scenario, recording, replayed_register

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _recorded() -> dict[str, dict[str, Any]]:
    return recording(*committed_scenario())


def test_every_committed_element_is_recorded_under_its_own_name() -> None:
    _frame, elements = committed_scenario()
    recorded = _recorded()

    assert elements, "no element is committed"
    assert {row["asset_id"] for row in recorded["register"]["list"]} == {item["asset_id"] for item in elements}
    assert set(recorded) == {"register", *(item["asset_id"] for item in elements)}


def test_the_recording_stands_on_the_scenario_day_and_lists_only_admitted_years() -> None:
    frame, _elements = committed_scenario()
    register = _recorded()["register"]

    assert register["today"] == frame["today"]
    assert register["default_year"] in register["years"]
    assert {option["tax_year"] for option in register["form_options"]} == set(register["years"])


def test_a_correction_leaves_the_claim_it_changed_stale() -> None:
    events = _recorded()["servidor"]["events"]

    claims = [event for event in events if event["event_kind"] == "claim_recorded"]
    assert [event["claim"]["stale_reason"] for event in claims] == ["revision_changed"]
    assert not claims[0]["claim"]["matches_current_schedule"]


def test_every_offered_forecast_is_one_the_plan_leaves_open() -> None:
    for asset_id, element in _recorded().items():
        if asset_id == "register":
            continue
        offered = {
            f"{interval['covered_from']}/{interval['covered_until']}"
            for row in element["rows"]
            for interval in row["claimable_intervals"]
        }
        assert set(element["forecasts"]) <= offered, asset_id


def test_the_replay_is_deterministic() -> None:
    assert json.dumps(recording(*committed_scenario()), sort_keys=True) == json.dumps(_recorded(), sort_keys=True)


def test_a_step_that_neither_creates_claims_nor_corrects_is_refused() -> None:
    frame, elements = committed_scenario()
    first = elements[0]
    broken = {**first, "steps": [*first["steps"], {"recorded_at": first["steps"][-1]["recorded_at"], "baja": {}}]}

    with pytest.raises(ValueError, match="a step creates, claims or corrects"):
        replayed_register(frame, (broken,))


def test_a_claim_below_the_first_admitted_year_is_refused() -> None:
    frame, elements = committed_scenario()
    first = elements[0]
    created = first["steps"][0]
    below = min(_recorded()["register"]["years"]) - 1
    early = {
        "recorded_at": created["recorded_at"],
        "claim": {"covered_from": date(below, 1, 1).isoformat(), "covered_through": date(below, 12, 31).isoformat()},
    }

    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        replayed_register(frame, ({**first, "steps": [created, early]},))
