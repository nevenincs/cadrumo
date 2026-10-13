"""Registered-executor conformance scenarios for the machine's reader status, report and browser build.

None of the three may reach a live model runtime or download a browser, so the
family closes the runtime's endpoint and points browser provisioning at a
cache of its own that already holds every pinned build.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from ...application.browser_runtime_operation import (
    BROWSER_RUNTIME_EXECUTE_PHASE,
    BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
    BROWSER_RUNTIME_PREFLIGHT_PHASE,
    BROWSER_RUNTIME_SETTLEMENT_PHASE,
    BrowserRuntimeProvisionPublicResultV1,
)
from ...application.local_reader_contracts import local_reader_fact_mapping
from ...application.local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportPublicResultV1,
)
from ...application.local_reader_status_operation import (
    LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
    LocalReaderStatusPublicResultV1,
)
from ...application.provisioning_browser import required_browser_builds
from ...application.tests.local_reader_operation_requests import (
    build_browser_runtime_provision_request,
    build_local_reader_report_request,
    build_local_reader_status_request,
)
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...tests.env_scope import scoped_env_var
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


@contextmanager
def _complete_browser_cache() -> Generator[None]:
    """Point browser provisioning at a private cache holding every build the installed Playwright pins.

    The environment setting outranks every other source of the cache
    location, so it is the one that keeps a run off the host's real cache.
    """
    builds = required_browser_builds()
    assert builds is not None, "the installed Playwright pins its Chromium builds"
    with TemporaryDirectory(prefix="cadrumo-conformance-browsers-") as directory:
        for build in builds:
            extracted = Path(directory) / build.directory_name
            extracted.mkdir()
            (extracted / "INSTALLATION_COMPLETE").write_bytes(b"")
        with scoped_env_var("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", directory):
            yield


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


def _prepare_browser() -> ConformancePreparation:
    request = build_browser_runtime_provision_request()

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(BrowserRuntimeProvisionPublicResultV1)
        assert (result.installed, result.already_installed) == (True, True)
        assert result.installer_exit_code is None
        assert (result.verdict_condition_id, result.verdict_facts) == (None, ())
        facts = local_reader_fact_mapping(result.facts)
        assert facts["chromium_installed"] is True
        assert "installer_ran" not in facts

    return ConformancePreparation(subject_ref=request.subject_ref, request=request.payload, verify=verify)


_PREPARATIONS = {
    LOCAL_READER_STATUS_OPERATION_DEFINITION_ID: _prepare_status,
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID: _prepare_report,
    BROWSER_RUNTIME_OPERATION_DEFINITION_ID: _prepare_browser,
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
        # A complete cache runs no installer, so the run settles without an effect.
        RegisteredExecutorConformanceCase(
            BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (BROWSER_RUNTIME_PREFLIGHT_PHASE, BROWSER_RUNTIME_EXECUTE_PHASE, BROWSER_RUNTIME_SETTLEMENT_PHASE),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
    host_environment=_complete_browser_cache,
)
