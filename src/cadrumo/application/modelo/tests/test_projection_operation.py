"""Registered modelo projections keep their full read and migration effects."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import fields, replace
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...ledger.persistence_ports import LedgerPersistenceConflictError
from ...ledger.tests.unused_repository_ports import ProfileOnlyCatalogueRepository
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import projection_operation
from ..calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from ..projection_migration_ports import ProjectionMigrationPlan, ProjectionMigrationPort
from ..projection_operation import (
    MODELO_COMPARE_OPERATION_DEFINITION_ID,
    MODELO_PROJECT_OPERATION_DEFINITION_ID,
    CompareDeltaRowProjection,
    CompareSectionProjection,
    ModeloCompareOperationProjection,
    ModeloCompareOperationRequest,
    ModeloProjectExecutor,
    ModeloProjectOperationProjection,
    ModeloProjectOperationRequest,
    ProjectionOverride,
    _prepare_and_maybe_commit,
    build_modelo_compare_definition,
    build_modelo_compare_registration,
    build_modelo_project_definition,
    build_modelo_project_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unused_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> CalculationActionPorts:
    raise AssertionError(f"access resolution must not open private ports for {bucket_id}")


def _public_registry():
    factory = cast(CalculationActionPortsFactory, _unused_factory)
    migration = cast(ProjectionMigrationPort, object())
    compare = build_modelo_compare_definition(factory=factory, migration=migration)
    project = build_modelo_project_definition(factory=factory, migration=migration)
    registry = OperationRegistry(
        definitions=(compare, project),
        public_registrations=(build_modelo_compare_registration(compare), build_modelo_project_registration(project)),
    )
    return registry


def _request(payload: ModeloProjectOperationRequest | ModeloCompareOperationRequest) -> OperationRequest[BaseModel]:
    definition_id = (
        MODELO_PROJECT_OPERATION_DEFINITION_ID
        if isinstance(payload, ModeloProjectOperationRequest)
        else MODELO_COMPARE_OPERATION_DEFINITION_ID
    )
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(payload.profile_id)),
        payload=payload,
    )


def test_closed_public_contracts_and_all_period_commit_access(authority_operation: PinnedAuthorityOperation) -> None:
    registry = _public_registry()
    for payload in (
        ModeloProjectOperationRequest(profile_id=_PROFILE, year=2025, ccaa="Madrid"),
        ModeloCompareOperationRequest(profile_id=_PROFILE, modelo="303", years=(2024, 2025)),
    ):
        request = _request(payload)
        contract = registry.lookup_public_contract(request.definition_id)
        assert contract.result_schema is not None
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        )
        resolved = resolve_operation_access(registry=registry, request=request, context=context)
        assert resolved.request.period_independent and resolved.policy.requires_all_periods
        assert resolved.request.periods == frozenset()
        assert AccessAction.COMMIT in resolved.policy.actions
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry,
                request=request,
                context=replace(context, profile_id=_OTHER),
            )
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_mcp_result_access_requires_exact_destination_and_tax_values(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    registry = _public_registry()
    destination = uuid4()
    for payload in (
        ModeloProjectOperationRequest(profile_id=_PROFILE, year=2025, ccaa="madrid"),
        ModeloCompareOperationRequest(profile_id=_PROFILE, modelo="130", years=(2025, 2026)),
    ):
        request = _request(payload)
        contract = registry.lookup_public_contract(request.definition_id)
        assert OperationFrontendProjection.MCP in contract.permitted_frontends
        assert contract.result_schema is not None
        resolved = resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=_PROFILE,
                destination_id=destination,
                action=AccessAction.RESULT,
                frontend=OperationFrontendProjection.MCP,
                contract=contract,
                published_authority=Availability.AVAILABLE,
                authority_operation=authority_operation,
            ),
        )
        assert resolved.request.profile_id == _PROFILE
        assert resolved.request.destination_id == destination
        assert resolved.request.period_independent and resolved.policy.requires_all_periods
        assert resolved.request.periods == frozenset()
        assert AccessAction.COMMIT in resolved.policy.actions
        assert resolved.policy.disclosures == frozenset(
            {
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=contract.result_schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                )
            }
        )


def test_public_request_and_result_validators_reject_incomplete_values() -> None:
    with pytest.raises(ValidationError):
        ModeloProjectOperationRequest(
            profile_id=_PROFILE,
            year=2025,
            ccaa="Madrid",
            casilla_overrides=(ProjectionOverride(key="0505", value="1"), ProjectionOverride(key="0505", value="2")),
        )
    with pytest.raises(ValidationError):
        ModeloCompareOperationRequest(profile_id=_PROFILE, modelo="303", years=(2024,))
    with pytest.raises(ValidationError):
        ModeloProjectOperationProjection.model_validate(
            {
                "profile_id": str(_PROFILE),
                "year": 2025,
                "ccaa": "Madrid",
                "quarters_filed": 2,
                "quarters_available": ["1T"],
                "is_extrapolated": True,
                "m130_accumulated": {
                    "ingresos": "1",
                    "gastos": "0",
                    "rendimiento_neto": "1",
                    "pagos_fraccionados": "0",
                },
                "casilla_observations": [],
                "m100_projection": {
                    "base_liquidable_general_0505": "0",
                    "pagos_fraccionados_0604": "0",
                    "cuota_integra_estatal_0545": "0",
                    "cuota_integra_autonomica_0546": "0",
                    "cuota_liquida_estatal_0595": "0",
                    "cuota_liquida_autonomica_0596": "0",
                    "cuota_resultante_0597": "0",
                },
            }
        )


def test_comparison_public_result_retains_order_and_every_provenance_reference() -> None:
    first = CompareDeltaRowProjection(
        casilla_id="0505",
        label="General base",
        section="base",
        year_a_value="1.00",
        year_b_value="2.00",
        delta="1.00",
        pct_change="100",
        formula_id="formula-1",
        legal_refs=("legal-1", "legal-2"),
        source_refs=("source-1", "source-2"),
    )
    second = first.model_copy(
        update={
            "casilla_id": "0604",
            "section": "payments",
            "year_a_value": "0.00",
            "year_b_value": "0.01",
            "delta": "0.01",
            "pct_change": None,
        }
    )
    projection = ModeloCompareOperationProjection(
        profile_id=_PROFILE,
        modelo="100",
        year_a=2024,
        year_b=2025,
        year_a_revision_id="a" * 64,
        year_b_revision_id="b" * 64,
        year_a_is_draft=False,
        year_b_is_draft=True,
        sections=(
            CompareSectionProjection(section="base", rows=(first,)),
            CompareSectionProjection(section="payments", rows=(second,)),
        ),
        delta_rows=(first, second),
    )
    assert ModeloCompareOperationProjection.model_validate_json(projection.model_dump_json()) == projection
    assert projection.delta_rows[0].legal_refs == ("legal-1", "legal-2")
    assert projection.delta_rows[1].delta == "0.01"
    with pytest.raises(ValidationError):
        ModeloCompareOperationProjection.model_validate(
            projection.model_dump() | {"sections": (CompareSectionProjection(section="base", rows=(first,)),)}
        )


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, value: str) -> None:
        self.phases.append(value)

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class _Fence:
    active = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        assert not self.active
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _Migration:
    def __init__(
        self,
        *,
        changed: bool,
        fence: _Fence,
        failure: Exception | None = None,
        prepare_failure: Exception | None = None,
    ) -> None:
        self.plan = ProjectionMigrationPlan(
            catalogue=CalculationRevisionCatalogue(), expected_revision_id="a" * 64, changed=changed
        )
        self.fence = fence
        self.failure = failure
        self.prepare_failure = prepare_failure
        self.commits = 0
        self.prepares = 0

    def prepare(self, repository: object, *, operation: PinnedAuthorityOperation) -> ProjectionMigrationPlan:
        assert not self.fence.active
        self.prepares += 1
        if self.prepare_failure is not None:
            raise self.prepare_failure
        return self.plan

    def commit(self, repository: object, plan: ProjectionMigrationPlan) -> None:
        assert self.fence.active and plan is self.plan
        self.commits += 1
        if self.failure is not None:
            raise self.failure


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("changed", "failure", "effects"),
    [
        (False, None, (OperationEffect.NONE,)),
        (True, None, (OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED)),
        (
            True,
            LedgerPersistenceConflictError("conflict"),
            (OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.NONE),
        ),
        (True, OSError("uncertain write"), (OperationEffect.NONE, OperationEffect.UNKNOWN)),
    ],
)
async def test_only_cas_commit_is_fenced_and_effect_is_truthful(
    authority_operation: PinnedAuthorityOperation,
    changed: bool,
    failure: Exception | None,
    effects: tuple[OperationEffect, ...],
) -> None:
    events = _Events()
    fence = _Fence()
    migration = _Migration(changed=changed, fence=fence, failure=failure)
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(events=events, cancellation=fence, authority_operation=authority_operation),
    )
    repository = ProfileOnlyCatalogueRepository[CalculationRevisionCatalogue](str(_PROFILE))
    if failure is None:
        result = await _prepare_and_maybe_commit(
            calculation_repository=repository,
            migration=cast(ProjectionMigrationPort, migration),
            context=context,
            phase_prefix="modelo.project",
        )
        assert result is migration.plan
    else:
        with pytest.raises(type(failure)):
            await _prepare_and_maybe_commit(
                calculation_repository=repository,
                migration=cast(ProjectionMigrationPort, migration),
                context=context,
                phase_prefix="modelo.project",
            )
    assert events.effects == list(effects)
    assert events.phases == (
        ["modelo.project.prepare", "modelo.project.commit"] if changed else ["modelo.project.prepare"]
    )
    assert migration.prepares == 1 and migration.commits == int(changed)
    assert not fence.active


@pytest.mark.anyio
async def test_preparation_failure_never_enters_commit_or_claims_a_write(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    events = _Events()
    fence = _Fence()
    migration = _Migration(changed=True, fence=fence, prepare_failure=ValueError("bad legacy relation"))
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(events=events, cancellation=fence, authority_operation=authority_operation),
    )
    repository = ProfileOnlyCatalogueRepository[CalculationRevisionCatalogue](str(_PROFILE))
    with pytest.raises(ValueError, match="bad legacy relation"):
        await _prepare_and_maybe_commit(
            calculation_repository=repository,
            migration=cast(ProjectionMigrationPort, migration),
            context=context,
            phase_prefix="modelo.project",
        )
    assert events.phases == ["modelo.project.prepare"]
    assert events.effects == [OperationEffect.NONE] and migration.commits == 0 and not fence.active


@pytest.mark.anyio
async def test_confirmed_migration_remains_updated_if_later_projection_fails(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = _Events()
    fence = _Fence()
    migration = _Migration(changed=True, fence=fence)
    repository = SimpleNamespace(bucket_id=str(_PROFILE))
    values: dict[str, Any] = {field.name: object() for field in fields(CalculationActionPorts)}
    values.update(
        operation=authority_operation,
        calculation_repository=repository,
        work_unit_repository=repository,
    )
    ports = CalculationActionPorts(**values)

    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> CalculationActionPorts:
        assert bucket_id == str(_PROFILE) and operation is authority_operation
        return ports

    def fail_projection(**_kwargs: object) -> None:
        assert not fence.active and migration.commits == 1
        raise ValueError("later canonical projection failure")

    monkeypatch.setattr(projection_operation, "_valid_execution", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(projection_operation, "project_modelo_100_from_m130", fail_projection)
    executor = ModeloProjectExecutor(
        cast(CalculationActionPortsFactory, factory), cast(ProjectionMigrationPort, migration)
    )
    payload = ModeloProjectOperationRequest(profile_id=_PROFILE, year=2025, ccaa="Madrid")
    request = OperationRequest[ModeloProjectOperationRequest](
        definition_id=MODELO_PROJECT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(events=events, cancellation=fence, authority_operation=authority_operation),
    )
    with pytest.raises(ValueError, match="later canonical projection failure"):
        await executor.execute(request, context)
    assert migration.prepares == migration.commits == 1
    assert events.effects == [OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert not fence.active
