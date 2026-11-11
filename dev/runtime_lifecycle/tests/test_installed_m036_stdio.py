"""Installed MCP exposes only the safe Modelo 036 query projection.

The query-only credential reads canonical M036 declaration records seeded
through the encrypted profile repositories under the same pinned authority.
The installed MCP process reaches those records through native credential
custody, real stdio, and the registered profile-worker operation.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.profile.m036_lifecycle import build_m036_lifecycle_ports
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.modelo.m036_lifecycle import (
    M036DeclarationCommand,
    list_m036_declarations,
    record_m036_declaration,
)
from cadrumo.application.modelo.m036_operation import (
    M036_QUERY_OPERATION_DEFINITION_ID,
    M036_READ_OPERATION_DEFINITION_ID,
    M036_RECORD_OPERATION_DEFINITION_ID,
    M036QueryDeclaration,
    M036QueryProjection,
    M036ReadRequest,
    M036RecordRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.censo_modelos import (
    CENSO_MODELO_EVENT_KINDS,
    CensoModeloEventKind,
    active_036_ownership_from_registry,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import native_api_cli_session

from .installed_mcp_stdio_support import assert_human_operation_refused, release_query_result, structured_object
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

_QUERY = M036_QUERY_OPERATION_DEFINITION_ID
_READ = M036_READ_OPERATION_DEFINITION_ID
_RECORD = M036_RECORD_OPERATION_DEFINITION_ID
_EVENTS = (
    (CensoModeloEventKind.ALTA, date(filing_year_envelope().floor, 1, 1)),
    (CensoModeloEventKind.MODIFICACION, date(filing_year_envelope().floor, 3, 1)),
    (CensoModeloEventKind.BAJA, date(filing_year_envelope().horizon, 1, 1)),
)


@dataclass(frozen=True, slots=True)
class _M036Seed:
    """Expected safe query rows and private sentinel values for the test."""

    expected_rows: tuple[M036QueryDeclaration, ...]
    note_sentinels: tuple[str, ...] = field(repr=False)
    receipt_sentinels: tuple[str, ...] = field(repr=False)


def _scope(destination: UUID) -> AccessScope:
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
        operations=frozenset({_QUERY}),
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
) -> _M036Seed:
    """Seed prior external filings locally under this profile and authority pin."""
    ownership = active_036_ownership_from_registry(operation)
    assert ownership.event_kinds == CENSO_MODELO_EVENT_KINDS
    bucket_id = str(profile_id)
    ports = build_m036_lifecycle_ports(bucket_id=bucket_id)
    nonce = uuid4().hex
    note_sentinels: list[str] = []
    receipt_sentinels: list[str] = []
    for event_kind, declared_on in _EVENTS:
        note = f"m036-private-note-{nonce}-{event_kind.value}"
        receipt = f"m036-private-receipt-{nonce}-{event_kind.value}"
        note_sentinels.append(note)
        receipt_sentinels.append(receipt)
        record_m036_declaration(
            M036DeclarationCommand(
                profile_id=bucket_id,
                event_kind=event_kind,
                declared_on=declared_on,
                sede_justificante=receipt,
                note=note,
            ),
            bucket_id=bucket_id,
            ports=ports,
        )
    canonical_rows = list_m036_declarations(bucket_id=bucket_id, ports=ports)
    expected_rows = tuple(
        M036QueryDeclaration(
            profile_id=profile_id,
            declaration_id=row.declaration_id,
            event_kind=row.event_kind,
            declared_on=row.declared_on,
            recorded_at=row.recorded_at,
            justificante_present=row.sede_justificante is not None,
            note_present=row.note is not None,
        )
        for row in canonical_rows
    )
    return _M036Seed(
        expected_rows=expected_rows,
        note_sentinels=tuple(note_sentinels),
        receipt_sentinels=tuple(receipt_sentinels),
    )


def _unique_digest_prefix(declaration_id: str, declaration_ids: tuple[str, ...]) -> str:
    """Choose a useful prefix that is unique among these exact seeded ids."""
    for length in range(12, len(declaration_id)):
        prefix = declaration_id[:length]
        if sum(candidate.startswith(prefix) for candidate in declaration_ids) == 1:
            return prefix
    raise AssertionError("a seeded M036 content digest must be unique")


async def _query(
    client: ClientSession,
    *,
    request: M036ReadRequest,
    contract: OperationPublicDefinitionContractV1,
    seed: _M036Seed,
    credential_reference: UUID,
) -> M036QueryProjection:
    result, document = await release_query_result(
        client,
        definition_id=_QUERY,
        profile_id=request.profile_id,
        request=request,
        contract=contract,
        result_model=OperationResultProjectionSuccessV1[M036QueryProjection],
        label=f"M036 {request.kind} query",
    )
    projection = result.projection
    assert projection.profile_id == request.profile_id
    assert projection.kind == request.kind
    if request.kind == "list":
        assert projection.declarations == seed.expected_rows
    else:
        assert request.declaration_id is not None
        assert len(projection.declarations) == 1
        assert str(projection.declarations[0].declaration_id).startswith(request.declaration_id)
        expected = next(
            row for row in seed.expected_rows if row.declaration_id == projection.declarations[0].declaration_id
        )
        assert projection.declarations == (expected,)

    for row in projection.declarations:
        assert row.profile_id == request.profile_id
        assert row.justificante_present is True
        assert row.note_present is True
    serialized_projection = canonical_json_bytes(projection.model_dump(mode="json")).decode("utf-8")
    serialized_response = canonical_json_bytes(document).decode("utf-8")
    assert all(sentinel not in serialized_projection for sentinel in seed.note_sentinels)
    assert all(sentinel not in serialized_projection for sentinel in seed.receipt_sentinels)
    assert all(sentinel not in serialized_response for sentinel in seed.note_sentinels)
    assert all(sentinel not in serialized_response for sentinel in seed.receipt_sentinels)
    assert str(credential_reference) not in serialized_response
    assert '"note":' not in serialized_projection
    assert '"sede_justificante":' not in serialized_projection
    assert '"note":' not in serialized_response
    assert '"sede_justificante":' not in serialized_response
    assert "note" not in M036QueryDeclaration.model_fields
    assert "sede_justificante" not in M036QueryDeclaration.model_fields
    return projection


@pytest.mark.anyio
async def test_installed_mcp_releases_only_safe_m036_query_rows(
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
            prepare_profile=lambda profile_id, root: _prepare_profile(profile_id, root, operation=operation),
            server_native_store=native if sys.platform == "linux" else None,
        ) as profile,
    ):
        chronological = sorted(profile.prepared.expected_rows, key=lambda row: (row.declared_on, row.recorded_at))
        assert [(row.event_kind, row.declared_on) for row in chronological] == [
            (event_kind, declared_on) for event_kind, declared_on in _EVENTS
        ]
        declaration_ids = tuple(str(row.declaration_id) for row in profile.prepared.expected_rows)
        alta = next(row for row in profile.prepared.expected_rows if row.event_kind is CensoModeloEventKind.ALTA)
        prefix = _unique_digest_prefix(str(alta.declaration_id), declaration_ids)
        assert 12 <= len(prefix) < len(str(alta.declaration_id))

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
            with (tmp_path / "installed-m036.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()
                    found = await client.call_tool("search", {"query": _QUERY})
                    assert found.is_error is False
                    visible = cast("list[dict[str, Any]]", structured_object(found.structured_content)["operations"])
                    assert any(item["definition_id"] == _QUERY for item in visible)

                    described = await client.call_tool("describe", {"definition_id": _QUERY})
                    assert described.is_error is False
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(
                            structured_object(structured_object(described.structured_content)["description"])[
                                "contract"
                            ]
                        ),
                    )
                    assert contract.definition_id == _QUERY
                    assert contract.request_schema.schema_id == _QUERY + ".request"
                    assert contract.result_schema is not None
                    assert contract.result_schema.schema_id == _QUERY + ".result"
                    assert OperationEffect.NONE in contract.permitted_effects
                    assert "note" not in M036QueryDeclaration.model_fields
                    assert "sede_justificante" not in M036QueryDeclaration.model_fields
                    result_schema_json = canonical_json_bytes(M036QueryProjection.model_json_schema()).decode("utf-8")
                    assert '"note":' not in result_schema_json
                    assert '"sede_justificante":' not in result_schema_json

                    await assert_human_operation_refused(
                        client,
                        definition_id=_READ,
                        profile_id=profile.profile_id,
                        request=M036ReadRequest(profile_id=profile.profile_id, kind="list"),
                    )
                    await assert_human_operation_refused(
                        client,
                        definition_id=_RECORD,
                        profile_id=profile.profile_id,
                        request=M036RecordRequest(
                            profile_id=profile.profile_id,
                            event_kind=CensoModeloEventKind.ALTA,
                            declared_on=date(filing_year_envelope().floor, 1, 1),
                        ),
                    )

                    listed = await _query(
                        client,
                        request=M036ReadRequest(profile_id=profile.profile_id, kind="list"),
                        contract=contract,
                        seed=profile.prepared,
                        credential_reference=reference,
                    )
                    assert len(listed.declarations) == 3

                    viewed = await _query(
                        client,
                        request=M036ReadRequest(
                            profile_id=profile.profile_id,
                            kind="view",
                            declaration_id=prefix,
                        ),
                        contract=contract,
                        seed=profile.prepared,
                        credential_reference=reference,
                    )
                    assert len(viewed.declarations) == 1
                    assert viewed.declarations[0].declaration_id == alta.declaration_id
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


__all__ = ["test_installed_mcp_releases_only_safe_m036_query_rows"]
