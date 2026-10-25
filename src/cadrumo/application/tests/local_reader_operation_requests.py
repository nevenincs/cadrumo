"""Build supervised local-reader requests for owning operation tests."""

from __future__ import annotations

from ...core.external_constants import OutputLanguage
from ...core.model_catalogue import ModelRole
from ..local_reader_contracts import (
    LOCAL_READER_OPERATION_DEFINITION_ID,
    LOCAL_READER_OPERATION_SUBJECT,
    LocalReaderProvisionAction,
    LocalReaderProvisionRequest,
)
from ..local_reader_report import LOCAL_READER_REPORT_OPERATION_DEFINITION_ID, LocalReaderReportRequest
from ..local_reader_status_operation import LOCAL_READER_STATUS_OPERATION_DEFINITION_ID, LocalReaderStatusRequest
from ..operations.models import OperationRequest


def build_local_reader_report_request() -> OperationRequest[LocalReaderReportRequest]:
    """Build the request that reads the machine's local-inference report."""
    return OperationRequest(
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderReportRequest(),
    )


def build_local_reader_status_request() -> OperationRequest[LocalReaderStatusRequest]:
    """Build the request that reads the machine's reader status."""
    return OperationRequest(
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderStatusRequest(),
    )


def build_local_reader_verify_request(
    role: ModelRole | None = None,
    model: str | None = None,
    *,
    output_language: OutputLanguage | None = None,
) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that verifies ``role``'s model, a named model, or every role's model."""
    return OperationRequest(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderProvisionRequest(
            action=LocalReaderProvisionAction.VERIFY, role=role, model=model, output_language=output_language
        ),
    )
