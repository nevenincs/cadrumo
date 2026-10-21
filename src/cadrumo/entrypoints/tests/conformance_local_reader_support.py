"""Registered-executor conformance scenarios for the machine's reader status and report.

Neither may reach a live model runtime, so the family closes the runtime's endpoint.
"""

from __future__ import annotations

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
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare_status() -> ConformancePreparation:
    endpoint = load_settings().cadrumo_llm_ollama_chat_url
    request = build_local_reader_status_request(probe=False)

    def verify(outcome: ConformanceOutcome) -> None:
        status = outcome.resolve_result(LocalReaderStatusPublicResultV1)
        assert status.host.reachable is False
        assert status.host.version is None
        assert endpoint.startswith(status.host.endpoint_url.rstrip("/"))
        assert status.host.endpoint_local is True
        assert status.roles, "every reader role is reported, reachable runtime or not"
        assert all(not role.ready for role in status.roles)
        assert status.extraction_ready is False

    return ConformancePreparation(subject_ref=request.subject_ref, request=request.payload, verify=verify)


def _prepare_report() -> ConformancePreparation:
    request = build_local_reader_report_request()

    def verify(outcome: ConformanceOutcome) -> None:
        report = outcome.resolve_result(LocalReaderReportPublicResultV1)
        assert report.runtime_reachable is False
        assert report.residents == ()
        assert report.models, "every reader role's model is reported, reachable runtime or not"
        assert all(not model.resident for model in report.models)

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
    closes_model_runtime=True,
)
