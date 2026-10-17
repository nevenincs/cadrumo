"""A command that ends refused logs its failure as an error, not as information."""

from __future__ import annotations

import logging

import pytest

from cadrumo_client.commands.errors import CliUnexpectedBoundaryError, log_cli_boundary_failure
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "error",
    [
        RefusalError(RefusalCode.PEER_UNTRUSTED, check="runtime_peer_untrusted"),
        CliUnexpectedBoundaryError(KeyError("unit")),
    ],
    ids=["refusal", "internal"],
)
def test_every_terminal_failure_is_logged_at_error(caplog: pytest.LogCaptureFixture, error: Exception) -> None:
    with caplog.at_level(logging.DEBUG):
        trace_id = log_cli_boundary_failure("unit_cli", error, durable=False)

    (record,) = [record for record in caplog.records if getattr(record, "failure_boundary", None) == "unit_cli"]
    assert record.levelno == logging.ERROR
    assert record.__dict__["trace_id"] == trace_id
