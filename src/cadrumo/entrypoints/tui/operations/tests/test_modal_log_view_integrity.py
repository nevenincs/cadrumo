"""The modal's log view refuses a shape that would misread the journal.

``OperationModalLogViewV1`` carries six refusals and none of them had a test.
They are not cosmetic: this view is the operator's only window onto what an
operation actually did, and each refusal marks a way the window could show
something the journal never said.

A view whose ``resynchronized`` flag disagrees with its replay status claims to
have restarted when it did not, or the reverse. One that keeps rows through a
resynchronization shows history the server has told it to discard -- the rows
either side of a compaction are not a continuous record. Rows out of sequence,
or past the cursor they were read up to, present an ordering the journal does
not have.

Every refusal is paired with the same construction succeeding when the shape is
sound, because a validator that rejected everything would satisfy the refusals
while making the log pane unreachable.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....application.operations.frontend_requests import OperationPublicEventPageV1
from .....application.operations.persistence.replay import OperationReplayStatus
from .....core.operations import OperationEventKind
from ..logs import OperationModalLogRowV1, OperationModalLogViewV1, build_initial_log_view, fold_event_page

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64


def _row(sequence: int) -> OperationModalLogRowV1:
    """One projected row; only its sequence matters to these invariants."""
    return OperationModalLogRowV1(
        sequence=sequence,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        kind=OperationEventKind.LOG,
        code="operation.probe",
        severity=None,
        diagnostic_ref=None,
    )


def _view(**overrides: object) -> OperationModalLogViewV1:
    """A sound live view, overridden field by field to state one defect at a time."""
    return OperationModalLogViewV1.model_validate(
        {
            "operation_id": _OPERATION_ID,
            "anchor_cursor": 0,
            "next_cursor": 10,
            "restart_cursor": None,
            "status": OperationReplayStatus.CAUGHT_UP,
            "resynchronized": False,
            "rows": (),
            **overrides,
        },
    )


def test_a_sound_live_view_is_accepted() -> None:
    """The control the refusals need, and the shape the modal actually holds."""
    view = _view(rows=(_row(1), _row(2)))

    assert view.resynchronized is False
    assert [row.sequence for row in view.rows] == [1, 2]


def test_the_resynchronized_flag_must_mirror_the_replay_status() -> None:
    """Claiming a restart that the status does not record misreads the journal."""
    with pytest.raises(ValueError, match="resynchronization flag"):
        _view(resynchronized=True)


def test_a_resynchronizing_view_cannot_keep_its_historical_rows() -> None:
    """Rows either side of a compaction are not one continuous record.

    The server has said the earlier range is gone; showing it beneath the
    restart would present a history the journal can no longer vouch for.
    """
    with pytest.raises(ValueError, match="stale historical rows"):
        _view(
            status=OperationReplayStatus.EXPIRED,
            resynchronized=True,
            restart_cursor=3,
            rows=(_row(1),),
        )


def test_rows_must_be_strictly_ordered_by_sequence() -> None:
    """Out-of-order rows present an ordering the operation never had."""
    with pytest.raises(ValueError, match="strictly ordered"):
        _view(rows=(_row(2), _row(1)))


def test_rows_cannot_run_past_the_cursor_they_were_read_to() -> None:
    """A row beyond `next_cursor` was never in the page that produced it."""
    with pytest.raises(ValueError, match="exceed their own next cursor"):
        _view(next_cursor=1, rows=(_row(5),))


def test_a_resynchronizing_view_with_no_rows_is_accepted() -> None:
    """Resynchronizing is not itself the defect; keeping rows through it is.

    Separating the two stops the refusal above from being read as "a
    compacted log cannot be shown at all", which would blank the pane exactly
    when the operator most needs to know a restart happened.
    """
    view = _view(status=OperationReplayStatus.EXPIRED, resynchronized=True, restart_cursor=3)

    assert view.resynchronized is True
    assert view.rows == ()


def test_the_initial_view_a_modal_starts_from_is_itself_valid() -> None:
    """The one view no page has folded into yet still has to satisfy the rules."""
    view = build_initial_log_view(_OPERATION_ID)

    assert view.rows == ()
    assert view.resynchronized is False
    assert view.status is OperationReplayStatus.CAUGHT_UP


def _page(**overrides: object) -> OperationPublicEventPageV1:
    """A caught-up page carrying no events, overridden one field at a time."""
    return OperationPublicEventPageV1.model_validate(
        {
            "operation_id": _OPERATION_ID,
            "anchor_cursor": 0,
            "requested_cursor": 0,
            "status": OperationReplayStatus.CAUGHT_UP,
            "events": (),
            "next_cursor": 0,
            "restart_cursor": None,
            **overrides,
        },
    )


def test_a_page_from_another_operation_is_refused() -> None:
    """Folding one operation's journal into another's view would invent history."""
    view = build_initial_log_view(_OPERATION_ID)

    with pytest.raises(ValueError, match="different operation"):
        fold_event_page(view, _page(operation_id="b" * 64))


def test_folding_a_resynchronizing_page_clears_the_view_and_keeps_the_restart() -> None:
    """The fold discards prior rows itself rather than relying on the validator.

    The view-level refusal above says such a combination is invalid; this says
    the fold never produces one, and carries the cursor the replay restarts
    from so the pane can say where the gap is.
    """
    view = fold_event_page(
        build_initial_log_view(_OPERATION_ID),
        _page(status=OperationReplayStatus.EXPIRED, anchor_cursor=7, next_cursor=7, restart_cursor=7),
    )

    assert view.resynchronized is True
    assert view.restart_cursor == 7
    assert view.rows == ()


def test_folding_an_ordinary_page_leaves_the_view_sound() -> None:
    """The control: the ordinary path still produces a view the validator accepts."""
    view = fold_event_page(build_initial_log_view(_OPERATION_ID), _page())

    assert view.resynchronized is False
    assert view.rows == ()


def test_a_resynchronizing_page_cannot_reach_the_fold_without_a_restart_cursor() -> None:
    """Why `fold_event_page`'s own restart-cursor guard has no test of its own.

    It is unreachable through a valid page: ``OperationPublicEventPageV1``
    already refuses a resynchronizing page that carries no restart cursor, so
    the fold's check is defensive depth rather than a live branch. Pinning the
    upstream refusal is the honest coverage -- constructing an invalid page to
    reach the inner raise would only prove the model can be bypassed.
    """
    with pytest.raises(ValueError, match="requires one restart cursor"):
        _page(status=OperationReplayStatus.EXPIRED, anchor_cursor=7, next_cursor=7)
