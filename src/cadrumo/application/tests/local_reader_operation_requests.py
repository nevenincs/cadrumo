"""Build supervised local-reader requests for owning operation tests."""

from __future__ import annotations

from ..browser_runtime_operation import (
    BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
    BROWSER_RUNTIME_OPERATION_SUBJECT,
    BrowserRuntimeProvisionRequest,
)
from ..local_reader_contracts import LOCAL_READER_OPERATION_SUBJECT
from ..local_reader_report import LOCAL_READER_REPORT_OPERATION_DEFINITION_ID, LocalReaderReportRequest
from ..local_reader_status_operation import LOCAL_READER_STATUS_OPERATION_DEFINITION_ID, LocalReaderStatusRequest
from ..operations.models import OperationRequest


def build_browser_runtime_provision_request() -> OperationRequest[BrowserRuntimeProvisionRequest]:
    """Build the request that provisions the browser build automation launches."""
    return OperationRequest(
        definition_id=BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
        subject_ref=BROWSER_RUNTIME_OPERATION_SUBJECT,
        payload=BrowserRuntimeProvisionRequest(),
    )


def build_local_reader_report_request() -> OperationRequest[LocalReaderReportRequest]:
    """Build the request that reads the machine's local-inference report."""
    return OperationRequest(
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderReportRequest(),
    )


def build_local_reader_status_request(*, probe: bool) -> OperationRequest[LocalReaderStatusRequest]:
    """Build the request that reads the machine's reader status, probing fitness when asked."""
    return OperationRequest(
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderStatusRequest(probe=probe),
    )
