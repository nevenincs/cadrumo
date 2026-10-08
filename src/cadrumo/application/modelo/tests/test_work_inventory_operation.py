"""Whole-profile work discovery keeps canonical rows behind explicit consent."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.operation_access_policy import operation_scope_refusal
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..work_inventory_operation import (
    MODELO_WORK_LIST_OPERATION_DEFINITION_ID,
    ModeloWorkListExecutor,
    ModeloWorkListProjection,
    ModeloWorkListRequest,
    build_modelo_work_list_definition,
    build_modelo_work_list_registration,
)
from ..work_lifecycle import list_work_units
from ..work_lifecycle_ports import WorkLifecyclePorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_INSTANT = datetime(2026, 3, 10, 12, tzinfo=UTC)


def _unit(profile: UUID, period_code: str, *, discarded: bool = False) -> WorkUnit:
    period = Period.from_year_and_code(2026, period_code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile), modelo="303", filing_year=2026, period=period, revision_id="2026-y-siguientes"
        ),
        bucket_id=str(profile),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name=period_code,
        created_at=_INSTANT,
        updated_at=_INSTANT,
        state=WorkUnitState.DESCARTADO if discarded else WorkUnitState.BORRADOR,
        discarded_at=_INSTANT if discarded else None,
        discarded_by="operator" if discarded else None,
    )


class _Repository:
    def __init__(self, units: tuple[WorkUnit, ...], *, bucket_id: str = str(_PROFILE)) -> None:
        self.bucket_id = bucket_id
        self.units = units
        self.loads = 0

    def load(self) -> WorkUnitCatalogue:
        self.loads += 1
        return WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in self.units})


def _factory(repository: _Repository):
    def factory() -> WorkLifecyclePorts:
        return cast(WorkLifecyclePorts, cast(object, SimpleNamespace(work_unit_repository=repository)))

    return factory


def _registration():
    definition = build_modelo_work_list_definition(_factory(_Repository(())))
    registration = build_modelo_work_list_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration


def _request(
    *, profile_id: UUID = _PROFILE, include_discarded: bool = False
) -> OperationRequest[ModeloWorkListRequest]:
    return OperationRequest[ModeloWorkListRequest](
        definition_id=MODELO_WORK_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloWorkListRequest(profile_id=profile_id, include_discarded=include_discarded),
    )


def _context(registration, *, action: AccessAction = AccessAction.SUBMIT) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_result_rejects_foreign_duplicate_and_hidden_discarded_rows() -> None:
    active = ModeloWorkMetadataSnapshot.from_work_unit(_unit(_PROFILE, "1T"))
    foreign = ModeloWorkMetadataSnapshot.from_work_unit(_unit(_OTHER, "1T"))
    discarded = ModeloWorkMetadataSnapshot.from_work_unit(_unit(_PROFILE, "2T", discarded=True))
    valid = ModeloWorkListProjection(profile_id=_PROFILE, include_discarded=False, units=(active,))
    assert ModeloWorkListProjection.model_validate_json(valid.model_dump_json()) == valid
    for rows in ((active, active), (foreign,), (discarded,)):
        with pytest.raises(ValidationError):
            ModeloWorkListProjection(profile_id=_PROFILE, include_discarded=False, units=rows)
    assert ModeloWorkListProjection(profile_id=_PROFILE, include_discarded=True, units=(discarded,)).units == (
        discarded,
    )


def test_profile_wide_access_requires_unrestricted_period_ceiling() -> None:
    registry, registration = _registration()
    resolved = resolve_operation_access(
        registry=registry,
        request=cast(OperationRequest[BaseModel], cast(object, _request())),
        context=_context(registration),
    )
    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.allow_period_independent and resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions
    for periods in (frozenset({Period.from_year_and_code(2026, "1T")}), frozenset()):
        scope = AccessScope(
            operations=frozenset({MODELO_WORK_LIST_OPERATION_DEFINITION_ID}),
            actions=frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(),
            periods=periods,
            allow_period_independent=True,
            allow_delegation=False,
        )
        denied = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=scope)
        assert denied is not None and denied.code is AccessDenialCode.PERIOD_DENIED


@pytest.mark.parametrize("include_discarded", [False, True])
def test_executor_captures_canonical_exact_profile_rows_without_reordering(include_discarded: bool) -> None:
    units = (
        _unit(_OTHER, "1T"),
        _unit(_PROFILE, "2T", discarded=True),
        _unit(_PROFILE, "1T"),
    )
    repository = _Repository(units)
    factory = _factory(repository)
    recorded: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Events:
        async def phase(self, _code: str) -> None:
            pass

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            recorded.append(operand)
            return "f" * 64

    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=MODELO_WORK_LIST_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                ),
                events=Events(),
                operands=Operands(),
            ),
        ),
    )
    request = _request(include_discarded=include_discarded)
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        reference = asyncio.run(ModeloWorkListExecutor(factory).execute(request, context))
    assert reference == "f" * 64
    assert effects == [OperationEffect.NONE]
    result = ModeloWorkListProjection.model_validate(recorded[0])
    expected = list_work_units(bucket_id=str(_PROFILE), include_discarded=include_discarded, ports=factory())
    assert tuple(row.to_work_unit() for row in result.units) == expected
    assert all(row.bucket_id == str(_PROFILE) for row in result.units)
    wrong_repository = _Repository(units, bucket_id=str(_OTHER))
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError):
        asyncio.run(ModeloWorkListExecutor(_factory(wrong_repository)).execute(request, context))
    assert wrong_repository.loads == 0


def test_wrong_request_profile_refused_before_catalogue() -> None:
    registry, registration = _registration()
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], cast(object, _request(profile_id=_OTHER))),
            context=_context(registration),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
