"""What stops a read is answered as a refusal, and only a read is.

The refusal for each kind of fault and the requests that count as reads are
decided by the worker's own dispatch functions, called here directly. That a
refused read leaves the worker serving is proven against a real runtime where
a subject can be made to vanish.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.errors.error_codes import build_error_envelope
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.period import Period, PeriodError
from cadrumo.core.request_faults import RequestFault
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import OperationManagementRequest
from cadrumo_client.contracts.projection_pages import ProjectionPageRequest
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerManageRequest,
    ProfileWorkerObserveRequest,
    ProfileWorkerOperationRequest,
    ProfileWorkerProjectPageRequest,
    ProfileWorkerProjectRequest,
    ProfileWorkerResumeRequest,
)

from ..worker_operation_requests import _is_read, read_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PRIVATE_TEXT = "synthetic-private-text-9d02"
_OPERATION = "a" * 64
_INTERACTION = "b" * 64
_DIGEST = sha256_hex(b"synthetic definition contract")


class _Synthetic(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    member: int


def _schema() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(schema_id="synthetic.read", schema_version=1, model_type=_Synthetic)


_EXTERNAL_CLIENT = OperationFrontendProjection.EXTERNAL_CLIENT


def _manage(management: OperationManagementRequest) -> ProfileWorkerManageRequest:
    return ProfileWorkerManageRequest(
        request_id=uuid4(), session_id=uuid4(), frontend=_EXTERNAL_CLIENT, management=management
    )


def _response(kind: type[OperationResponseControlRequestV1]) -> OperationResponseControlRequestV1:
    fields: dict[str, object] = {
        "operation_id": _OPERATION,
        "interaction_id": _INTERACTION,
        "revision": 0,
        "actor_ref": f"session:{uuid4()}",
    }
    if kind is not OperationResponseControlRequestV1:
        fields["responded_at"] = now()
    return kind.model_validate(fields)


def test_a_registered_error_is_answered_with_the_code_and_message_the_command_line_prints() -> None:
    with pytest.raises(PeriodError) as raised:
        Period.from_year_and_code(2025, "evento")
    printed = build_error_envelope(raised.value)

    refusal = read_refusal(raised.value)

    assert isinstance(refusal, AutomationCustodyError)
    assert refusal.reason is AutomationCustodyCode.INVALID
    assert refusal.request_faults == (RequestFault(location=(), type=printed.code, message=printed.message),)


@pytest.mark.parametrize("fault_type", [ValueError, KeyError, LookupError, IndexError, TypeError])
def test_an_unregistered_fault_is_answered_with_the_generic_refusal_and_only_its_type_is_logged(
    fault_type: type[Exception], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        refusal = read_refusal(fault_type(_PRIVATE_TEXT))

    assert isinstance(refusal, ProfileAccessRefusedError)
    assert refusal.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert _PRIVATE_TEXT not in str(refusal)
    logged = [record.getMessage() for record in caplog.records]
    assert logged == [f"worker read stopped by an unexpected fault exception_type={fault_type.__name__}"]


def test_a_typed_refusal_a_model_refusal_and_a_fault_of_the_channel_are_left_as_they_are() -> None:
    with pytest.raises(ValidationError) as unread:
        _Synthetic.model_validate({"member": "synthetic"})
    untouched: tuple[Exception, ...] = (
        AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE),
        ProfileAccessRefusedError(AccessDenialCode.DISCLOSURE_DENIED),
        unread.value,
        RefusalError(RefusalCode.CONNECTION_CLOSED),
        OSError("synthetic channel fault"),
        RuntimeError("synthetic unexpected fault"),
    )

    assert [read_refusal(fault) for fault in untouched] == [None] * len(untouched)


def test_an_observation_a_projection_a_page_and_the_inspection_of_a_review_are_the_reads() -> None:
    result = OperationResultProjectionRequestV1(
        operation_id=_OPERATION, terminal_revision=1, definition_contract_digest=_DIGEST, result_schema=_schema()
    )
    review = OperationReviewProjectionRequestV1(
        reference=OperationReviewProjectionReferenceV1(
            operation_id=_OPERATION,
            interaction_id=_INTERACTION,
            revision=1,
            review_projection_schema=_schema(),
            definition_contract_digest=_DIGEST,
            expires_at=None,
        )
    )
    reads: tuple[BaseModel, ...] = (
        ProfileWorkerObserveRequest(
            request_id=uuid4(),
            session_id=uuid4(),
            frontend=_EXTERNAL_CLIENT,
            observation=OperationObservationRequestV1(operation_id=_OPERATION, after_cursor=0, page_limit=8),
        ),
        ProfileWorkerProjectRequest(
            request_id=uuid4(), session_id=uuid4(), frontend=_EXTERNAL_CLIENT, projection=result
        ),
        ProfileWorkerProjectRequest(
            request_id=uuid4(), session_id=uuid4(), frontend=_EXTERNAL_CLIENT, projection=review
        ),
        ProfileWorkerProjectPageRequest(
            request_id=uuid4(),
            session_id=uuid4(),
            frontend=_EXTERNAL_CLIENT,
            projection=result,
            page=ProjectionPageRequest(),
        ),
        _manage(_response(OperationResponseControlRequestV1)),
    )
    acts: tuple[BaseModel, ...] = (
        _manage(_response(OperationResponseApplyRequestV1)),
        _manage(_response(OperationResponseRejectRequestV1)),
        _manage(OperationCancellationRequestV1(operation_id=_OPERATION, expected_revision=0)),
        _manage(OperationDetachRequestV1(operation_id=_OPERATION, expected_revision=0)),
        ProfileWorkerOperationRequest(
            request_id=uuid4(), session_id=uuid4(), frontend=_EXTERNAL_CLIENT, operation_id=_OPERATION
        ),
        ProfileWorkerResumeRequest(
            request_id=uuid4(), session_id=uuid4(), frontend=_EXTERNAL_CLIENT, operation_id=_OPERATION
        ),
    )

    assert [_is_read(request) for request in reads] == [True] * len(reads)
    assert [_is_read(request) for request in acts] == [False] * len(acts)
    # A request read back from its wire document is classified as the one that was sent.
    assert [_is_read(type(request).model_validate_json(request.model_dump_json())) for request in (*reads, *acts)] == [
        *([True] * len(reads)),
        *([False] * len(acts)),
    ]
