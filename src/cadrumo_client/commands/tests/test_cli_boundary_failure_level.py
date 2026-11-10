"""A command's terminal failure is logged by kind: faults as errors, served refusals as outcomes."""

from __future__ import annotations

import logging

import pytest

from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.tests.log_records import delivered_records
from cadrumo_client.commands.errors import CliUnexpectedBoundaryError, log_cli_boundary_failure
from cadrumo_client.commands.registered_operation_errors import (
    registered_operation_still_running,
    submitted_operation_error,
)
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


def _refused(
    code: str,
    effect: OperationEffect | None,
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.REFUSED,
) -> Exception:
    return submitted_operation_error("a" * 64, code, terminal_condition=condition, effect=effect)


@pytest.mark.parametrize(
    ("error", "level"),
    [
        (RefusalError(RefusalCode.PEER_UNTRUSTED, check="unit"), logging.ERROR),
        (_refused_by_untrusted_peer(), logging.ERROR),
        (CliUnexpectedBoundaryError(KeyError("unit")), logging.ERROR),
        (FrontendRefusedError("authentication_required"), logging.INFO),
        (_refused("REFUSED_MODELO_PROFILE_READINESS", OperationEffect.NONE), logging.INFO),
        (_refused("REFUSED_RETENCIONES_WINDOW_EMPTY", OperationEffect.NONE), logging.INFO),
        (_refused("REFUSED_MODELO_PROFILE_READINESS", OperationEffect.UNKNOWN), logging.WARNING),
        (_refused("REFUSED_MODELO_PROFILE_READINESS", OperationEffect.UPDATED), logging.WARNING),
        (_refused("REFUSED_MODELO_PROFILE_READINESS", OperationEffect.PARTIAL), logging.WARNING),
        (_refused("REFUSED_MODELO_PROFILE_READINESS", None), logging.WARNING),
        (
            _refused(
                "REFUSED_MODELO_PROFILE_READINESS", OperationEffect.NONE, condition=OperationTerminalCondition.FAILED
            ),
            logging.WARNING,
        ),
        (registered_operation_still_running("a" * 64, OperationEffect.UNKNOWN, None), logging.WARNING),
    ],
    ids=[
        "transport_refusal",
        "caused_by_transport_refusal",
        "internal",
        "admission_refusal_nothing_attempted",
        "refused_no_effect",
        "refused_no_effect_second_code",
        "refused_unknown_effect",
        "refused_updated_effect",
        "refused_partial_effect",
        "refused_effect_not_observed",
        "failed_settlement_with_refusal_code",
        "still_running",
    ],
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
