"""Registered work-unit taxation comparison keeps its profile and authority scope."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, DisclosureCategory

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationFrontendProjection, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationRegistry
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..calculation_action_ports import CalculationActionPorts
from ..taxation_comparison import (
    TaxationComparisonError,
    TaxationComparisonRefusal,
    TaxationComparisonResult,
    TaxationRecommendation,
    TaxationRecommendationReason,
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
from .registration_access_context_support import registration_access_context

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_YEAR = newest_authored_edition("100")
_NOW = datetime(filing_year_envelope().horizon, 4, 10, 9, 0, tzinfo=UTC)
_REVISION = f"renta-test-{_YEAR}"
_AUTHORITY = cast(PinnedAuthorityOperation, object())
_CALCULATION_PORTS = cast(CalculationActionPorts, object())


def _unused_calculation_ports(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_record: object | None = None,
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
) -> CalculationActionPorts:
    del bucket_id, operation, profile_record, mutation_writer
    pytest.fail("access resolution must not build calculation ports")


def _unit(
    profile_id: UUID = _PROFILE,
    *,
    revision: str = _REVISION,
    modelo: str = "100",
) -> WorkUnit:
    period = Period.from_year_and_code(_YEAR, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id), modelo=modelo, filing_year=_YEAR, period=period, revision_id=revision
        ),
        bucket_id=str(profile_id),
        modelo=modelo,
        filing_year=_YEAR,
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

    definition = build_modelo_taxation_comparison_definition(_unused_calculation_ports)
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
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
) -> OperationAccessContext:
    return registration_access_context(
        registration,
        profile_id=profile_id,
        action=action,
        frontend=frontend,
        authority_operation=authority_operation,
        admitted_request=admitted,
    )


def _comparison(*, revision: str = _REVISION) -> TaxationComparisonResult:
    return TaxationComparisonResult(
        filing_year=_YEAR,
        modelo="100",
        revision=revision,
        conjunta_cuota_resultante=Decimal("1250.00"),
        individual_cuota_resultante=Decimal("1800.00"),
        conjunta_resultado=Decimal("900.00"),
        individual_resultado=Decimal("1450.00"),
        delta_resultado=Decimal("550.00"),
        recommendation=TaxationRecommendation.CONJUNTA,
        recommendation_reason=TaxationRecommendationReason.CONJUNTA_LOWER_RESULT,
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


def test_taxation_comparison_is_admitted_on_the_external_client_frontend_without_a_commit_door() -> None:
    unit = _unit()
    reader = _Reader(WorkUnitCatalogue(work_units={unit.work_unit_id: unit}))
    _factory, _factory_calls, _definition, registration, registry = _registered(reader)

    resolved = resolve_operation_access(
        registry=registry,
        request=_request(unit),
        context=_access_context(registration, frontend=OperationFrontendProjection.EXTERNAL_CLIENT),
    )
    assert resolved.request.frontend is OperationFrontendProjection.EXTERNAL_CLIENT
    assert resolved.request.periods == frozenset({unit.period})
    assert AccessAction.COMMIT not in resolved.policy.actions


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
    factory_calls: list[tuple[str, PinnedAuthorityOperation]] = []

    def factory(
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
        profile_record: object | None = None,
        mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    ) -> CalculationActionPorts:
        del mutation_writer
        assert profile_record is None
        factory_calls.append((bucket_id, operation))
        return _CALCULATION_PORTS

    definition = build_modelo_taxation_comparison_definition(factory)
    authority = cast(PinnedAuthorityOperation, object())
    submitted: list[tuple[str, str, CalculationActionPorts]] = []

    def compare(work_unit_id: str, *, bucket_id: str, ports: CalculationActionPorts):
        submitted.append((work_unit_id, bucket_id, ports))
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

    with override_settings(cadrumo_active_profile=str(_PROFILE), cadrumo_output_language="en"):
        reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert reference == "f" * 64
    assert factory_calls == [(str(_PROFILE), authority)]
    assert submitted == [(unit.work_unit_id, str(_PROFILE), _CALCULATION_PORTS)]
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
    assert projection.result_version == 2
    assert projection.recommendation_reason is TaxationRecommendationReason.CONJUNTA_LOWER_RESULT
    assert projection.words_language is OutputLanguage.EN
    euro = chr(0xA0) + "€"
    assert projection.recommendation_reason_words == (
        f"Joint filing comes out lower: your result is 900.00{euro} jointly and 1,450.00{euro} individually, "
        f"a difference of 550.00{euro}."
    )
    assert "two separate returns" in projection.individual_branch_caveat
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
        "recommendation_reason_words",
        "words_language",
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
    definition = build_modelo_taxation_comparison_definition(lambda **_kwargs: _CALCULATION_PORTS)
    authority = cast(PinnedAuthorityOperation, object())

    monkeypatch.setattr(
        operation_module,
        "compare_taxation_for_work_unit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            TaxationComparisonError(TaxationComparisonRefusal.NOT_CALCULATED)
        ),
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
    assert refused.value.refusal is TaxationComparisonRefusal.NOT_CALCULATED
    assert stored == []
    assert effects == []

    monkeypatch.setattr(operation_module, "compare_taxation_for_work_unit", lambda *_args, **_kwargs: _comparison())
    monkeypatch.setattr(operation_module, "PROJECTION_RESULT_MAX_BYTES", 1)
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError) as oversized:
        asyncio.run(definition.executor_factory.create().execute(request, context))
    assert oversized.value.reason is AccessDenialCode.OPERATION_DENIED
    assert stored == []
    assert effects == []


def test_executor_requires_exact_active_profile_before_comparison() -> None:
    unit = _unit()
    request = _request(unit)
    calls: list[str] = []

    def factory(
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
        profile_record: object | None = None,
        mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    ) -> CalculationActionPorts:
        del mutation_writer
        del operation, profile_record
        calls.append(bucket_id)
        return _CALCULATION_PORTS

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


def _comparison_ports(unit: WorkUnit, authority: object) -> CalculationActionPorts:
    class WorkUnits:
        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    class Calculations:
        def load(self, *, operation: object = None) -> SimpleNamespace:
            del operation
            return SimpleNamespace(get=lambda _revision_id: None)

    return cast(
        CalculationActionPorts,
        cast(
            object,
            SimpleNamespace(
                operation=authority, work_unit_repository=WorkUnits(), calculation_repository=Calculations()
            ),
        ),
    )


def test_work_unit_revision_must_equal_the_pinned_registry_selection() -> None:
    selected = published_snapshot("100", filing_year=_YEAR, period="0A")
    stale_unit = _unit(revision="stale-revision")
    selections: list[tuple[str, int, str]] = []

    def snapshot(modelo: str, *, filing_year: int, period: str):
        selections.append((modelo, filing_year, period))
        return selected

    with pytest.raises(TaxationComparisonError) as refused:
        compare_taxation_for_work_unit(
            stale_unit.work_unit_id,
            bucket_id=str(_PROFILE),
            ports=_comparison_ports(stale_unit, SimpleNamespace(reading_snapshot=snapshot)),
        )
    assert refused.value.refusal is TaxationComparisonRefusal.REVISION_OUTDATED
    assert selections == [("100", _YEAR, "0A")]


def test_work_unit_without_a_calculation_refuses_before_any_run() -> None:
    selected = published_snapshot("100", filing_year=_YEAR, period="0A")
    unit = _unit(revision=selected.revision.id)
    authority = SimpleNamespace(reading_snapshot=lambda _modelo, **_coordinates: selected)

    with pytest.raises(TaxationComparisonError) as refused:
        compare_taxation_for_work_unit(
            unit.work_unit_id, bucket_id=str(_PROFILE), ports=_comparison_ports(unit, authority)
        )
    assert refused.value.refusal is TaxationComparisonRefusal.NOT_CALCULATED


def test_revision_without_a_filing_mode_refuses_as_not_declared() -> None:
    selected = published_snapshot("303", filing_year=_YEAR, period="3T")
    unit = _unit(revision=selected.revision.id, modelo="303")
    authority = SimpleNamespace(reading_snapshot=lambda _modelo, **_coordinates: selected)

    with pytest.raises(TaxationComparisonError) as refused:
        compare_taxation_for_work_unit(
            unit.work_unit_id, bucket_id=str(_PROFILE), ports=_comparison_ports(unit, authority)
        )
    assert refused.value.refusal is TaxationComparisonRefusal.NOT_DECLARED


def test_projection_rejects_non_finite_amount_and_unmodeled_scope() -> None:
    with pytest.raises(ValidationError):
        ModeloTaxationComparisonProjection.model_validate(
            ModeloTaxationComparisonProjection.from_comparison(
                _comparison(), profile_id=_PROFILE, work_unit_id=_unit().work_unit_id
            ).model_dump()
            | {"delta_resultado": "NaN"}
        )

    with pytest.raises(ValidationError, match="does not belong to its recommendation"):
        ModeloTaxationComparisonProjection.model_validate(
            ModeloTaxationComparisonProjection.from_comparison(
                _comparison(), profile_id=_PROFILE, work_unit_id=_unit().work_unit_id
            ).model_dump()
            | {"recommendation_reason": TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT}
        )

    unsupported = _comparison().model_copy(update={"modelo": "303"})
    with pytest.raises(TaxationComparisonError) as refused:
        ModeloTaxationComparisonProjection.from_comparison(
            unsupported,
            profile_id=_PROFILE,
            work_unit_id=_unit().work_unit_id,
        )
    assert refused.value.refusal is TaxationComparisonRefusal.NOT_DECLARED
