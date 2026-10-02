"""Validated calculation prerequisites stay private, exact to Apply, and consumable once."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...operations.models import OperationRequest
from .. import operation_definitions
from .._edit_execution import _pre_effect_refusal
from ..action_errors import ModeloEditRefusedError, modelo_edit_refusal_error
from ..edit_contract import ModeloEditMutationFamily
from ..edit_models import (
    ModeloEditBaselineV1,
    ModeloEditDomainRefusalV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ..edit_refusal_projection import ModeloEditCalculationPrerequisiteV1, ModeloEditRefusalProjectionStore
from .test_edit_models import _baseline as admitted_baseline

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
    outcome = _pre_effect_refusal(_error(casilla_id="1388", binding_id=_BINDING), revision=_revision())
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
    refusal = _pre_effect_refusal(_error(**context), revision=_revision()).refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.address is None and refusal.evidence == ()
    assert "calculation_source_unresolved" not in refusal.facts


def _baseline() -> ModeloEditBaselineV1:
    return ModeloEditBaselineV1.model_construct(
        work_unit_id="a" * 64,
        baseline_id="b" * 64,
        current_calculation_revision_id="c" * 64,
    )


def _prerequisite() -> ModeloEditCalculationPrerequisiteV1:
    return ModeloEditCalculationPrerequisiteV1(
        operation_id="d" * 64,
        work_unit_id="a" * 64,
        baseline_id="b" * 64,
        calculation_revision_id="c" * 64,
        casilla_id="1388",
        binding_ids=(_BINDING,),
    )


def test_only_the_registered_renewed_baseline_can_deliver_and_be_consumed_once() -> None:
    store = ModeloEditRefusalProjectionStore()
    prerequisite = _prerequisite()
    store.observe(prerequisite)
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None
    store.expect(prerequisite.operation_id, _baseline())
    store.observe(replace(prerequisite, baseline_id="e" * 64))
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None
    store.expect(prerequisite.operation_id, _baseline())
    store.observe(prerequisite)
    assert (
        store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) == prerequisite
    )
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None


@pytest.mark.parametrize("work,head", [("e" * 64, "c" * 64), ("a" * 64, "e" * 64)])
def test_a_replaced_work_coordinate_discards_the_private_projection(work: str, head: str) -> None:
    store = ModeloEditRefusalProjectionStore()
    prerequisite = _prerequisite()
    store.expect(prerequisite.operation_id, _baseline())
    store.observe(prerequisite)
    assert store.take(prerequisite.operation_id, work_unit_id=work, calculation_revision_id=head) is None
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None


def test_terminal_consumption_and_session_cleanup_remove_unfulfilled_context() -> None:
    store = ModeloEditRefusalProjectionStore()
    prerequisite = _prerequisite()
    store.expect(prerequisite.operation_id, _baseline())
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None
    store.observe(prerequisite)
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None
    store.expect(prerequisite.operation_id, _baseline())
    store.observe(prerequisite)
    store.clear()
    assert store.take(prerequisite.operation_id, work_unit_id="a" * 64, calculation_revision_id="c" * 64) is None


@pytest.mark.asyncio
async def test_observer_failure_keeps_the_exact_registered_refusal_and_none_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = admitted_baseline()
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
        definition_id=operation_definitions.MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        subject_ref=baseline.work_unit_id,
        payload=operation_definitions.ModeloEditApplyOperationRequestV1(
            submission=operation_definitions.ModeloEditApplySubmissionV1.from_submission(submission)
        ),
    )
    refusal = _pre_effect_refusal(_error(casilla_id="1388", binding_id=_BINDING), revision=_revision())
    monkeypatch.setattr(operation_definitions, "apply_modelo_edit", lambda *args, **kwargs: refusal)
    effects: list[object] = []

    class Events:
        async def phase(self, code: str) -> None:
            del code

        async def effect(self, effect: object) -> None:
            effects.append(effect)

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
        ),
    )
    with pytest.raises(ModeloEditRefusedError) as caught:
        await executor.execute(request, context)
    assert [str(effect) for effect in effects] == ["unknown", "none"]
    assert len(delivered) == 1 and delivered[0].baseline_id == str(baseline.baseline_id)
    assert _BINDING not in str(caught.value.context) and "1388" not in str(caught.value.context)
