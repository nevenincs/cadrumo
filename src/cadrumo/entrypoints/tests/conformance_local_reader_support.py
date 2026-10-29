"""Registered-executor conformance scenarios for the machine's reader status and report.

Neither asks a local AI server. The status judges each role's selected lane
from the stored selections; a test profile selects no model, so no role is
ready and the reader falls back to text layers alone.
"""

from __future__ import annotations

from ...application.local_reader import LocalReaderDocumentReadiness
from ...application.local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportPublicResultV1,
)
from ...application.local_reader_status_operation import (
    LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
    LocalReaderStatusPublicResultV1,
)
from ...application.tests.local_reader_operation_requests import (
    build_local_reader_report_request,
    build_local_reader_status_request,
)
from ...core.operations import OperationEffect, OperationTerminalCondition
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare_status() -> ConformancePreparation:
    request = build_local_reader_status_request()

    def verify(outcome: ConformanceOutcome) -> None:
        status = outcome.resolve_result(LocalReaderStatusPublicResultV1)
        assert status.roles, "every reader role is reported, ready or not"
        assert all(not role.ready for role in status.roles)
        assert all(role.failed_condition_id is not None for role in status.roles)
        assert status.extraction_ready is False
        assert status.document_readiness is LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        assert status.text_layer_model_fill_available is False

    return ConformancePreparation(subject_ref=request.subject_ref, request=request.payload, verify=verify)


def _prepare_report() -> ConformancePreparation:
    request = build_local_reader_report_request()

    def verify(outcome: ConformanceOutcome) -> None:
        report = outcome.resolve_result(LocalReaderReportPublicResultV1)
        assert report.models, "every reader role's selection is reported"

    return ConformancePreparation(subject_ref=request.subject_ref, request=request.payload, verify=verify)


_PREPARATIONS = {
    LOCAL_READER_STATUS_OPERATION_DEFINITION_ID: _prepare_status,
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID: _prepare_report,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARATIONS.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(f"no local reader conformance scenario for {context.definition.definition_id}")
    return prepare()


LOCAL_READER_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
