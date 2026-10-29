"""The mapping lane reports a column-naming reader it could not ask, rather than declining.

A table the lane never read must not be described as one whose columns could
not be mapped: that sends the person to edit a file that was never wrong. The
lane carries the reader's verdict on its validation, and detection hands such a
file to the lane so the import can say which component is missing.
"""

from __future__ import annotations

import pytest

from ......application.ledger.column_roles import ColumnRoleReaderUnavailable, bind_column_role_mapping_resolver
from ......application.probe_outcomes import (
    ProbePreconditionCondition,
    probe_no_recovery_verdict,
)
from ......tests.english_locale_fixture import english_locale_fixture
from ......tests.inventory import FIXTURES_DIR
from .._mapped_tabular import MappedTabularProvider
from ..base import InvalidFinancialSourceError
from ..detection import detect_provider

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: An expenses-app export whose header vocabulary no exact provider reads, so
#: detection reaches the mapping lane with it.
_UNREAD_VOCABULARY = FIXTURES_DIR / "financial" / "tabular-dialects" / "expenses_app_export_2026.csv"


def _reader_unavailable() -> ColumnRoleReaderUnavailable:
    """The outcome a composed mapper reports when the role's model is not installed."""
    return ColumnRoleReaderUnavailable(
        precondition_verdict=probe_no_recovery_verdict(
            ProbePreconditionCondition.ROLE_MODEL_INSTALLED,
            facts={"role": "column_role_mapping", "runtime_reachable": True, "role_model_installed": False},
        )
    )


def test_a_reader_that_cannot_be_asked_is_reported_rather_than_declined() -> None:
    unavailable = _reader_unavailable()
    lane = MappedTabularProvider(mapping_resolver=lambda table: unavailable)

    validation = lane.validate_source(_UNREAD_VOCABULARY)

    assert not validation.is_valid
    assert validation.reader_unavailable_verdict == unavailable.precondition_verdict
    assert not any("could not be established" in warning for warning in validation.warnings)
    with pytest.raises(InvalidFinancialSourceError, match="not available"):
        list(lane.ingest(_UNREAD_VOCABULARY))


def test_a_declining_lane_carries_no_reader_verdict() -> None:
    """A mapping that established nothing names no missing component."""
    validation = MappedTabularProvider(mapping_resolver=lambda table: None).validate_source(_UNREAD_VOCABULARY)

    assert not validation.is_valid
    assert validation.reader_unavailable_verdict is None


def test_detection_hands_a_reader_blocked_file_to_its_lane() -> None:
    """The control is the same file under a declining mapper, which no provider claims."""
    unavailable = _reader_unavailable()
    with bind_column_role_mapping_resolver(lambda table: unavailable):
        blocked = detect_provider(_UNREAD_VOCABULARY)
    with bind_column_role_mapping_resolver(lambda table: None):
        declined = detect_provider(_UNREAD_VOCABULARY)

    assert isinstance(blocked, MappedTabularProvider)
    assert declined is None


def test_the_reason_states_the_column_model_is_unavailable() -> None:
    unservable = ColumnRoleReaderUnavailable(
        precondition_verdict=probe_no_recovery_verdict(
            ProbePreconditionCondition.SELECTED_MODEL_AVAILABLE,
            facts={"role": "column_role_mapping", "runtime_reachable": True, "role_model_selected": False},
        )
    )
    lane = MappedTabularProvider(mapping_resolver=lambda table: unservable)

    (reason,) = lane.validate_source(_UNREAD_VOCABULARY).warnings

    assert "column names" in reason
    assert "not available right now" in reason
    with pytest.raises(InvalidFinancialSourceError, match="not available right now"):
        list(lane.ingest(_UNREAD_VOCABULARY))
