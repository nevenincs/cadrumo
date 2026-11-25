"""Installed MCP stdio round-trips real encrypted ledger LLM diagnostics."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.ledger.llm_diagnostics import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    LlmDiagnosticsReport,
    build_llm_diagnostics_report,
)
from cadrumo.application.ledger.llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.core.config_support import LLMProvider, RetiredLLMProvider
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.entrypoints.ledger_llm_diagnostics_composition import (
    build_ledger_llm_diagnostics_operation_ports,
)
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import native_api_cli_session
from cadrumo_runtime.host.tests.frontend.cli.test_ledger_llm_diagnostics import (
    seed_ledger_llm_classified_transactions,
    seed_ledger_llm_usage_records,
)

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
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux"},
        reason="installed native admission is covered on Windows/Linux",
    ),
]

_DEFINITION = LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
_SINCE = date(1980, 4, 1)
_UNTIL = date(1980, 4, 3)
_THRESHOLD = DEFAULT_LOW_CONFIDENCE_THRESHOLD


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
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=_DEFINITION + ".result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _prepare(
    profile_id: UUID,
    _root: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> LlmDiagnosticsReport:
    """Seed both encrypted sources, then capture their canonical report."""
    seed_ledger_llm_usage_records()
    seed_ledger_llm_classified_transactions(str(profile_id))
    ports = build_ledger_llm_diagnostics_operation_ports(profile_id=profile_id, operation=operation)
    return build_llm_diagnostics_report(
        ports=ports.diagnostics,
        since=_SINCE,
        until=_UNTIL,
        low_confidence_threshold=_THRESHOLD,
    )


@pytest.mark.anyio
async def test_installed_mcp_roundtrips_encrypted_ledger_llm_diagnostics(
    tmp_path: Path, run_cadrumo_cli: Callable[..., Result]
) -> None:
    """The installed worker returns stored usage precision and confidence unchanged."""
    require_os_credential_store()
    native = native_automation_secret_store(native_backend_for_current_platform())
    with (
        bundled_indexed_authority().operation() as operation,
        native_api_cli_session(
            tmp_path,
            invoke_cli=run_cadrumo_cli,
            scope_for_destination=_scope,
            prepare_profile=lambda profile_id, root: _prepare(profile_id, root, operation=operation),
            server_native_store=native if sys.platform == "linux" else None,
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
            assert executable.is_file(), "the installed cadrumo-mcp executable is required"
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
            with (tmp_path / "installed-ledger-llm-diagnostics.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()

                    found = await client.call_tool("search", {"query": _DEFINITION})
                    assert found.is_error is False
                    assert any(
                        item["definition_id"] == _DEFINITION
                        for item in cast(
                            "list[dict[str, Any]]", structured_object(found.structured_content)["operations"]
                        )
                    )

                    described = await client.call_tool("describe", {"definition_id": _DEFINITION})
                    assert described.is_error is False
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(
                            structured_object(structured_object(described.structured_content)["description"])[
                                "contract"
                            ]
                        )
                    )
                    assert contract.definition_id == _DEFINITION
                    assert contract.result_schema is not None

                    request = LedgerLlmDiagnosticsRequest(
                        profile_id=profile.profile_id,
                        since=_SINCE,
                        until=_UNTIL,
                        low_confidence_threshold=PublicDecimal(decimal=str(_THRESHOLD)),
                    )
                    result, _document = await release_query_result(
                        client,
                        definition_id=_DEFINITION,
                        profile_id=profile.profile_id,
                        request=request,
                        contract=contract,
                        result_model=OperationResultProjectionSuccessV1[LedgerLlmDiagnosticsProjection],
                        label="ledger LLM diagnostics",
                    )
                    projection = result.projection
                    assert projection.profile_id == profile.profile_id
                    assert projection.operation_id == _DEFINITION
                    assert projection.outcome == "completed"
                    assert projection.effect is OperationEffect.NONE
                    assert projection.since == request.since
                    assert projection.until == request.until
                    assert projection.low_confidence_threshold == request.low_confidence_threshold

                    canonical = profile.prepared
                    assert isinstance(canonical, LlmDiagnosticsReport)
                    assert canonical.total_calls == 3
                    assert canonical.total_classified == 2
                    usage = {row.provider: row for row in canonical.usage_providers}
                    assert usage[RetiredLLMProvider.ANTHROPIC.value].cost_estimate_usd == Decimal("0.0015")
                    assert usage[LLMProvider.AGENT.value].cost_estimate_usd is None
                    assert usage[LLMProvider.AGENT.value].unpriced_calls == 1
                    assert canonical.confidence_providers[0].mean_confidence == Decimal("0.6250")
                    assert projection.to_report() == canonical
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
