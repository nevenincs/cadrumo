"""Validated calculation prerequisites stay private, exact to Apply, and consumable once."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ....domain.calculations.registry.bindings_previous_filing import previous_filing_binding_source_casilla_ids
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.tests.financial_operand_delivery import deliver_financial_operand
from .. import edit_operation as operation_definitions
from ..action_errors import ModeloEditRefusedError, modelo_edit_refusal_error
from ..edit_contract import ModeloEditMutationFamily
from ..edit_execution import pre_effect_refusal
from ..edit_models import (
    ModeloEditDomainRefusalV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ..edit_operation_requests import ModeloEditApplyOperationRequestV2
from ..edit_refusal_projection import ModeloEditCalculationPrerequisiteV1, ModeloEditRefusalProjectionStore
from ..edit_transient_operand import modelo_edit_financial_operand
from ..operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ..reconciliation_sources import ReconciliationSourceNeed, ReconciliationSourceStanding
from ..work_missing_input import ModeloPriorPeriodUnfiledError
from .test_edit_models import edit_models_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BINDING = "prior-general-loss"


def _revision() -> ModeloRevision:
    return ModeloRevision.model_construct(
        casillas=(CasillaDefinition.model_construct(id="1388", input_kind=InputKind.BOUND, binding=_BINDING),),
        bindings=(BindingDefinition.model_construct(id=_BINDING),),
    )


def _error(**context: object) -> RegistryValidationError:
    return RegistryValidationError(
        "private exception sentence must never travel to the interface",
        translated_message="errors.calc.bound_casilla_binding_value_missing",
        context=context,
    )


def test_a_known_producer_names_only_revision_validated_prerequisite_coordinates() -> None:
    outcome = pre_effect_refusal(_error(casilla_id="1388", binding_id=_BINDING), revision=_revision())
    refusal = outcome.refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.address == ModeloEditScalarAddressV1(casilla_id="1388")
    assert refusal.evidence == (_BINDING,)
    assert "calculation_source_unresolved" in refusal.facts
    assert "private exception" not in refusal.model_dump_json()
    public = modelo_edit_refusal_error(refusal)
    assert "1388" not in str(public.context) and _BINDING not in str(public.context)


@pytest.mark.parametrize(
    "context",
    [
        {},
        {"casilla_id": "other", "binding_id": _BINDING},
        {"casilla_id": "1388", "binding_id": "unknown"},
        {"casilla_id": "1388", "binding_id": [_BINDING]},
        {"casilla_id": "1388", "binding_id": _BINDING + "," + _BINDING},
    ],
)
def test_unknown_or_malformed_producer_context_retains_only_the_safe_family(context: dict[str, object]) -> None:
    refusal = pre_effect_refusal(_error(**context), revision=_revision()).refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.address is None and refusal.evidence == ()
    assert "calculation_source_unresolved" not in refusal.facts


def test_a_carry_waiting_on_an_unfiled_earlier_period_names_the_box_it_feeds() -> None:
    support = published_supported_filing_years()
    assert support is not None
    unfiled = ModeloPriorPeriodUnfiledError(
        _error(binding_id=_BINDING),
        binding_id=_BINDING,
        source_needs=(
            ReconciliationSourceNeed(
                modelo="130",
                period=Period.from_year_and_code(support.horizon, "1T"),
                standing=ReconciliationSourceStanding.MISSING,
                unit=None,
            ),
        ),
        translated_message="application.modelo.errors.prior_period_unfiled",
        context={"modelo": "130", "filing_year": support.horizon, "period": "2T", "unfiled_period": "1T"},
        precondition_verdict=None,
        next_step=None,
    )

    refusal = pre_effect_refusal(unfiled, revision=_revision()).refusal

    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.address == ModeloEditScalarAddressV1(casilla_id="1388")
    assert refusal.evidence == (_BINDING,)
    assert "calculation_source_unresolved" in refusal.facts


def _modelo_100_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    return tuple(sorted(support.years))


@pytest.mark.parametrize("year", _modelo_100_years())
def test_an_earlier_return_that_cannot_show_a_carry_names_the_first_box_the_carries_feed(
    year: int, *, operation: PinnedAuthorityOperation
) -> None:
    revision = operation.snapshot(
        "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    carried = ("1384", "1387", "1390", "1391")
    carries = tuple(
        binding.id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.PREVIOUS_FILING
        and set(previous_filing_binding_source_casilla_ids(binding)) & set(carried)
    )
    assert carries, "the Modelo 100 carries the negative general base pending from the earlier return"
    error = RegistryValidationError.for_previous_filing_casillas_unobserved(
        source_modelo="100",
        source_filing_year=year - 1,
        source_period="0A",
        casilla_ids=carried,
        binding_ids=carries,
    )

    refusal = pre_effect_refusal(error, revision=revision).refusal

    first = next(casilla for casilla in revision.casillas if set(bound_casilla_binding_ids(casilla)) & set(carries))
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.address == ModeloEditScalarAddressV1(casilla_id=first.id)
    assert set(refusal.evidence) == set(bound_casilla_binding_ids(first)) & set(carries)
    assert "calculation_source_unresolved" in refusal.facts


def _prerequisite() -> ModeloEditCalculationPrerequisiteV1:
    return ModeloEditCalculationPrerequisiteV1(
        operation_id="d" * 64,
        work_unit_id="a" * 64,
        baseline_id="b" * 64,
        calculation_revision_id="c" * 64,
        casilla_id="1388",
        binding_ids=(_BINDING,),
    )


def _take(store: ModeloEditRefusalProjectionStore, **coordinates: str) -> ModeloEditCalculationPrerequisiteV1 | None:
    exact = {"work_unit_id": "a" * 64, "baseline_id": "b" * 64, "calculation_revision_id": "c" * 64}
    return store.take("d" * 64, **{**exact, **coordinates})


def test_a_retained_prerequisite_is_consumed_once_by_its_exact_apply() -> None:
    store = ModeloEditRefusalProjectionStore()
    assert _take(store) is None
    store.retain(_prerequisite())
    assert _take(store) == _prerequisite()
    assert _take(store) is None


@pytest.mark.parametrize(
    "coordinates",
    [
        {"work_unit_id": "e" * 64},
        {"baseline_id": "e" * 64},
        {"calculation_revision_id": "e" * 64},
    ],
)
def test_a_read_naming_other_coordinates_discards_the_prerequisite_unread(coordinates: dict[str, str]) -> None:
    store = ModeloEditRefusalProjectionStore()
    store.retain(_prerequisite())
    assert _take(store, **coordinates) is None
    assert _take(store) is None


def test_the_store_forgets_the_oldest_prerequisite_beyond_its_bound() -> None:
    store = ModeloEditRefusalProjectionStore()
    retained = [replace(_prerequisite(), operation_id=f"{index:064x}") for index in range(17)]
    for prerequisite in retained:
        store.retain(prerequisite)
    exact = {"work_unit_id": "a" * 64, "baseline_id": "b" * 64, "calculation_revision_id": "c" * 64}
    assert store.take(retained[0].operation_id, **exact) is None
    assert store.take(retained[-1].operation_id, **exact) == retained[-1]


@pytest.mark.asyncio
async def test_observer_failure_keeps_the_exact_registered_refusal_and_none_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = edit_models_baseline().model_copy(update={"bucket_id": "13000000-0000-4000-8000-000000000730"})
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id="06"),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=Decimal(1),
            ),
        ),
    )
    request = OperationRequest(
        definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        subject_ref=baseline.work_unit_id,
        payload=ModeloEditApplyOperationRequestV2(
            profile_id=UUID(baseline.bucket_id),
            work_unit_id=baseline.work_unit_id,
            financial_baseline_ref=baseline.baseline_id,
        ),
    )
    refusal = pre_effect_refusal(_error(casilla_id="1388", binding_id=_BINDING), revision=_revision())
    monkeypatch.setattr(operation_definitions, "apply_modelo_edit", lambda *args, **kwargs: refusal)
    effects: list[object] = []

    class Events:
        async def phase(self, code: str) -> None:
            del code

        async def effect(self, effect: object) -> None:
            effects.append(effect)

    @asynccontextmanager
    async def irreversible_section() -> AsyncGenerator[None]:
        yield

    delivered: list[ModeloEditCalculationPrerequisiteV1] = []

    def unavailable(prerequisite: ModeloEditCalculationPrerequisiteV1) -> None:
        delivered.append(prerequisite)
        raise RuntimeError("private diagnostic consumer unavailable")

    executor = operation_definitions.ModeloEditApplyExecutor(
        calculation_action_ports_factory=cast(Any, lambda **kwargs: None),
        receipt_repository_factory=cast(Any, lambda **kwargs: None),
        prerequisite_observer=unavailable,
    )
    context = cast(
        Any,
        SimpleNamespace(
            events=Events(),
            identity=SimpleNamespace(operation_id="d" * 64),
            authority_operation=None,
            cancellation=SimpleNamespace(irreversible_section=irreversible_section),
        ),
    )
    async with deliver_financial_operand(
        identity=OperationIdentity(
            operation_id="d" * 64, definition_id=request.definition_id, subject_ref=baseline.work_unit_id
        ),
        declaration=modelo_edit_financial_operand(None),
        operand=submission,
    ) as access:
        context.typed_financial_operand = access
        with pytest.raises(ModeloEditRefusedError) as caught:
            await executor.execute(request, context)
    assert [str(effect) for effect in effects] == ["unknown", "none"]
    assert len(delivered) == 1 and delivered[0].baseline_id == str(baseline.baseline_id)
    assert _BINDING not in str(caught.value.context) and "1388" not in str(caught.value.context)
