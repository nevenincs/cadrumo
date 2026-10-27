"""A command's terminal failure is logged by kind: faults as errors, expected refusals as warnings."""

from __future__ import annotations

import logging

import pytest

from cadrumo.tests.log_records import delivered_records
from cadrumo_client.commands.errors import CliUnexpectedBoundaryError, log_cli_boundary_failure
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _refused_by_untrusted_peer() -> Exception:
    try:
        try:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="unit")
        except RefusalError as transport:
            raise FrontendRefusedError("authentication_required") from transport
    except FrontendRefusedError as error:
        return error


@pytest.mark.parametrize(
    ("error", "level"),
    [
        (RefusalError(RefusalCode.PEER_UNTRUSTED, check="unit"), logging.ERROR),
        (_refused_by_untrusted_peer(), logging.ERROR),
        (CliUnexpectedBoundaryError(KeyError("unit")), logging.ERROR),
        (FrontendRefusedError("authentication_required"), logging.WARNING),
    ],
    ids=["transport_refusal", "caused_by_transport_refusal", "internal", "state_refusal"],
)
def test_terminal_failure_level_follows_its_kind(
    caplog: pytest.LogCaptureFixture, error: Exception, level: int
) -> None:
    with caplog.at_level(logging.DEBUG):
        trace_id = log_cli_boundary_failure("unit_cli", error, durable=False)

    (record,) = [
        record for record in delivered_records(caplog) if getattr(record, "failure_boundary", None) == "unit_cli"
    ]
    assert record.levelno == level
    assert record.__dict__["trace_id"] == trace_id
