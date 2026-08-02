"""An overdue calendar entry must not lose its recovery obligations in transport.

The canonical :class:`Recovery` requires the resolved
:class:`RecargoBand` -- with its Ley 58/2003 art-27 ``legal_ref`` -- plus the
next command the operator has to run. The CLI entry payload exposed
``recovery`` as a bare ``dict[str, object] | None``, so an empty mapping
validated and serialized as a perfectly good recovery: an overdue row could
reach the operator with its legal grounding and its remedial action absent.

These tests drive the real canonical models through the real payload (no
doubles): a genuine Recovery projects field for field, and every way of
dropping one of its obligations is refused.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.deadlines import RecargoBand, Recovery
from .._overview_payloads import OverviewCalendarEntryPayload, OverviewRecoveryPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _canonical_recovery() -> Recovery:
    """A real overdue recovery, every defaultable field set non-default."""
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
        next_command="aeat app modelo work calculate",
    )


def _recovery_json() -> dict[str, object]:
    return _canonical_recovery().model_dump(mode="json")


def test_canonical_recovery_projects_into_the_payload_field_for_field() -> None:
    """Every canonical field survives the CLI boundary with its value."""
    payload = OverviewRecoveryPayload.model_validate(_recovery_json())

    assert payload.still_filable is True
    assert payload.next_command == "aeat app modelo work calculate"
    assert payload.recargo_band.id == "completed_months_0"
    assert payload.recargo_band.legal_ref == "ley-58-2003:art-27.2"
    assert payload.recargo_band.surcharge_pct == "1.00"
    assert payload.recargo_band.min_completed_months == 0
    assert payload.recargo_band.max_completed_months == 3
    assert payload.recargo_band.interest_applies is False


def test_payload_mirrors_every_canonical_recovery_field() -> None:
    """No canonical recovery field may stop at the CLI boundary."""
    assert set(Recovery.model_fields) - set(OverviewRecoveryPayload.model_fields) == set()


def test_payload_mirrors_every_canonical_recargo_band_field() -> None:
    """Same contract for the nested band that carries the legal grounding."""
    from .._overview_payloads import OverviewRecargoBandPayload

    assert set(RecargoBand.model_fields) - set(OverviewRecargoBandPayload.model_fields) == set()


def test_an_empty_recovery_mapping_is_refused() -> None:
    """The audit's probe: ``recovery={}`` must not serialize as a recovery."""
    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate({})


@pytest.mark.parametrize("dropped", ["recargo_band", "next_command"])
def test_a_recovery_missing_a_legal_obligation_is_refused(dropped: str) -> None:
    """Neither the recargo band nor the operator's next command is optional."""
    payload = _recovery_json()
    del payload[dropped]

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(payload)


@pytest.mark.parametrize("dropped", ["id", "surcharge_pct", "legal_ref"])
def test_a_band_missing_its_grounding_is_refused(dropped: str) -> None:
    """A band without its identity, rate, or legal reference is not a band."""
    payload = _recovery_json()
    band = payload["recargo_band"]
    assert isinstance(band, dict)
    del band[dropped]

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(payload)


def test_a_blank_next_command_is_refused() -> None:
    """An overdue row must carry a runnable action, not an empty string."""
    payload = _recovery_json()
    payload["next_command"] = ""

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(payload)


def test_an_inverted_band_window_is_refused_at_the_boundary_too() -> None:
    """The canonical window invariant holds on the transport shape as well."""
    payload = _recovery_json()
    band = payload["recargo_band"]
    assert isinstance(band, dict)
    band["min_completed_months"] = 6
    band["max_completed_months"] = 3

    with pytest.raises(ValidationError):
        OverviewRecoveryPayload.model_validate(payload)


def test_calendar_entry_recovery_is_the_typed_payload_not_a_bare_mapping() -> None:
    """The entry field must be the typed projection, so the guarantees apply."""
    annotation = OverviewCalendarEntryPayload.model_fields["recovery"].annotation

    assert annotation is not None
    assert OverviewRecoveryPayload in getattr(annotation, "__args__", (annotation,))


def test_a_not_overdue_entry_may_still_carry_no_recovery() -> None:
    """Only OVERDUE rows resolve a recovery; ``None`` stays legitimate."""
    assert OverviewRecoveryPayload.model_validate(_recovery_json()) is not None
    assert OverviewCalendarEntryPayload.model_fields["recovery"].default is None
