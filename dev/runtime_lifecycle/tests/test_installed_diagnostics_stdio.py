"""Installed MCP releases complete canonical reports from an exact-profile worker.

Native credential custody and stdio are real. Enrollment delivery and OS-login
observations use the synthetic controls of the shared encrypted-profile fixture.
No provider requests or data transmissions are performed.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.llm.run_records import LLMRunRecord, LLMRunRecorder
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import (
    ClientCredentialMetadata,
    NativeClientCredentialStore,
)
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
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.user_profile.automation_custody_port import NativeSecretBackend
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.entrypoints.diagnostics_operation_composition import build_diagnostics_read_ports
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo_client.contracts.access_refusals import ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import NativeApiCliSession, native_api_cli_session

from .installed_mcp_stdio_support import release_query_result, structured_object
from .test_installed_authenticated_stdio import (
    installed_mcp_executable,
    native_backend_for_current_platform,
    unused_reference,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="native admission is covered on Windows/Linux"),
]

_DEFINITION = DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
_KINDS: tuple[DiagnosticsReadKind, ...] = ("run_health", "runs", "latency", "errors", "llm_usage")
_SINCE, _UNTIL = date(1980, 4, 1), date(1980, 4, 2)
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
    recorder = LLMRunRecorder()
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
                started_at=datetime(1980, 4, day, 9, tzinfo=UTC),
            )
        )
    ports = build_diagnostics_read_ports(profile_id=profile_id, operation=operation)
    return {
        "run_health": build_run_health_report(
            since=_SINCE,
            until=_UNTIL,
            provider=_PROVIDER,
            run_record_port=ports.run_record_port,
            auth_probe_port=ports.auth_probe_port,
        ).model_dump(mode="json"),
        "runs": [
            row.model_dump(mode="json")
            for row in list_recent_runs(
                since=_SINCE, until=_UNTIL, provider=_PROVIDER, limit=1, run_record_port=ports.run_record_port
            )
        ],
        "latency": build_latency_report(
            since=_SINCE, until=_UNTIL, provider=_PROVIDER, run_record_port=ports.run_record_port
        ).model_dump(mode="json"),
        "errors": build_error_breakdown(
            since=_SINCE, until=_UNTIL, provider=_PROVIDER, run_record_port=ports.run_record_port
        ).model_dump(mode="json"),
        "llm_usage": build_llm_usage_report(
            since=_SINCE, until=_UNTIL, provider=_PROVIDER, run_record_port=ports.run_record_port
        ).model_dump(mode="json"),
    }


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


async def _assert_exact_custody_admission(
    client: ClientSession,
    profile: NativeApiCliSession[dict[str, object]],
    metadata: ClientCredentialMetadata,
    backend: NativeSecretBackend,
) -> None:
    status_call = await client.call_tool("status", {})
    assert status_call.is_error is False
    status_document = structured_object(status_call.structured_content)
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


async def _discover_diagnostics_contract(client: ClientSession) -> OperationPublicDefinitionContractV1:
    found = await client.call_tool("search", {"query": _DEFINITION})
    assert found.is_error is False
    assert any(
        item["definition_id"] == _DEFINITION for item in structured_object(found.structured_content)["operations"]
    )
    described = await client.call_tool("describe", {"definition_id": _DEFINITION})
    assert described.is_error is False
    contract = OperationPublicDefinitionContractV1.model_validate_json(
        canonical_json_bytes(
            structured_object(structured_object(described.structured_content)["description"])["contract"]
        )
    )
    assert contract.result_schema is not None
    return contract


async def _assert_every_report_matches(
    client: ClientSession,
    profile: NativeApiCliSession[dict[str, object]],
    contract: OperationPublicDefinitionContractV1,
) -> None:
    for kind in _KINDS:
        request = DiagnosticsReadRequest(
            profile_id=profile.profile_id,
            kind=kind,
            since=_SINCE,
            until=_UNTIL,
            provider=_PROVIDER,
            limit=1 if kind == "runs" else None,
        )
        result, _document = await release_query_result(
            client,
            definition_id=_DEFINITION,
            profile_id=profile.profile_id,
            request=request,
            contract=contract,
            result_model=OperationResultProjectionSuccessV1[DiagnosticsReadProjection],
            label=f"diagnostics {kind}",
        )
        assert result.projection.profile_id == profile.profile_id
        assert result.projection.model_dump(
            include=set(DiagnosticsReadRequest.model_fields), mode="json"
        ) == request.model_dump(mode="json")
        assert _canonical_report(result.projection) == profile.prepared[kind]


@pytest.mark.anyio
async def test_installed_mcp_reads_all_diagnostics_reports_with_exact_filters(
    tmp_path: Path, run_cadrumo_cli: Callable[..., Result]
) -> None:
    require_os_credential_store()
    backend = native_backend_for_current_platform()
    native = native_automation_secret_store(backend)
    assert native.backend is backend
    with (
        bundled_indexed_authority().operation() as operation,
        native_api_cli_session(
            tmp_path,
            invoke_cli=run_cadrumo_cli,
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
        reference = unused_reference(protected)
        primary: BaseException | None = None
        try:
            protected.replace(
                credential_reference=reference,
                grant_id=metadata.grant_id,
                key_id=metadata.key_id,
                review_digest=metadata.review_digest,
                credential=source.read(),
            )
            executable = installed_mcp_executable()
            assert executable.is_file()
            parameters = StdioServerParameters(
                command=str(executable),
                args=["--profile-id", str(profile.profile_id), "--credential-reference", str(reference)],
                cwd=tmp_path,
                env={
                    "CADRUMO_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
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
                    await _assert_exact_custody_admission(client, profile, metadata, backend)
                    contract = await _discover_diagnostics_contract(client)
                    await _assert_every_report_matches(client, profile, contract)
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
