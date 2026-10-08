"""Retained-profile read executors enforce identity before phase or port access."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ...operations import profile_guard
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import (
    check_operation as check,
)
from .. import (
    history_operation as history,
)
from .. import (
    list_operation as list_ledger,
)
from .. import (
    participation_operation as participation,
)
from .. import (
    preflight_operation as preflight,
)
from .. import (
    review_operation as review,
)
from .. import (
    status_operation as status,
)
from .. import (
    track_operation as track,
)
from .. import (
    view_operation as view,
)
from .profile_identity_operation_support import (
    PortFactoryProbe,
    RetainedProfileFactoryReachedError,
    execution_context,
    unexpected_active_profile_lookup,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")


@dataclass(frozen=True)
class _ReadCase:
    name: str
    request: OperationRequest[BaseModel]
    build_executor: Callable[[PortFactoryProbe], Any]


def _request(definition_id: str, payload: BaseModel) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        payload=payload,
    )


def _read_cases() -> tuple[_ReadCase, ...]:
    period = PublicPeriod.from_period(Period.from_year_and_code(2026, "1T"))
    return (
        _ReadCase(
            "check",
            _request(check.LEDGER_CHECK_OPERATION_DEFINITION_ID, check.LedgerCheckRequest(profile_id=_PROFILE_ID)),
            lambda ports: check.LedgerCheckExecutor(cast(Any, ports)),
        ),
        _ReadCase(
            "history",
            _request(
                history.LEDGER_HISTORY_OPERATION_DEFINITION_ID,
                history.LedgerHistoryRequest(profile_id=_PROFILE_ID, transaction_prefix="a" * 12),
            ),
            lambda ports: history.LedgerHistoryExecutor(cast(Any, ports)),
        ),
        _ReadCase(
            "list",
            _request(
                list_ledger.LEDGER_LIST_OPERATION_DEFINITION_ID, list_ledger.LedgerListRequest(profile_id=_PROFILE_ID)
            ),
            lambda ports: list_ledger.LedgerListExecutor(cast(Any, ports)),
        ),
        _ReadCase(
            "participation",
            _request(
                participation.LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
                participation.LedgerParticipationRequest(profile_id=_PROFILE_ID, transaction_prefix="a" * 12),
            ),
            lambda ports: participation.LedgerParticipationExecutor(cast(Any, ports), cast(Any, ports)),
        ),
        _ReadCase(
            "preflight",
            _request(
                preflight.LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
                preflight.LedgerPreflightRequest(profile_id=_PROFILE_ID, period=period),
            ),
            lambda ports: preflight.LedgerPreflightExecutor(cast(Any, ports)),
        ),
        _ReadCase(
            "review",
            _request(review.LEDGER_REVIEW_OPERATION_DEFINITION_ID, review.LedgerReviewRequest(profile_id=_PROFILE_ID)),
            lambda ports: review.LedgerReviewExecutor(cast(Any, ports)),
        ),
        _ReadCase(
            "view",
            _request(
                view.LEDGER_VIEW_OPERATION_DEFINITION_ID,
                view.LedgerViewRequest(profile_id=_PROFILE_ID, transaction_prefix="a" * 12),
            ),
            lambda ports: view.LedgerViewExecutor(cast(Any, ports)),
        ),
        _ReadCase(
            "status",
            _request(status.LEDGER_STATUS_OPERATION_DEFINITION_ID, status.LedgerStatusRequest(profile_id=_PROFILE_ID)),
            lambda ports: status.LedgerStatusExecutor(cast(Any, ports), cast(Any, ports)),
        ),
        _ReadCase(
            "track",
            _request(
                track.LEDGER_TRACK_OPERATION_DEFINITION_ID,
                track.LedgerTrackRequest(profile_id=_PROFILE_ID, transaction_prefix="a" * 12),
            ),
            lambda ports: track.LedgerTrackExecutor(cast(Any, ports), cast(Any, ports)),
        ),
    )


_READ_CASES = _read_cases()


@pytest.mark.parametrize("case", _READ_CASES, ids=lambda case: case.name)
@pytest.mark.parametrize("defect", ("request_definition", "request_target", "executor_definition", "executor_subject"))
@pytest.mark.asyncio
async def test_read_executor_refuses_identity_mismatch_before_phase_or_port_access(
    monkeypatch: pytest.MonkeyPatch,
    case: _ReadCase,
    defect: str,
) -> None:
    request = case.request
    identity_definition: str | None = None
    identity_subject: str | None = None
    if defect == "request_definition":
        request = request.model_copy(update={"definition_id": "ledger.read.unexpected"})
    elif defect == "request_target":
        request = request.model_copy(update={"subject_ref": profile_operation_subject(str(_OTHER_PROFILE_ID))})
    elif defect == "executor_definition":
        identity_definition = "ledger.read.unexpected"
    else:
        identity_subject = profile_operation_subject(str(_OTHER_PROFILE_ID))

    context, events = execution_context(
        request,
        definition_id=identity_definition,
        subject_ref=identity_subject,
    )
    provider = PortFactoryProbe(profile_id=_PROFILE_ID)
    monkeypatch.setattr(
        profile_guard,
        "require_active_bucket_id",
        unexpected_active_profile_lookup,
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await case.build_executor(provider).execute(request, context)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert events.codes == []
    assert provider.calls == []


@pytest.mark.parametrize("case", _READ_CASES, ids=lambda case: case.name)
@pytest.mark.asyncio
async def test_valid_identity_reaches_exact_profile_ports_without_active_pointer_gate(
    monkeypatch: pytest.MonkeyPatch,
    case: _ReadCase,
) -> None:
    context, events = execution_context(case.request)
    provider = PortFactoryProbe(profile_id=_PROFILE_ID)
    monkeypatch.setattr(
        profile_guard,
        "require_active_bucket_id",
        unexpected_active_profile_lookup,
    )

    with pytest.raises(RetainedProfileFactoryReachedError):
        await case.build_executor(provider).execute(case.request, context)

    assert events.codes == [case.request.definition_id]
    assert len(provider.calls) == 1
    assert provider.calls[0]["bucket_id"] == str(_PROFILE_ID)
    assert provider.calls[0]["operation"] is context.authority_operation
