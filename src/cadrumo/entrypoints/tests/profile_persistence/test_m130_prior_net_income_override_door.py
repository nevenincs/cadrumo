"""A Modelo 130 whose stored earlier Modelo 100 cannot show box 13's source is refused with the door to state it.

Box 13 of a Modelo 130 reduces the payment by the previous year's net income
from the economic activity, read from boxes of the previous year's Modelo 100.
When that return is stored but does not show those boxes, the carry is unknown,
never zero, so the calculation refuses. The refusal names the box, the earlier
return and the boxes it lacks, and opens the override bound to this work unit
and input, leaving the amount to the operator. Stating the amount through the
guarded edit lets the declaration calculate, and a later recalculation keeps it.
An edit of another input, admitted while box 13's source is still unshown,
settles under that same refusal, worded again from its public coordinates.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production calculate and edit executors.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from ....application.modelo.edit_value_grammar import ModeloEditValueFamily
from ....application.modelo.work_missing_input import ModeloWorkMissingInputError
from ....application.operations.error_detail import build_operation_error_detail
from ....application.operations.next_step import OperationOpenWorkStepV1
from ....core.casilla_id import validated_casilla_id
from ....core.operator_action_enums import ActionArgumentStatus
from ....domain.calculations.registry.modelo_localization import binding_label_text
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import seeded_operator_work
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PRIOR_NET_INCOME = "irpf.previous_year_economic_activity_net_income"
_BOX = "13"
#: A box of the earlier Modelo 100 that is not one box 13 reads.
_UNRELATED_M100_BOX = validated_casilla_id("0001", surface="_UNRELATED_M100_BOX")


def _save_unrelated_prior_m100(year: int) -> None:
    """A stored Modelo 100 of the previous year that shows none of the boxes box 13 reads."""
    save_stamped_observation(
        CalculationObservationRepository(),
        registry_grounded_modelo_observation(
            modelo="100",
            filing_year=year - 1,
            period="0A",
            casilla_values={_UNRELATED_M100_BOX: Decimal("10")},
        ),
        source_kind="app_filing",
    )


def test_box_13_without_its_source_boxes_opens_the_override_and_stating_it_lets_the_130_calculate(
    tmp_path: Path,
) -> None:
    year = filing_year_envelope().horizon
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=year, period_code="1T") as work,
    ):
        _save_unrelated_prior_m100(year)

        with pytest.raises(ModeloWorkMissingInputError) as refused:
            work.recalculate()
        assert work.head() is None

        detail = build_operation_error_detail(refused.value)
        assert detail is not None
        assert detail.error_code == "REFUSED_MODELO_WORK_INPUT_REQUIRED"
        assert detail.message_key == "application.modelo.errors.previous_filing_unobserved"
        words = detail.refusal_words
        assert words is not None
        assert "%{" not in words
        assert _BOX in words
        # The input is named as the form names it, by its declared label, never by its binding id.
        assert detail.refusal_words_language is not None
        label = binding_label_text("130", _PRIOR_NET_INCOME, locale=detail.refusal_words_language.value)
        assert label != _PRIOR_NET_INCOME
        assert label in words
        assert _PRIOR_NET_INCOME not in words
        assert str(year - 1) in words
        assert isinstance(detail.next_step, OperationOpenWorkStepV1)
        assert detail.next_step.work_unit_id == work.work_unit_id
        assert detail.precondition_verdict_json is not None
        verdict = json.loads(detail.precondition_verdict_json)
        assert verdict["failed_condition_id"] == "modelo.work.calculate.input.supplied"
        assert verdict["action"]["action_id"] == "operator.modelo.work.override"
        bound = {entry["argument_name"]: entry for entry in verdict["argument_bindings"]}
        assert bound["work_unit_id"]["value"] == work.work_unit_id
        assert bound["binding_id"]["value"] == _PRIOR_NET_INCOME
        assert bound["value"]["status"] == ActionArgumentStatus.MISSING.value
        (evidence,) = verdict["evidence"]
        assert evidence["values"]["source_modelo"] == "100"
        assert evidence["values"]["source_filing_year"] == str(year - 1)
        assert evidence["values"]["source_period"] == "0A"

        # Following the door: the operator states the previous year's net income.
        applied = work.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=bound["binding_id"]["value"]),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=Decimal("8000.00"),
                ),
            )
        )
        assert applied.refusal is None
        head = work.require_head()
        # A previous-year net income of 9,000 euros or less reduces the payment by the full 100 euros.
        assert head.casilla_values[_BOX] == Decimal("100")

        recalculated = work.recalculate()
        assert recalculated.casilla_values[_BOX] == Decimal("100")
        layer = recalculated.operator_layer
        assert layer is not None
        assert Decimal(layer.binding_overrides[_PRIOR_NET_INCOME]) == Decimal("8000.00")


def test_an_edit_of_another_input_settles_under_the_worded_unobserved_source_refusal(tmp_path: Path) -> None:
    """The edit's value is admitted; the recalculation's refusal names box 13's source boxes and opens its override."""
    year = filing_year_envelope().horizon
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=year, period_code="1T") as work,
    ):
        _save_unrelated_prior_m100(year)
        other = next(
            entry.binding_id
            for entry in work.baseline().permitted_surface
            if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
            and entry.binding_id != _PRIOR_NET_INCOME
            and ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in entry.allowed_intents
            and entry.grammar.family is ModeloEditValueFamily.DECIMAL
        )
        refused = work.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=other),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=Decimal("0"),
                ),
            )
        )
        head = work.head()

    assert refused.refusal is not None
    assert head is None
    detail = build_operation_error_detail(refused.refusal)
    assert detail is not None
    assert detail.error_code == "REFUSED_MODELO_WORK_INPUT_REQUIRED"
    assert detail.message_key == "application.modelo.errors.previous_filing_unobserved"
    words = detail.refusal_words
    assert words is not None
    assert "%{" not in words
    assert detail.refusal_words_language is not None
    label = binding_label_text("130", _PRIOR_NET_INCOME, locale=detail.refusal_words_language.value)
    assert label in words
    assert _PRIOR_NET_INCOME not in words
    assert _BOX in words
    assert str(year - 1) in words
    assert detail.precondition_verdict_json is not None
    verdict = json.loads(detail.precondition_verdict_json)
    assert verdict["failed_condition_id"] == "modelo.work.calculate.input.supplied"
    assert verdict["action"]["action_id"] == "operator.modelo.work.override"
    assert [evidence["values"] for evidence in verdict["evidence"]] == [{"edit_values_admitted": True}]
