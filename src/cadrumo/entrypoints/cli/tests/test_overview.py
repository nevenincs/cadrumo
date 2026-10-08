"""Overview rendering retains its settled receipt and refuses private errors safely."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

import pytest
import typer

from ....application.overview.read_payload import OverviewStatusRead
from ....application.overview.read_projection import OverviewStatusSnapshot
from ....application.overview.read_request import OverviewReadKind, OverviewReadRequest
from ....application.overview.read_result import OverviewReadProjection
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import _overview
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..runtime_overview import OverviewReadCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64


@pytest.fixture
def completed() -> OverviewReadCompletion:
    profile_id = UUID("5aa00000-0000-4000-8000-0000000000aa")
    request = OverviewReadRequest(
        profile_id=profile_id,
        kind=OverviewReadKind.STATUS,
        output_language=OutputLanguage.EN,
    )
    payload = OverviewStatusRead(
        report=OverviewStatusSnapshot(
            active_profile_name="synthetic-profile",
            transactions=0,
            invoices=0,
            drafts=0,
            work_units=0,
            discarded_work_units=0,
            calculation_revisions=0,
            unreadable_rows=0,
            filing_obligation_advisories=(),
            unsupported_work_create_modelos=(),
        )
    )
    projection = OverviewReadProjection(profile_id=profile_id, request=request, payload=payload)
    return OverviewReadCompletion(
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        payload=payload,
    )


def test_overview_returns_successful_rendered_output(completed: OverviewReadCompletion) -> None:
    assert _overview._emit_read(completed, lambda: "rendered overview") == "rendered overview"


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError])
def test_overview_render_failure_keeps_receipt_and_hides_private_exception(
    completed: OverviewReadCompletion,
    error_type: type[Exception],
) -> None:
    private_detail = "synthetic taxpayer 12345678Z amount 9876.54"

    def fail() -> NoReturn:
        raise error_type(private_detail)

    with pytest.raises(CliRefusedBoundaryError) as refusal:
        _overview._emit_read(completed, fail)

    assert refusal.value.context == {
        "operation_id": _OPERATION_ID,
        "reason": RuntimeRefusalCode.UNAVAILABLE.value,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
        "effect": OperationEffect.NONE.value,
    }
    assert private_detail not in str(refusal.value)
    assert refusal.value.__suppress_context__


@pytest.mark.parametrize("error", [typer.Exit(2), CliRefusedBoundaryError(context={"reason": "synthetic refusal"})])
def test_overview_preserves_explicit_cli_refusal_and_exit(
    completed: OverviewReadCompletion,
    error: Exception,
) -> None:
    def fail() -> NoReturn:
        raise error

    with pytest.raises(type(error)) as refusal:
        _overview._emit_read(completed, fail)

    assert refusal.value is error
