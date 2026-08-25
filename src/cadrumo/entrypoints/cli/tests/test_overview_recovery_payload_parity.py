"""CLI transport for typed overdue recovery facts and actions.

The domain :class:`Recovery` carries only the Ley 58/2003 art-27 legal facts.
The overview application layer declares the ``operator.modelo.work.create``
catalogue action from the resolved modelo, filing year, and period, and this
CLI boundary resolves it against the live command surface before serializing
the recovery payload.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....application.overview import (
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarRange,
    OverviewPeriodState,
    declare_next_action,
)
from ....core import STR_KEYED_MAPPING_ADAPTER, Period
from ....domain.deadlines import ObligationStatus, RecargoBand, Recovery
from .._overview_payloads import OverviewCalendarEntryPayload, OverviewRecoveryPayload
from .._overview_rendering import _resolved_action, overview_calendar_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _canonical_recovery() -> Recovery:
    """A real overdue recovery containing only legal recargo facts."""
    return Recovery(
        still_filable=True,
        recargo_band=RecargoBand(
            id="completed_months_0",
            min_completed_months=0,
            max_completed_months=3,
            surcharge_pct=Decimal("1.00"),
            interest_applies=False,
            legal_ref="ley-58-2003:art-27.2",
        ),
    )


def _declared_recovery_action():
    return declare_next_action(
        "operator.modelo.work.create",
        modelo="303",
        year=2025,
        period="1T",
    )


def _recovery_json() -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_python(_canonical_recovery().model_dump(mode="json"))


def _recovery_payload_json() -> dict[str, object]:
    next_action = _resolved_action(_declared_recovery_action())
    assert next_action is not None
    return {
        **_recovery_json(),
        "next_action": next_action,
    }


def _recargo_band_json() -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_python(_canonical_recovery().recargo_band.model_dump(mode="json"))


def test_canonical_legal_recovery_projects_with_a_resolved_action() -> None:
    """Legal facts cross unchanged; executable identity comes from the resolver."""
    payload = OverviewRecoveryPayload.model_validate(_recovery_payload_json())

    assert payload.still_filable is True
    assert payload.recargo_band.id == "completed_months_0"
    assert payload.recargo_band.legal_ref == "ley-58-2003:art-27.2"
    assert payload.recargo_band.surcharge_pct == "1.00"
    assert payload.recargo_band.min_completed_months == 0
    assert payload.recargo_band.max_completed_months == 3
    assert payload.recargo_band.interest_applies is False
    assert payload.next_action.action.action_id == "operator.modelo.work.create"
    assert payload.next_action.action.target_command_key == "modelo.work.create"
    assert payload.next_action.action.cli_path == ("app", "modelo", "work", "create")
    assert {binding.argument_name: binding.value for binding in payload.next_action.argument_bindings} == {
        "modelo": "303",
        "year": 2025,
        "period": "1T",
    }


def test_payload_contains_all_legal_recovery_fields_and_only_its_resolved_action() -> None:
    """The CLI adds resolution; it does not reconstruct domain legal facts."""
    assert set(OverviewRecoveryPayload.model_fields) == {
        *Recovery.model_fields,
        "next_action",
    }


def test_payload_mirrors_every_canonical_recargo_band_field() -> None:
    """Same contract for the nested band that carries the legal grounding."""
    from .._overview_payloads import OverviewRecargoBandPayload

    assert set(RecargoBand.model_fields) - set(OverviewRecargoBandPayload.model_fields) == set()


def test_an_empty_recovery_mapping_is_refused() -> None:
    """An overdue entry cannot serialize without legal facts and an action."""
    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate({})


@pytest.mark.parametrize("dropped", ["recargo_band", "next_action"])
def test_a_recovery_missing_a_required_payload_part_is_refused(dropped: str) -> None:
    """Neither the legal band nor the resolved continuation is optional."""
    payload = {key: value for key, value in _recovery_payload_json().items() if key != dropped}

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(payload)


@pytest.mark.parametrize("dropped", ["id", "surcharge_pct", "legal_ref"])
def test_a_band_missing_its_grounding_is_refused(dropped: str) -> None:
    """A band without its identity, rate, or legal reference is not a band."""
    payload = {
        **_recovery_payload_json(),
        "recargo_band": {key: value for key, value in _recargo_band_json().items() if key != dropped},
    }

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(payload)


def test_an_unresolved_action_and_retired_raw_command_are_refused() -> None:
    """The wire contract accepts only a resolver-owned action projection."""
    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate({**_recovery_json(), "next_action": {}})

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(
            {
                **_recovery_payload_json(),
                "next_command": "retired",
            },
        )


def test_calendar_entry_recovery_is_the_typed_payload_not_a_bare_mapping() -> None:
    """The entry field must be the typed projection, so the guarantees apply."""
    annotation = OverviewCalendarEntryPayload.model_fields["recovery"].annotation

    assert annotation is not None
    assert OverviewRecoveryPayload in getattr(annotation, "__args__", (annotation,))


def test_cli_calendar_resolves_the_application_overdue_declaration() -> None:
    """Only the CLI boundary materializes the application's catalogue declaration."""
    period = Period.from_year_and_code(2025, "1T")
    calendar_range = OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20))
    entry = OverviewCalendarEntry(
        modelo="303",
        period=period,
        opens_on=date(2025, 4, 1),
        closes_on=date(2025, 4, 20),
        adjusted_closes_on=date(2025, 4, 21),
        shift_reason="weekend",
        status=ObligationStatus.OVERDUE,
        user_state=OverviewPeriodState.LATE,
        recovery=_canonical_recovery(),
        recovery_action=_declared_recovery_action(),
        filing_year=2025,
    )
    calendar = OverviewCalendar(
        range=calendar_range,
        entries=(entry,),
        generated_at=datetime(2025, 5, 1, tzinfo=UTC),
    )

    result, _, _ = overview_calendar_output(calendar, calendar_range, evidence_notices=())
    recovery = result.entries[0].recovery

    assert recovery is not None
    assert recovery.next_action.action.action_id == "operator.modelo.work.create"
    assert recovery.next_action.action.cli_path == ("app", "modelo", "work", "create")
    assert {binding.argument_name: binding.value for binding in recovery.next_action.argument_bindings} == {
        "modelo": "303",
        "year": 2025,
        "period": "1T",
    }


def test_a_not_overdue_entry_may_still_carry_no_recovery() -> None:
    """Only OVERDUE rows resolve a recovery; ``None`` stays legitimate."""
    assert OverviewRecoveryPayload.model_validate(_recovery_payload_json()) is not None
    assert OverviewCalendarEntryPayload.model_fields["recovery"].default is None
