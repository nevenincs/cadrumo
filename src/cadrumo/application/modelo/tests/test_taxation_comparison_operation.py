"""Registered work-unit taxation comparison keeps its profile and authority scope."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..taxation_comparison import (
    TaxationComparisonError,
    TaxationComparisonResult,
    TaxationRecommendation,
    compare_taxation_for_work_unit,
)
from ..taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonProjection,
    ModeloTaxationComparisonRequest,
    build_modelo_taxation_comparison_definition,
    build_modelo_taxation_comparison_registration,
)
from ..taxation_comparison_ports import TaxationComparisonPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_REVISION = "renta-test-2025"
_AUTHORITY = cast(PinnedAuthorityOperation, object())


def _unit(
    profile_id: UUID = _PROFILE,
    *,
    revision: str = _REVISION,
    modelo: str = "100",
) -> WorkUnit:
    period = Period.from_year_and_code(2025, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id), modelo=modelo, filing_year=2025, period=period, revision_id=revision
        ),
        bucket_id=str(profile_id),
        modelo=modelo,
        filing_year=2025,
        period=period,
        revision_id=revision,
        name="Annual declaration",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


class _Reader:
    def __init__(self, catalogue: WorkUnitCatalogue, *, bucket_id: str = str(_PROFILE)) -> None:
        self.catalogue = catalogue
        self.bucket_id = bucket_id
        self.loads = 0

    def load(self) -> WorkUnitCatalogue:
        self.loads += 1
        return self.catalogue


def _registered(reader: _Reader):
    factory_calls: list[str] = []

    def factory(*, bucket_id: str) -> TaxationComparisonPorts:
        factory_calls.append(bucket_id)
        return TaxationComparisonPorts(work_unit_reader=reader)

    definition = build_modelo_taxation_comparison_definition(factory)
    registration = build_modelo_taxation_comparison_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return factory, factory_calls, definition, registration, registry


def _request(
    unit: WorkUnit,
    *,
    profile_id: UUID = _PROFILE,
    subject_ref: str | None = None,
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref or profile_operation_subject(str(profile_id)),
        payload=ModeloTaxationComparisonRequest(profile_id=profile_id, work_unit_id=unit.work_unit_id),
    )


def _access_context(
    registration,
    *,
    action: AccessAction = AccessAction.SUBMIT,
    profile_id: UUID = _PROFILE,
    admitted=None,
    authority_operation: PinnedAuthorityOperation | None = _AUTHORITY,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
        authority_operation=authority_operation,
    )


def _comparison(*, revision: str = _REVISION) -> TaxationComparisonResult:
    return TaxationComparisonResult(
        filing_year=2025,
        modelo="100",
        revision=revision,
        conjunta_cuota_resultante=Decimal("1250.00"),
        individual_cuota_resultante=Decimal("1800.00"),
        conjunta_resultado=Decimal("900.00"),
        individual_resultado=Decimal("1450.00"),
        delta_resultado=Decimal("550.00"),
        recommendation=TaxationRecommendation.CONJUNTA,
        recommendation_reason="conjunta saves 550.00 €",
    )


def test_registered_access_pins_one_profile_period_and_tax_value_result() -> None:
    unit = _unit()
    reader = _Reader(WorkUnitCatalogue(work_units={unit.work_unit_id: unit}))
    _factory, factory_calls, definition, registration, registry = _registered(reader)
    request = _request(unit)

    admitted = resolve_operation_access(
        registry=registry,
        request=request,
        context=_access_context(registration),
    )

    assert definition.definition_id == MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID
    assert factory_calls == [str(_PROFILE)]
    assert reader.loads == 1
    assert admitted.request.profile_id == _PROFILE
    assert admitted.request.periods == frozenset({unit.period})
    assert admitted.request.period_independent is False

    result_context = _access_context(
        registration,
        action=AccessAction.RESULT,
        admitted=admitted.request,
    )
    result_access = resolve_operation_access(registry=registry, request=request, context=result_context)
    permission = next(iter(result_access.policy.disclosures))
    assert permission.category is DisclosureCategory.TAX_VALUES
    assert permission.destination_id == result_context.destination_id
    assert registration.contract.result_schema is not None
    assert permission.projection_id == registration.contract.result_schema.schema_id
    assert factory_calls == [str(_PROFILE)]
    assert reader.loads == 1


@pytest.mark.parametrize("failure", ["missing", "foreign_bucket"])
def test_registration_refuses_missing_or_foreign_work_unit(failure: str) -> None:
    unit = _unit(_OTHER_PROFILE) if failure == "foreign_bucket" else _unit()
    catalogue = WorkUnitCatalogue(work_units={} if failure == "missing" else {unit.work_unit_id: unit})
    reader = _Reader(catalogue)
    _factory, factory_calls, _definition, registration, registry = _registered(reader)
    request = _request(_unit())

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration),
        )

    # A foreign bucket's derived work-unit id cannot match the requested id;
    # it therefore resolves as unavailable inside this profile's catalogue.
    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
    assert factory_calls == [str(_PROFILE)]
    assert reader.loads == 1


def test_registration_refuses_foreign_profile_subject_and_missing_authority_before_read() -> None:
    unit = _unit()
    reader = _Reader(WorkUnitCatalogue(work_units={unit.work_unit_id: unit}))
    _factory, factory_calls, _definition, registration, registry = _registered(reader)

    for request, context in (
        (_request(unit, profile_id=_OTHER_PROFILE), _access_context(registration)),
        (_request(unit, subject_ref="profile:foreign"), _access_context(registration)),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=context)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH

    with pytest.raises(ProfileAccessRefusedError) as unavailable:
        resolve_operation_access(
            registry=registry,
            request=_request(unit),
            context=_access_context(registration, authority_operation=None),
        )
    assert unavailable.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert factory_calls == []
    assert reader.loads == 0


def _executor_context(
    request: OperationRequest[BaseModel],
    *,
    authority_operation: PinnedAuthorityOperation,
    stored: list[BaseModel],
    effects: list[OperationEffect],
    phases: list[str],
):
    class Events:
        async def phase(self, phase_code: str) -> None:
            phases.append(phase_code)

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            stored.append(operand)
            return "f" * 64

    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
                    subject_ref=request.subject_ref,
                ),
                authority_operation=authority_operation,
                events=Events(),
                operands=Operands(),
            ),
        ),
    )


def test_executor_passes_exact_bucket_and_owner_authority_and_stores_closed_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import taxation_comparison_operation as operation_module

    unit = _unit()
    request = _request(unit)
    reader = _Reader(WorkUnitCatalogue(work_units={unit.work_unit_id: unit}))
    factory_calls: list[str] = []
    ports = TaxationComparisonPorts(work_unit_reader=reader)

    def factory(*, bucket_id: str) -> TaxationComparisonPorts:
        factory_calls.append(bucket_id)
        return ports

    definition = build_modelo_taxation_comparison_definition(factory)
    authority = cast(PinnedAuthorityOperation, object())
    submitted: list[tuple[str, str, TaxationComparisonPorts, object]] = []

    def compare(work_unit_id: str, *, bucket_id: str, ports: TaxationComparisonPorts, operation: object):
        submitted.append((work_unit_id, bucket_id, ports, operation))
        return _comparison(revision=unit.revision_id)

    monkeypatch.setattr(operation_module, "compare_taxation_for_work_unit", compare)
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []
    phases: list[str] = []
    context = _executor_context(
        request,
        authority_operation=authority,
        stored=stored,
        effects=effects,
        phases=phases,
    )

    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert reference == "f" * 64
    assert factory_calls == [str(_PROFILE)]
    assert submitted == [(unit.work_unit_id, str(_PROFILE), ports, authority)]
    assert phases == [MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID]
    assert effects == [OperationEffect.NONE]
    assert len(stored) == 1
    projection = ModeloTaxationComparisonProjection.model_validate(stored[0])
    assert projection.profile_id == _PROFILE
    assert projection.work_unit_id == unit.work_unit_id
    assert projection.filing_year == unit.filing_year
    assert projection.modelo == str(unit.modelo)
    assert projection.revision == unit.revision_id
    assert projection.delta_resultado == "550.00"
    assert projection.individual_branch_single_earner_only is True
    assert "two-earner" in projection.individual_branch_caveat
    assert set(ModeloTaxationComparisonProjection.model_fields) == {
        "result_version",
        "profile_id",
        "work_unit_id",
        "filing_year",
        "modelo",
        "revision",
        "conjunta_cuota_resultante",
        "individual_cuota_resultante",
        "conjunta_resultado",
        "individual_resultado",
        "delta_resultado",
        "recommendation",
        "recommendation_reason",
        "individual_branch_single_earner_only",
        "individual_branch_caveat",
    }
    assert "sensitive_inputs" not in projection.model_dump_json()
    assert "casilla_values" not in projection.model_dump_json()


def test_executor_preserves_typed_comparison_refusal_and_rejects_oversized_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import taxation_comparison_operation as operation_module

    unit = _unit()
    request = _request(unit)
    ports = TaxationComparisonPorts(work_unit_reader=_Reader(WorkUnitCatalogue()))
    definition = build_modelo_taxation_comparison_definition(lambda **_kwargs: ports)
    authority = cast(PinnedAuthorityOperation, object())

    monkeypatch.setattr(
        operation_module,
        "compare_taxation_for_work_unit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TaxationComparisonError("private calculation detail")),
    )
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []
    phases: list[str] = []
    context = _executor_context(
        request,
        authority_operation=authority,
        stored=stored,
        effects=effects,
        phases=phases,
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(TaxationComparisonError) as refused:
        asyncio.run(definition.executor_factory.create().execute(request, context))
    assert str(refused.value) == "private calculation detail"
    assert stored == []
    assert effects == []

    monkeypatch.setattr(operation_module, "compare_taxation_for_work_unit", lambda *_args, **_kwargs: _comparison())
    monkeypatch.setattr(operation_module, "_MAX_RESULT_BYTES", 1)
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError) as oversized:
        asyncio.run(definition.executor_factory.create().execute(request, context))
    assert oversized.value.reason is AccessDenialCode.OPERATION_DENIED
    assert stored == []
    assert effects == []


def test_executor_requires_exact_active_profile_before_comparison() -> None:
    unit = _unit()
    request = _request(unit)
    calls: list[str] = []

    def factory(*, bucket_id: str) -> TaxationComparisonPorts:
        calls.append(bucket_id)
        return TaxationComparisonPorts(work_unit_reader=_Reader(WorkUnitCatalogue()))

    definition = build_modelo_taxation_comparison_definition(factory)
    authority = cast(PinnedAuthorityOperation, object())
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []
    phases: list[str] = []
    context = _executor_context(
        request,
        authority_operation=authority,
        stored=stored,
        effects=effects,
        phases=phases,
    )

    with (
        override_settings(cadrumo_active_profile=str(_OTHER_PROFILE)),
        pytest.raises(ProfileAccessRefusedError) as refused,
    ):
        asyncio.run(definition.executor_factory.create().execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert calls == []
    assert phases == []
    assert stored == []


def test_work_unit_revision_must_equal_the_pinned_registry_selection() -> None:
    selected = published_snapshot("100", filing_year=2025, period="0A")
    stale_unit = _unit(revision="stale-revision")

    class Authority:
        def __init__(self) -> None:
            self.selections: list[tuple[str, int, str]] = []

        def snapshot(self, modelo: str, *, filing_year: int, period: str):
            self.selections.append((modelo, filing_year, period))
            return selected

    class WorkUnits:
        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={stale_unit.work_unit_id: stale_unit})

    authority = Authority()
    with pytest.raises(TaxationComparisonError, match="no longer the published revision"):
        compare_taxation_for_work_unit(
            stale_unit.work_unit_id,
            bucket_id=str(_PROFILE),
            ports=TaxationComparisonPorts(work_unit_reader=WorkUnits()),
            operation=cast(PinnedAuthorityOperation, cast(object, authority)),
        )
    assert authority.selections == [("100", 2025, "0A")]


def test_work_unit_comparison_refuses_unproven_manual_and_relation_inputs() -> None:
    selected = published_snapshot("100", filing_year=2025, period="0A")
    unit = _unit(revision=selected.revision.id)

    class WorkUnits:
        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    authority = SimpleNamespace(snapshot=lambda _modelo, **_coordinates: selected)
    with pytest.raises(TaxationComparisonError, match="complete resolved tax-input basis"):
        compare_taxation_for_work_unit(
            unit.work_unit_id,
            bucket_id=str(_PROFILE),
            ports=TaxationComparisonPorts(work_unit_reader=WorkUnits()),
            operation=cast(PinnedAuthorityOperation, cast(object, authority)),
        )


def test_projection_rejects_non_finite_amount_and_unmodeled_scope() -> None:
    with pytest.raises(ValidationError):
        ModeloTaxationComparisonProjection(
            **(
                ModeloTaxationComparisonProjection.from_comparison(
                    _comparison(), profile_id=_PROFILE, work_unit_id=_unit().work_unit_id
                ).model_dump()
                | {"delta_resultado": "NaN"}
            )
        )

    unsupported = _comparison().model_copy(update={"modelo": "303"})
    with pytest.raises(TaxationComparisonError, match="unsupported filing scope"):
        ModeloTaxationComparisonProjection.from_comparison(
            unsupported,
            profile_id=_PROFILE,
            work_unit_id=_unit().work_unit_id,
        )
