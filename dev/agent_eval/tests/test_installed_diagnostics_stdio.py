"""Installed MCP releases complete canonical reports from an exact-profile worker.

Native credential custody and stdio are real. Enrollment delivery and OS-login
observations use the synthetic controls of the shared encrypted-profile fixture.
No provider requests or telemetry transmissions are performed.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.diagnostics_operation import (
    DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
)
from cadrumo.application.diagnostics_read_contracts import (
    DiagnosticsReadKind,
    DiagnosticsReadProjection,
    DiagnosticsReadRequest,
)
from cadrumo.application.diagnostics_run_health import (
    build_error_breakdown,
    build_latency_report,
    build_llm_usage_report,
    build_run_health_report,
    list_recent_runs,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessStatus,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_authority_descriptor_path,
    bundled_indexed_authority,
)
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo.entrypoints.diagnostics_operation_composition import build_diagnostics_read_ports
from cadrumo.tests.os_keychain_hook import require_os_credential_store

from .test_installed_authenticated_stdio import (
    _installed_mcp_executable,
    _native_backend_for_current_platform,
    _unused_reference,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="native admission is covered on Windows/Linux"),
]

_DEFINITION = DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
_KINDS: tuple[DiagnosticsReadKind, ...] = ("run_health", "runs", "latency", "errors", "llm_usage")
_SINCE, _UNTIL = date(2026, 4, 1), date(2026, 4, 2)
_PROVIDER = "llm:claude:synthetic"


def _scope(destination: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({_DEFINITION}),
        actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT}),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=_DEFINITION + ".result",
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _prepare(profile_id: UUID, _root: Path, *, operation: PinnedAuthorityOperation) -> dict[str, object]:
    recorder = LLMRunTelemetryRecorder()
    for run_id, day, provider, duration, succeeded in (
        ("first", 1, _PROVIDER, 1200, True),
        ("last", 2, _PROVIDER, 45000, False),
        ("other-provider", 2, "llm:codex:synthetic", 99000, True),
        ("outside-window", 3, _PROVIDER, 88000, True),
    ):
        recorder.record(
            LLMRunRecord(
                run_id=run_id,
                caller="cadrumo.application.ledger.llm_classification",
                provider=provider,
                model="synthetic",
                duration_ms=duration,
                succeeded=succeeded,
                error_kind="" if succeeded else "LLMClassifierError",
                started_at=datetime(2026, 4, day, 9, tzinfo=UTC),
            )
        )
    ports = build_diagnostics_read_ports(profile_id=profile_id, operation=operation)
    return {
        "run_health": build_run_health_report(
            since=_SINCE,
            until=_UNTIL,
            provider=_PROVIDER,
            run_telemetry_port=ports.run_telemetry_port,
            auth_probe_port=ports.auth_probe_port,
        ).model_dump(mode="json"),
        "runs": [
            row.model_dump(mode="json")
            for row in list_recent_runs(
                since=_SINCE, until=_UNTIL, provider=_PROVIDER, limit=1, run_telemetry_port=ports.run_telemetry_port
            )
        ],
        "latency": build_latency_report(
            since=_SINCE, until=_UNTIL, provider=_PROVIDER, run_telemetry_port=ports.run_telemetry_port
        ).model_dump(mode="json"),
        "errors": build_error_breakdown(
            since=_SINCE, until=_UNTIL, provider=_PROVIDER, run_telemetry_port=ports.run_telemetry_port
        ).model_dump(mode="json"),
        "llm_usage": build_llm_usage_report(
            since=_SINCE, until=_UNTIL, provider=_PROVIDER, run_telemetry_port=ports.run_telemetry_port
        ).model_dump(mode="json"),
    }


def _object(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _canonical_report(projection: DiagnosticsReadProjection) -> object:
    """Compare full canonical meaning after the reviewed decimal wire conversion."""
    if projection.run_health is not None:
        return projection.run_health.to_report().model_dump(mode="json")
    if projection.latency is not None:
        return projection.latency.to_report().model_dump(mode="json")
    if projection.llm_usage is not None:
        return projection.llm_usage.to_report().model_dump(mode="json")
    if projection.errors is not None:
        return projection.errors.model_dump(mode="json")
    assert projection.runs is not None
    return [row.model_dump(mode="json") for row in projection.runs]


@pytest.mark.anyio
async def test_installed_mcp_reads_all_diagnostics_reports_with_exact_filters(tmp_path: Path) -> None:
    require_os_credential_store()
    backend = _native_backend_for_current_platform()
    native = native_automation_secret_store(backend)
    assert native.backend is backend
    with (
        bundled_indexed_authority().operation() as operation,
        native_api_cli_session(
            tmp_path,
            scope_for_destination=_scope,
            prepare_profile=lambda profile_id, root: _prepare(profile_id, root, operation=operation),
            server_native_store=native,
        ) as profile,
    ):
        source = NativeClientCredentialStore.resolve_reference(
            credential_reference=profile.credential_reference,
            binding=profile.binding,
            secrets_store=profile._client_native,
        )
        metadata = source.metadata
        protected = NativeClientCredentialStore(
            secrets_store=native,
            binding=profile.binding,
            client_id=metadata.client_id,
            destination_id=metadata.destination_id,
        )
        reference = _unused_reference(protected)
        primary: BaseException | None = None
        try:
            protected.replace(
                credential_reference=reference,
                grant_id=metadata.grant_id,
                key_id=metadata.key_id,
                review_digest=metadata.review_digest,
                credential=source.read(),
            )
            executable = _installed_mcp_executable()
            assert executable.is_file()
            parameters = StdioServerParameters(
                command=str(executable),
                args=["--profile-id", str(profile.profile_id), "--credential-reference", str(reference)],
                cwd=tmp_path,
                env={
                    "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
                    "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                    "PYDANTIC_DISABLE_PLUGINS": "__all__",
                },
            )
            with (tmp_path / "installed-diagnostics.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()
                    status_call = await client.call_tool("status", {})
                    assert status_call.is_error is False
                    status_document = _object(status_call.structured_content)
                    assert status_document["outcome"] == "status"
                    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(status_document["status"]))
                    assert status.profile_id == profile.profile_id
                    assert status.connected and status.credential_authenticated and status.profile_bound
                    assert status.denial is None and status.grant_valid
                    assert status.session_id is not None
                    custody = profile.server_custody_health()
                    assert custody.binding == profile.binding
                    assert custody.backend is backend
                    assert custody.control_anchor_present is True
                    assert custody.grant_ids == (metadata.grant_id,)
                    assert custody.key_ids == (metadata.key_id,)
                    assert custody.wrap_count == 1
                    assert custody.wrapping_keys_valid is True
                    assert custody.runtime_uses_same_store is True
                    worker = profile.worker_health(status.session_id)
                    assert worker.identity.binding == profile.binding
                    assert worker.identity.binding.profile_id == profile.profile_id
                    assert worker.alive and worker.exact_session_admitted
                    assert worker.worker_process_id > 0
                    assert worker.worker_process_id != worker.runtime_process_id
                    assert worker.admitted_session_count == 1
                    found = await client.call_tool("search", {"query": _DEFINITION})
                    assert found.is_error is False
                    assert any(
                        item["definition_id"] == _DEFINITION for item in _object(found.structured_content)["operations"]
                    )
                    described = await client.call_tool("describe", {"definition_id": _DEFINITION})
                    assert described.is_error is False
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(_object(_object(described.structured_content)["description"])["contract"])
                    )
                    assert contract.result_schema is not None
                    for kind in _KINDS:
                        request = DiagnosticsReadRequest(
                            profile_id=profile.profile_id,
                            kind=kind,
                            since=_SINCE,
                            until=_UNTIL,
                            provider=_PROVIDER,
                            limit=1 if kind == "runs" else None,
                        )
                        submitted = await client.call_tool(
                            "execute",
                            {
                                "definition_id": _DEFINITION,
                                "subject_ref": profile_operation_subject(str(profile.profile_id)),
                                "payload": request.model_dump(mode="json"),
                            },
                        )
                        assert submitted.is_error is False
                        receipt = OperationSubmissionReceiptV1.model_validate_json(
                            canonical_json_bytes(_object(submitted.structured_content)["receipt"])
                        )
                        observation_request = OperationObservationRequestV1(
                            operation_id=receipt.operation_id, after_cursor=0, page_limit=32
                        )
                        terminal: OperationObservationSuccessV1 | None = None
                        for _attempt in range(100):
                            observed = await client.call_tool(
                                "observe", {"observation": observation_request.model_dump(mode="json")}
                            )
                            assert observed.is_error is False
                            candidate = OperationObservationSuccessV1.model_validate_json(
                                canonical_json_bytes(
                                    _object(_object(observed.structured_content)["reply"])["observation"]
                                )
                            )
                            if candidate.projection.lifecycle is OperationLifecycle.TERMINAL:
                                terminal = candidate
                                break
                            await asyncio.sleep(0.05)
                        assert terminal is not None, f"diagnostics {kind} did not settle"
                        assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                        assert terminal.projection.effect is OperationEffect.NONE
                        result_request = OperationResultProjectionRequestV1(
                            operation_id=receipt.operation_id,
                            terminal_revision=terminal.projection.revision,
                            definition_contract_digest=contract.definition_contract_digest,
                            result_schema=contract.result_schema,
                        )
                        released = await client.call_tool("result", {"result": result_request.model_dump(mode="json")})
                        assert released.is_error is False
                        result = OperationResultProjectionSuccessV1[DiagnosticsReadProjection].model_validate_json(
                            canonical_json_bytes(_object(released.structured_content)["document"])
                        )
                        assert result.projection.profile_id == profile.profile_id
                        assert result.projection.model_dump(
                            include=set(DiagnosticsReadRequest.model_fields), mode="json"
                        ) == request.model_dump(mode="json")
                        assert _canonical_report(result.projection) == profile.prepared[kind]
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                protected.delete(
                    credential_reference=reference,
                    grant_id=metadata.grant_id,
                    key_id=metadata.key_id,
                    review_digest=metadata.review_digest,
                )
            except BaseException as cleanup_error:
                if primary is None:
                    raise
                primary.add_note(f"exact native credential cleanup failed ({type(cleanup_error).__name__})")
