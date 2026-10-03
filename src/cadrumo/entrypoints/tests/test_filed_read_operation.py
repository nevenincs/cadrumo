"""Recorded exact-profile Sede listing and discovery with synthetic provider facts."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.filed_data_ports import (
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledDeclarationAvailabilityReportProtocol,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from cadrumo.application.live.filed_history_operation import FiledHistoryBrowserResourcesFactory
from cadrumo.application.live.filed_read_operation import (
    FILED_DISCOVER_DEFINITION_ID,
    FILED_LIST_DEFINITION_ID,
    FiledDiscoverPublicResultV1,
    FiledDiscoverRequest,
    FiledListPublicResultV1,
    FiledListRequest,
    FiledReadComposition,
    FiledReadCompositionFactory,
    build_filed_discover_definition,
    build_filed_discover_registration,
    build_filed_list_definition,
    build_filed_list_registration,
)
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.capabilities import OperationOwnedResource
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.core.register_scoping_signal import RegisterScopingSignal
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.deadlines.models import TaxpayerProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)
_EXPEDIENTE_ID = "202510013522222A"


@dataclass(frozen=True, slots=True)
class _SyntheticDeclaration:
    """One synthetic row, with only link-presence facts consumed by listing."""

    modelo: str
    ejercicio: int
    period: Period
    expediente_id: str = _EXPEDIENTE_ID
    estado: str = "ALTA"
    presented_at: datetime = _NOW
    tipo_solicitud: str | None = None
    observaciones: str | None = None
    justificante_link_text: str | None = "synthetic receipt"
    archive_link_text: str | None = "synthetic submitted file"
    declaration_copy_link_text: str | None = None
    justificante_cell_index: int = 7
    archive_cell_index: int | None = 8
    declaration_copy_cell_index: int | None = None


@dataclass(frozen=True, slots=True)
class _AvailabilityItem:
    modelo: str
    ejercicios: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _AvailabilityReport:
    items: tuple[_AvailabilityItem, ...]

    @property
    def offered_pairs(self) -> tuple[tuple[str, int], ...]:
        return tuple((item.modelo, year) for item in self.items for year in item.ejercicios)


class _SyntheticRegister:
    """Return one synthetic declaration and one bounded bulk-walk failure."""

    walk_timeout_ms = 1000

    def __init__(self, trace: list[str]) -> None:
        self._trace = trace
        self.walk_calls: list[tuple[str, int]] = []
        self.failed_pair: tuple[str, int] | None = None

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        self._trace.append("register-walk")
        self.walk_calls.append((modelo, ejercicio))
        if len(self.walk_calls) == 1:
            return cast(
                tuple[FiledRegisterDeclarationProtocol, ...],
                (_SyntheticDeclaration(modelo, ejercicio, Period.from_year_and_code(ejercicio, "1T")),),
            )
        if len(self.walk_calls) == 2:
            self.failed_pair = (modelo, ejercicio)
            raise RuntimeError("synthetic register read failure")
        return ()

    async def capture_observation(self, *args: object, **kwargs: object):
        del args, kwargs
        raise AssertionError("a filed-list read must not download declaration evidence")

    async def capture_observation_deferred(self, *args: object, **kwargs: object):
        del args, kwargs
        raise AssertionError("a filed-list read must not defer declaration evidence")


class _SyntheticFiledDataPort:
    """Make only the provider reads needed by list and discovery available."""

    def __init__(self, *, trace: list[str], resource_is_active: Callable[[], bool]) -> None:
        self._trace = trace
        self._resource_is_active = resource_is_active
        self.register = _SyntheticRegister(trace)
        self._availability = _AvailabilityReport(
            items=(
                _AvailabilityItem(modelo="100", ejercicios=(2025,)),
                _AvailabilityItem(modelo="303", ejercicios=(2024, 2025)),
            )
        )
        self.register_authorities: list[PinnedAuthorityOperation | None] = []
        self.availability_operations: list[str] = []

    @asynccontextmanager
    async def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AsyncIterator[FiledDataRegisterPort]:
        assert self._resource_is_active()
        assert operation == "live-expedientes-read"
        assert effect_guard is not None and on_session_write is not None
        self.register_authorities.append(authority_operation)
        self._trace.append("register-open")
        yield cast(FiledDataRegisterPort, self.register)

    async def discover_availability(
        self,
        *,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> FiledDeclarationAvailabilityReportProtocol:
        assert self._resource_is_active()
        assert operation == "live-expedientes-read"
        assert effect_guard is not None and on_session_write is not None
        self.availability_operations.append(operation)
        self._trace.append("availability-read")
        return cast(FiledDeclarationAvailabilityReportProtocol, self._availability)


@dataclass(frozen=True, slots=True)
class _Composition:
    filed_data_port: FiledDataCapturePort


class _ResourceScope:
    """Track worker-owned PROCESS activation and cleanup without launching AEAT."""

    def __init__(self) -> None:
        self.activation_depth = 0
        self.activation_entries = 0
        self.close_calls = 0
        self.closed = False

    @contextmanager
    def activate(self) -> Iterator[None]:
        self.activation_entries += 1
        self.activation_depth += 1
        try:
            yield
        finally:
            self.activation_depth -= 1

    async def close(self) -> None:
        assert self.activation_depth == 0
        self.close_calls += 1
        self.closed = True


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def _assert_exact_mcp_access[RequestPayloadT: BaseModel](
    *,
    registry: OperationRegistry,
    request: OperationRequest[RequestPayloadT],
    registration,
    profile_id: UUID,
    authority: PinnedAuthorityOperation,
) -> None:
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.MCP,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority,
    )
    admitted = resolve_operation_access(
        registry=registry,
        request=cast(OperationRequest[BaseModel], request),
        context=context,
    )
    assert admitted.request.profile_id == profile_id
    assert admitted.request.period_independent
    assert admitted.request.periods == frozenset()
    assert admitted.policy.requires_all_periods

    foreign_profile_id = uuid4()
    assert foreign_profile_id != profile_id
    foreign_request = request.model_copy(
        update={
            "subject_ref": profile_operation_subject(str(foreign_profile_id)),
            "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
        }
    )
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], foreign_request),
            context=context,
        )
    assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_supervisor_records_filed_list_and_discover_for_exact_mcp_profile(tmp_path: Path) -> None:
    """Record register listing and option discovery without contacting AEAT."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        trace: list[str] = []
        resources: list[_ResourceScope] = []

        def resource_is_active() -> bool:
            return any(resource.activation_depth == 1 for resource in resources)

        filed_port = _SyntheticFiledDataPort(trace=trace, resource_is_active=resource_is_active)
        composition = _Composition(filed_data_port=cast(FiledDataCapturePort, filed_port))
        list_preflights: list[tuple[UUID, PinnedAuthorityOperation]] = []
        discover_preflights: list[tuple[UUID, PinnedAuthorityOperation]] = []
        profile_resolutions: list[PinnedAuthorityOperation] = []

        def list_preflight(profile_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            list_preflights.append((profile_arg, pinned_authority))
            trace.append("list-preflight")

        def discover_preflight(profile_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            discover_preflights.append((profile_arg, pinned_authority))
            trace.append("discover-preflight")

        def composition_factory(label: str) -> FiledReadCompositionFactory:
            def build(*, operation: PinnedAuthorityOperation) -> FiledReadComposition:
                trace.append(f"{label}-composition")
                return cast(FiledReadComposition, composition)

            return build

        def resource_factory(label: str) -> FiledHistoryBrowserResourcesFactory:
            def build() -> _ResourceScope:
                trace.append(f"{label}-resources")
                resource = _ResourceScope()
                resources.append(resource)
                return resource

            return build

        def resolve_missing_profile(pinned_authority: PinnedAuthorityOperation) -> TaxpayerProfile | None:
            profile_resolutions.append(pinned_authority)
            trace.append("profile-resolver")
            return None

        list_definition = build_filed_list_definition(
            composition_factory=composition_factory("list"),
            browser_resources_factory=resource_factory("list"),
            provider_preflight=list_preflight,
        )
        discover_definition = build_filed_discover_definition(
            composition_factory=composition_factory("discover"),
            browser_resources_factory=resource_factory("discover"),
            provider_preflight=discover_preflight,
            profile_resolver=resolve_missing_profile,
        )
        list_registration = build_filed_list_registration(list_definition)
        discover_registration = build_filed_discover_registration(discover_definition)
        registry = OperationRegistry(
            definitions=(discover_definition, list_definition),
            public_registrations=(discover_registration, list_registration),
        )
        list_request = OperationRequest(
            definition_id=FILED_LIST_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledListRequest(profile_id=profile_id, modelo=None, year_from=2025, year_to=2025),
        )
        discover_request = OperationRequest(
            definition_id=FILED_DISCOVER_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledDiscoverRequest(profile_id=profile_id),
        )
        _assert_exact_mcp_access(
            registry=registry,
            request=list_request,
            registration=list_registration,
            profile_id=profile_id,
            authority=authority,
        )
        _assert_exact_mcp_access(
            registry=registry,
            request=discover_request,
            registration=discover_registration,
            profile_id=profile_id,
            authority=authority,
        )

        for definition in (list_definition, discover_definition):
            assert OperationFrontendProjection.MCP in definition.permitted_frontends
            assert definition.capabilities.owned_resources == frozenset({OperationOwnedResource.PROCESS})

        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run(request, operation_id: str, result_type: type[BaseModel]):
            submitted_id = await supervisor.submit(request, operation_id=operation_id)
            terminal = await _run_to_terminal(supervisor, submitted_id)
            contract = registry.lookup_public_contract(request.definition_id)
            assert contract.result_schema is not None
            projected = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                result_type,
            )
            return terminal, projected

        list_terminal, list_projected = asyncio.run(run(list_request, "3" * 64, FiledListPublicResultV1))
        discover_terminal, discover_projected = asyncio.run(
            run(discover_request, "4" * 64, FiledDiscoverPublicResultV1)
        )

    assert list_terminal.lifecycle is OperationLifecycle.TERMINAL
    assert list_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert list_terminal.effect is OperationEffect.NONE
    assert list_terminal.terminal_receipt is not None
    assert list_terminal.terminal_receipt.effect is OperationEffect.NONE
    assert isinstance(list_projected, OperationResultProjectionSuccessV1)
    assert isinstance(list_projected.projection, FiledListPublicResultV1)
    listed = list_projected.projection
    assert listed.modelo_filter is None
    assert (listed.year_from, listed.year_to, listed.row_count) == (2025, 2025, 1)
    assert listed.failed_count == len(listed.failures)
    assert listed.rows[0].model_dump() == {
        "modelo": filed_port.register.walk_calls[0][0],
        "year": 2025,
        "period": "1T",
        "expediente_id": _EXPEDIENTE_ID,
        "status": "ALTA",
        "presented_at": _NOW,
        "has_submitted_file": True,
        "has_declaration_copy": False,
        "has_justificante": True,
    }
    assert set(listed.rows[0].model_dump()) == {
        "modelo",
        "year",
        "period",
        "expediente_id",
        "status",
        "presented_at",
        "has_submitted_file",
        "has_declaration_copy",
        "has_justificante",
    }
    synthetic_failures = [failure for failure in listed.failures if failure.error_type == "RuntimeError"]
    assert filed_port.register.failed_pair is not None
    assert len(synthetic_failures) == 1
    assert synthetic_failures[0].model_dump() == {
        "modelo": filed_port.register.failed_pair[0],
        "year": 2025,
        "period": None,
        "expediente_id": None,
        "error_type": "RuntimeError",
        "message": "synthetic register read failure",
    }
    assert all(
        set(failure.model_dump()) == {"modelo", "year", "period", "expediente_id", "error_type", "message"}
        for failure in listed.failures
    )

    assert discover_terminal.lifecycle is OperationLifecycle.TERMINAL
    assert discover_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert discover_terminal.effect is OperationEffect.NONE
    assert discover_terminal.terminal_receipt is not None
    assert discover_terminal.terminal_receipt.effect is OperationEffect.NONE
    assert isinstance(discover_projected, OperationResultProjectionSuccessV1)
    assert isinstance(discover_projected.projection, FiledDiscoverPublicResultV1)
    discovered = discover_projected.projection
    assert discovered.model_dump().keys() == {
        "pairs",
        "profile_year_span_determined",
        "register_options_read",
        "scoping_signal",
    }
    assert discovered.profile_year_span_determined is False
    assert discovered.register_options_read is True
    assert discovered.scoping_signal is RegisterScopingSignal.INCONCLUSIVE
    assert tuple((pair.modelo, pair.ejercicio, pair.signals) for pair in discovered.pairs) == (
        ("100", 2025, (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)),
        ("303", 2025, (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)),
        ("303", 2024, (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)),
    )
    assert all(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY not in pair.signals for pair in discovered.pairs)
    assert profile_resolutions == [authority]

    assert list_preflights == [(profile_id, authority)]
    assert discover_preflights == [(profile_id, authority)]
    assert filed_port.register_authorities == [authority]
    assert filed_port.availability_operations == ["live-expedientes-read"]
    assert trace.index("list-preflight") < trace.index("register-open")
    assert trace.index("discover-preflight") < trace.index("availability-read")
    assert trace.index("discover-preflight") < trace.index("profile-resolver")
    assert trace.index("profile-resolver") < trace.index("discover-composition")
    assert len(resources) == 2
    assert all(resource.activation_entries == 1 for resource in resources)
    assert all(resource.closed and resource.close_calls == 1 for resource in resources)
    assert all(resource.activation_depth == 0 for resource in resources)
