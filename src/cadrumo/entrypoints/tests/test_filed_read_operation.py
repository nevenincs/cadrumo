"""Recorded exact-profile Sede listing and discovery with synthetic provider facts."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

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
from cadrumo.application.operations.access_resolution import resolve_operation_access
from cadrumo.application.operations.capabilities import OperationOwnedResource
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.core.register_scoping_signal import RegisterScopingSignal
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.deadlines.models import TaxpayerProfile
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from .supervised_operation_rig import (
    ProcessResourceScope,
    assert_foreign_profile_refused,
    build_supervised_operation,
    operation_access_context,
    settle_and_project,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_FILING_YEAR = newest_authored_edition("100")

_NOW = datetime(_YEAR, 8, 24, 20, tzinfo=UTC)
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
                _AvailabilityItem(modelo="100", ejercicios=(_FILING_YEAR,)),
                _AvailabilityItem(modelo="303", ejercicios=(_FILING_YEAR - 1, _FILING_YEAR)),
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
    ) -> AsyncGenerator[FiledDataRegisterPort]:
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


def _assert_exact_external_client_access[RequestPayloadT: BaseModel](
    *,
    registry: OperationRegistry,
    request: OperationRequest[RequestPayloadT],
    registration,
    profile_id: UUID,
    authority: PinnedAuthorityOperation,
) -> None:
    context = operation_access_context(
        registration.contract,
        profile_id=profile_id,
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
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
    # Reusing a saved provider session re-publishes it, a local write behind the COMMIT door.
    assert AccessAction.COMMIT in admitted.policy.actions

    assert_foreign_profile_refused(registry=registry, request=request, context=context)


def _assert_settled_without_effect(terminal: OperationPersistedSnapshot) -> None:
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.NONE
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.effect is OperationEffect.NONE


def _assert_listed_register(projected: object, filed_port: _SyntheticFiledDataPort) -> None:
    list_projected = projected
    assert isinstance(list_projected, OperationResultProjectionSuccessV1)
    assert isinstance(list_projected.projection, FiledListPublicResultV1)
    listed = list_projected.projection
    assert listed.modelo_filter is None
    assert (listed.year_from, listed.year_to, listed.row_count) == (_FILING_YEAR, _FILING_YEAR, 1)
    assert listed.failed_count == len(listed.failures)
    assert listed.rows[0].model_dump() == {
        "modelo": filed_port.register.walk_calls[0][0],
        "year": _FILING_YEAR,
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
        "year": _FILING_YEAR,
        "period": None,
        "expediente_id": None,
        "error_type": "RuntimeError",
        "message": "synthetic register read failure",
    }
    assert all(
        set(failure.model_dump()) == {"modelo", "year", "period", "expediente_id", "error_type", "message"}
        for failure in listed.failures
    )


def _assert_discovered_pairs(projected: object) -> None:
    discover_projected = projected
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
        ("100", _FILING_YEAR, (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)),
        ("303", _FILING_YEAR, (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)),
        ("303", _FILING_YEAR - 1, (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)),
    )
    assert all(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY not in pair.signals for pair in discovered.pairs)


def test_supervisor_records_filed_list_and_discover_for_exact_external_client_profile(tmp_path: Path) -> None:
    """Record register listing and option discovery without contacting AEAT."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        trace: list[str] = []
        resources: list[ProcessResourceScope] = []

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
            def build() -> ProcessResourceScope:
                trace.append(f"{label}-resources")
                resource = ProcessResourceScope()
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
            payload=FiledListRequest(profile_id=profile_id, modelo=None, year_from=_FILING_YEAR, year_to=_FILING_YEAR),
        )
        discover_request = OperationRequest(
            definition_id=FILED_DISCOVER_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledDiscoverRequest(profile_id=profile_id),
        )
        _assert_exact_external_client_access(
            registry=registry,
            request=list_request,
            registration=list_registration,
            profile_id=profile_id,
            authority=authority,
        )
        _assert_exact_external_client_access(
            registry=registry,
            request=discover_request,
            registration=discover_registration,
            profile_id=profile_id,
            authority=authority,
        )

        for definition in (list_definition, discover_definition):
            assert definition.capabilities.owned_resources == frozenset({OperationOwnedResource.PROCESS})

        _, _, _, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path, objects=profile.repository, authority=authority, registry=registry, now=_NOW
        )

        list_terminal, list_projected = asyncio.run(
            settle_and_project(supervisor, result_service, registry, list_request, FiledListPublicResultV1)
        )
        discover_terminal, discover_projected = asyncio.run(
            settle_and_project(
                supervisor,
                result_service,
                registry,
                discover_request,
                FiledDiscoverPublicResultV1,
                operation_id="4" * 64,
            )
        )

    _assert_settled_without_effect(list_terminal)
    _assert_listed_register(list_projected, filed_port)
    _assert_settled_without_effect(discover_terminal)
    _assert_discovered_pairs(discover_projected)
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
