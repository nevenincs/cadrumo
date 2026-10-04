"""Installed MCP releases only the safe Borrador query projection.

The query-only profile receives a canonical snapshot through encrypted test
setup under the same pinned authority operation. The installed MCP process
then reads it through native credential custody, a real stdio transport, and
the registered worker operation; it cannot invoke human import/read purposes.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.live.borrador_100 import Borrador100SnapshotService
from cadrumo.application.live.borrador_100_contracts import (
    Borrador100ImportRequest,
    Borrador100QueryProjection,
    Borrador100ReadRequest,
)
from cadrumo.application.live.borrador_100_operation import (
    BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
    BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,
    BORRADOR_100_READ_OPERATION_DEFINITION_ID,
)
from cadrumo.application.live.snapshot_base import SnapshotStateFilter
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_authority_descriptor_path,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
from cadrumo.entrypoints.adapter_composition import build_borrador_100_snapshot_repository
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo.tests.fixtures.borrador.generate import corpus_casilla_values, corpus_years

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

_QUERY = BORRADOR_100_QUERY_OPERATION_DEFINITION_ID
_READ = BORRADOR_100_READ_OPERATION_DEFINITION_ID
_IMPORT = BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID


def _fixture_year() -> int:
    support = published_supported_filing_years()
    assert support is not None, "published authority declares no support envelope"
    return max(year for year in corpus_years() if year in support.years)


_FILING_YEAR = _fixture_year()
_CASILLAS = ("0505", "0545", "0546", "0585", "0586")


@dataclass(frozen=True, slots=True)
class _BorradorSeed:
    """Canonical encrypted fixture row and its private provenance sentinel."""

    snapshot_id: str
    source_url: str


def _scope(destination: UUID) -> AccessScope:
    operations = frozenset({_QUERY})
    disclosures = {
        DisclosurePermission(
            destination_id=destination,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        ),
    }
    for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES):
        disclosures.add(
            DisclosurePermission(
                destination_id=destination,
                projection_id=_QUERY + ".result",
                category=category,
            )
        )
    return AccessScope(
        operations=operations,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
            }
        ),
        disclosures=frozenset(disclosures),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _prepare_profile(
    profile_id: UUID,
    _root: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> _BorradorSeed:
    """Seed the synthetic encrypted bucket through the canonical snapshot service.

    The installed profile's exact grant is query-only, so it cannot authorize
    the human CLI import. This fixture setup writes one canonical snapshot
    under the same pinned authority operation before runtime admission.
    """
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    printed = corpus_casilla_values(_FILING_YEAR)
    bindings = {
        f"casilla.{casilla}": printed[validated_casilla_id(casilla, surface="test.installed_query")]
        for casilla in _CASILLAS
    }
    source_url = "test-secret-source:" + uuid4().hex
    service = Borrador100SnapshotService(
        bucket_id=str(profile_id),
        repository=build_borrador_100_snapshot_repository(bucket_id=str(profile_id)),
    )
    snapshot = service.capture(
        filing_year=_FILING_YEAR,
        period=period,
        captured_at=now(),
        source_url=source_url,
        binding_values=bindings,
        operation=operation,
    )
    return _BorradorSeed(snapshot_id=str(snapshot.snapshot_id), source_url=source_url)


def _object(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


async def _query(
    client: ClientSession,
    *,
    request: Borrador100ReadRequest,
    contract: OperationPublicDefinitionContractV1,
    source_url_sentinel: str,
    credential_reference: UUID,
) -> Borrador100QueryProjection:
    submitted = await client.call_tool(
        "execute",
        {
            "definition_id": _QUERY,
            "subject_ref": profile_operation_subject(str(request.profile_id)),
            "payload": request.model_dump(mode="json"),
        },
    )
    assert submitted.is_error is False
    receipt = OperationSubmissionReceiptV1.model_validate_json(
        canonical_json_bytes(_object(submitted.structured_content)["receipt"]),
    )
    observation_request = OperationObservationRequestV1(
        operation_id=receipt.operation_id,
        after_cursor=0,
        page_limit=32,
    )
    terminal: OperationObservationSuccessV1 | None = None
    for _attempt in range(100):
        observed = await client.call_tool(
            "observe",
            {"observation": observation_request.model_dump(mode="json")},
        )
        assert observed.is_error is False
        candidate = OperationObservationSuccessV1.model_validate_json(
            canonical_json_bytes(_object(_object(observed.structured_content)["reply"])["observation"]),
        )
        if candidate.projection.lifecycle is OperationLifecycle.TERMINAL:
            terminal = candidate
            break
        await asyncio.sleep(0.05)
    assert terminal is not None, f"Borrador {request.kind} query did not settle"
    assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.projection.effect is OperationEffect.NONE

    result_schema = contract.result_schema
    assert result_schema is not None
    result_request = OperationResultProjectionRequestV1(
        operation_id=receipt.operation_id,
        terminal_revision=terminal.projection.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=result_schema,
    )
    released = await client.call_tool("result", {"result": result_request.model_dump(mode="json")})
    assert released.is_error is False
    result = OperationResultProjectionSuccessV1[Borrador100QueryProjection].model_validate_json(
        canonical_json_bytes(_object(released.structured_content)["document"]),
    )
    projection = result.projection
    assert projection.profile_id == request.profile_id
    assert projection.kind == request.kind
    assert projection.filing_year == request.filing_year
    if request.kind == "list":
        expected_state = request.state.as_lifecycle_state()
        assert projection.snapshot is None
        assert expected_state is None or all(row.state is expected_state for row in projection.rows)
    elif request.kind == "view":
        assert projection.snapshot is not None
        assert not projection.rows
        assert request.snapshot_id is not None
        assert str(projection.snapshot.snapshot_id).startswith(request.snapshot_id)
    else:
        assert projection.snapshot is not None
        assert not projection.rows
        assert projection.snapshot.filing_year == request.filing_year

    released_json = canonical_json_bytes(projection.model_dump(mode="json")).decode("utf-8")
    assert source_url_sentinel not in released_json
    assert str(credential_reference) not in released_json
    assert "source_url" not in released_json
    assert "warnings" not in released_json
    return projection


async def _assert_human_operation_refused(
    client: ClientSession,
    *,
    definition_id: str,
    profile_id: UUID,
    request: BaseModel,
) -> None:
    """Require the current typed MCP refusal before a human-only request is admitted."""
    refusal = await client.call_tool(
        "execute",
        {
            "definition_id": definition_id,
            "subject_ref": profile_operation_subject(str(profile_id)),
            "payload": request.model_dump(mode="json"),
        },
    )
    assert refusal.is_error is True
    assert refusal.structured_content == {"outcome": "refused", "code": "operation_denied"}


@pytest.mark.anyio
async def test_installed_mcp_queries_borrador_without_releasing_source_provenance(tmp_path: Path) -> None:
    backend = _native_backend_for_current_platform()
    native = native_automation_secret_store(backend)
    assert native.backend is backend
    with (
        bundled_indexed_authority().operation() as operation,
        native_api_cli_session(
            tmp_path,
            scope_for_destination=_scope,
            prepare_profile=lambda profile_id, root: _prepare_profile(profile_id, root, operation=operation),
            server_native_store=native if sys.platform == "linux" else None,
        ) as profile,
    ):
        operation.snapshot("100", filing_year=_FILING_YEAR, period="0A")
        snapshot_id = profile.prepared.snapshot_id
        source_url_sentinel = profile.prepared.source_url

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
            assert executable.is_file(), "the installed cadrumo-mcp executable is required"
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
            with (tmp_path / "installed-borrador.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()

                    found = await client.call_tool("search", {"query": "live.borrador.100"})
                    assert found.is_error is False
                    operations = cast("list[dict[str, Any]]", _object(found.structured_content)["operations"])
                    visible_ids = {str(item["definition_id"]) for item in operations}
                    assert _QUERY in visible_ids

                    described = await client.call_tool("describe", {"definition_id": _QUERY})
                    assert described.is_error is False
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(_object(_object(described.structured_content)["description"])["contract"]),
                    )
                    assert contract.definition_id == _QUERY
                    assert contract.result_schema is not None
                    assert contract.result_schema.schema_id == _QUERY + ".result"
                    assert OperationFrontendProjection.MCP in contract.permitted_frontends
                    query_schema = canonical_json_bytes(Borrador100QueryProjection.model_json_schema()).decode("utf-8")
                    assert '"source_url"' not in query_schema
                    assert '"warnings"' not in query_schema

                    await _assert_human_operation_refused(
                        client,
                        definition_id=_READ,
                        profile_id=profile.profile_id,
                        request=Borrador100ReadRequest(
                            profile_id=profile.profile_id,
                            kind="view",
                            snapshot_id=snapshot_id,
                        ),
                    )
                    await _assert_human_operation_refused(
                        client,
                        definition_id=_IMPORT,
                        profile_id=profile.profile_id,
                        request=Borrador100ImportRequest(
                            profile_id=profile.profile_id,
                            source_path=tmp_path / "must-not-be-opened.pdf",
                            filing_year=_FILING_YEAR,
                            period=PublicPeriod.from_period(Period.from_year_and_code(_FILING_YEAR, "0A")),
                        ),
                    )

                    hidden = source_url_sentinel
                    listed = await _query(
                        client,
                        request=Borrador100ReadRequest(
                            profile_id=profile.profile_id,
                            kind="list",
                            state=SnapshotStateFilter.ACTIVE,
                        ),
                        contract=contract,
                        source_url_sentinel=hidden,
                        credential_reference=reference,
                    )
                    assert len(listed.rows) == 1
                    assert listed.rows[0].snapshot_id == snapshot_id
                    assert listed.rows[0].binding_count == len(_CASILLAS)

                    viewed = await _query(
                        client,
                        request=Borrador100ReadRequest(
                            profile_id=profile.profile_id,
                            kind="view",
                            snapshot_id=snapshot_id,
                        ),
                        contract=contract,
                        source_url_sentinel=hidden,
                        credential_reference=reference,
                    )
                    assert viewed.snapshot is not None
                    assert viewed.snapshot.snapshot_id == snapshot_id
                    assert viewed.snapshot.state.value == "active"
                    actual_values = viewed.snapshot.binding_map()
                    printed = corpus_casilla_values(_FILING_YEAR)
                    expected_values = {
                        f"casilla.{casilla}": printed[validated_casilla_id(casilla, surface="test.installed_query")]
                        for casilla in _CASILLAS
                    }
                    assert actual_values == expected_values
                    assert all(isinstance(value, Decimal) for value in actual_values.values())

                    latest = await _query(
                        client,
                        request=Borrador100ReadRequest(
                            profile_id=profile.profile_id,
                            kind="latest",
                            filing_year=_FILING_YEAR,
                        ),
                        contract=contract,
                        source_url_sentinel=hidden,
                        credential_reference=reference,
                    )
                    assert latest.snapshot is not None
                    assert latest.snapshot.snapshot_id == snapshot_id
                    assert latest.filing_year == _FILING_YEAR
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


__all__ = ["test_installed_mcp_queries_borrador_without_releasing_source_provenance"]
