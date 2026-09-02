"""What the out-of-process full-screen session protocol accepts and refuses.

The protocol is the only thing two entrypoint packages share, and neither may
import the other, so its round trips and its refusals are the whole guarantee
that a request written on one side is read the same way on the other.

Every case here exercises the real render and parse functions. There is
nothing to mock: the protocol is pure text in and typed values out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..full_screen_session_protocol import (
    DESTINATION_OPTION,
    OUTCOME_FILE_OPTION,
    SELF_TEST_FLAG,
    FullScreenDestination,
    FullScreenOutcomeKind,
    FullScreenSessionOutcome,
    FullScreenSessionProtocolError,
    FullScreenSessionRequest,
    parse_outcome,
    parse_request_arguments,
    render_outcome,
    render_request_arguments,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _request(
    *,
    destination: FullScreenDestination = FullScreenDestination.MODELO_WORK_SELECT,
    work_unit_id: str | None = None,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    output_language: str | None = None,
    self_test: bool = False,
) -> FullScreenSessionRequest:
    """Build a complete request whose varying fields the case names."""
    return FullScreenSessionRequest(
        destination=destination,
        outcome_file=Path("outcome.json"),
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        include_discarded=include_discarded,
        output_language=output_language,
        self_test=self_test,
    )


@pytest.mark.parametrize(
    "request_",
    [
        _request(),
        _request(destination=FullScreenDestination.MODELO_WORK_REVIEW, work_unit_id="a" * 64),
        _request(bucket_id="bucket-one", include_discarded=True),
        _request(output_language="es", self_test=True),
        _request(work_unit_id="b" * 64, bucket_id="bucket-two", output_language="en", include_discarded=True),
    ],
)
def test_a_rendered_request_parses_back_to_the_same_request(request_: FullScreenSessionRequest) -> None:
    """Every field survives the crossing, including the absent ones."""
    assert parse_request_arguments(render_request_arguments(request_)) == request_


def test_arguments_without_a_destination_are_the_root_session_rather_than_an_error() -> None:
    """A bare invocation and a self-test both request the root session."""
    assert parse_request_arguments([]) is None
    assert parse_request_arguments([SELF_TEST_FLAG]) is None


@pytest.mark.parametrize(
    "arguments",
    [
        [DESTINATION_OPTION],
        [DESTINATION_OPTION, "modelo.work.select"],
        [DESTINATION_OPTION, "modelo.work.invented", OUTCOME_FILE_OPTION, "outcome.json"],
        [DESTINATION_OPTION, "modelo.work.select", OUTCOME_FILE_OPTION, "outcome.json", "--invented"],
        [
            DESTINATION_OPTION,
            "modelo.work.select",
            DESTINATION_OPTION,
            "modelo.work.review",
            OUTCOME_FILE_OPTION,
            "outcome.json",
        ],
    ],
    ids=["no-destination-value", "no-outcome-file", "unknown-destination", "unknown-option", "repeated-option"],
)
def test_an_incomplete_or_unrecognised_request_is_refused(arguments: list[str]) -> None:
    """A child that guessed would open a surface nobody asked for."""
    with pytest.raises(FullScreenSessionProtocolError):
        parse_request_arguments(arguments)


@pytest.mark.parametrize(
    "outcome",
    [
        FullScreenSessionOutcome(kind=FullScreenOutcomeKind.CANCELLED),
        FullScreenSessionOutcome(kind=FullScreenOutcomeKind.COMPLETED, work_unit_id="c" * 64),
        FullScreenSessionOutcome(kind=FullScreenOutcomeKind.SELECTED, work_unit_id="d" * 64),
        FullScreenSessionOutcome(
            kind=FullScreenOutcomeKind.NOT_ADMITTED,
            work_unit_id="e" * 64,
            detail="Añada el período\ty el ejercicio\nantes de reintentar",
        ),
    ],
)
def test_a_rendered_outcome_parses_back_to_the_same_outcome(outcome: FullScreenSessionOutcome) -> None:
    """Localized detail carrying its own tabs and newlines survives intact.

    The record has to hold operator-facing prose without that prose being
    mistaken for record structure, which is the reason it is not written in
    the product's tab-separated line grammar.
    """
    assert parse_outcome(render_outcome(outcome)) == outcome


@pytest.mark.parametrize(
    "record",
    [
        "not a record at all",
        '["selected"]',
        "{}",
        '{"outcome": "invented"}',
        '{"outcome": "selected", "invented": 1}',
        '{"outcome": "selected", "work_unit_id": 7}',
    ],
    ids=["unreadable", "not-a-record", "no-outcome", "unknown-outcome", "unknown-field", "non-text-field"],
)
def test_an_outcome_record_this_protocol_does_not_define_is_refused(record: str) -> None:
    """A malformed record must not read as some nearby valid outcome."""
    with pytest.raises(FullScreenSessionProtocolError):
        parse_outcome(record)
