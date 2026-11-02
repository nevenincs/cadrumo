"""The form asks for the answers a calculation refuses to run without, instead of presenting them as optional.

Every expectation about what the engine refuses without is read from the engine
itself: the 2025 Modelo 100 is calculated over the published registry with one
answer left out, and the refusal names the binding. The form is then built by
the real builder, and must ask for exactly the boxes those refusals belong to --
the earlier year's negative base (1388) always, and the normal direct
estimation answer (0168) only for a filer whose profile states an economic
activity, since the calculation reads it only behind that fact.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.modelo_100_registry_support import neutral_binding_values
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ..calculation_required_inputs import calculation_required_inputs
from ..work_form_models import ModeloFormOrigin, ModeloFormStanding, ModeloWorkForm, section_fields
from .work_form_fixture import built_form, form_casilla, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = 2025
_SALARY: CasillaId = validated_casilla_id("0003", surface="_SALARY")
_EARLIER_NEGATIVE_BASE_BOX = "1388"
_EARLIER_NEGATIVE_BASE: BindingId = "renta-base-liquidable-negativa-general-anterior"
_DIRECT_ESTIMATION_BOX = "0168"
_DIRECT_ESTIMATION: BindingId = "renta-modelo-100-estimacion-directa-es-normal"
_ECONOMIC_ACTIVITY: BindingId = "renta-profile-has-economic-activity"


def _calculation_snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("100", filing_year=_YEAR, period="0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate_without(snapshot: RegistrySnapshot, *, activity: bool, omitted: BindingId | None) -> None:
    """Run the engine over every binding's neutral answer, leaving ``omitted`` unanswered."""
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    booleans[_ECONOMIC_ACTIVITY] = activity
    booleans[_DIRECT_ESTIMATION] = True
    decimals["renta-profile-declaration-type"] = Decimal(1)
    if omitted is not None:
        decimals.pop(omitted, None)
        booleans.pop(omitted, None)
    calculate_registry_snapshot(
        snapshot,
        inputs={
            _SALARY: Decimal("30000.00"),
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals),
        },
        date_context={"filing_period": date(_YEAR, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


def _refused_binding(snapshot: RegistrySnapshot, *, activity: bool, omitted: BindingId) -> str:
    with pytest.raises(RegistryValidationError) as refused:
        _calculate_without(snapshot, activity=activity, omitted=omitted)
    assert refused.value.translated_message in {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
    }
    return str((refused.value.context or {}).get("binding_id"))


# -- what the engine refuses without -------------------------------------------


def test_the_engine_runs_when_every_answer_is_given(operation: PinnedAuthorityOperation) -> None:
    _calculate_without(_calculation_snapshot(operation), activity=True, omitted=None)


def test_the_engine_refuses_without_the_earlier_negative_base_whoever_the_filer_is(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _calculation_snapshot(operation)

    for activity in (True, False):
        assert _refused_binding(snapshot, activity=activity, omitted=_EARLIER_NEGATIVE_BASE) == _EARLIER_NEGATIVE_BASE


def test_the_engine_refuses_without_the_direct_estimation_answer_only_for_a_filer_with_an_activity(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _calculation_snapshot(operation)

    assert _refused_binding(snapshot, activity=True, omitted=_DIRECT_ESTIMATION) == _DIRECT_ESTIMATION
    _calculate_without(snapshot, activity=False, omitted=_DIRECT_ESTIMATION)


# -- what the registry says the form must ask for -------------------------------


def test_the_inputs_named_are_the_ones_the_engine_refused_without(operation: PinnedAuthorityOperation) -> None:
    revision = _calculation_snapshot(operation).revision

    def named(truths: dict[str, bool] | None) -> set[str]:
        return {
            str(item)
            for item in calculation_required_inputs(revision, registry_period="0A", known_truths=truths).casilla_ids
        }

    assert named(None) == {_EARLIER_NEGATIVE_BASE_BOX}
    assert named({_ECONOMIC_ACTIVITY: False}) == {_EARLIER_NEGATIVE_BASE_BOX}
    assert named({_ECONOMIC_ACTIVITY: True}) == {_EARLIER_NEGATIVE_BASE_BOX, _DIRECT_ESTIMATION_BOX}


def test_a_carry_between_periods_of_one_year_is_not_named(operation: PinnedAuthorityOperation) -> None:
    """Modelo 130's earlier instalments are produced by this campaign's own declarations; the form waits for them."""
    revision = form_snapshot(operation, "130", 2026, "2T").revision

    assert calculation_required_inputs(revision, registry_period="2T").casilla_ids == frozenset()


# -- what the form asks ---------------------------------------------------------


def _needs_you(form: ModeloWorkForm) -> set[str]:
    return {
        str(field.address.casilla_id)
        for page in form.pages
        for section in page.sections
        for field in section_fields(section)
        if field.standing is ModeloFormStanding.NEEDS_YOU and hasattr(field.address, "casilla_id")
    }


def test_the_earlier_negative_base_needs_the_filer_instead_of_waiting_for_an_import(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "100", _YEAR, "0A")

    field = form_casilla(form, _EARLIER_NEGATIVE_BASE_BOX)
    assert field.origin is ModeloFormOrigin.NEEDS_INPUT
    assert field.standing is ModeloFormStanding.NEEDS_YOU
    # Verification's own set is unchanged: the form asks for what the calculation needs, not more of the check.
    assert not field.required
    assert _EARLIER_NEGATIVE_BASE_BOX in _needs_you(form)


def test_the_direct_estimation_answer_is_asked_of_a_filer_with_an_activity_only(
    operation: PinnedAuthorityOperation,
) -> None:
    unknown = form_casilla(built_form(operation, "100", _YEAR, "0A"), _DIRECT_ESTIMATION_BOX)
    without = form_casilla(
        built_form(operation, "100", _YEAR, "0A", known_truths={_ECONOMIC_ACTIVITY: False}), _DIRECT_ESTIMATION_BOX
    )
    with_activity = form_casilla(
        built_form(operation, "100", _YEAR, "0A", known_truths={_ECONOMIC_ACTIVITY: True}), _DIRECT_ESTIMATION_BOX
    )

    # A fact the form does not know claims nothing; a filer without an activity is never asked.
    assert unknown.origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert without.origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert with_activity.origin is ModeloFormOrigin.NEEDS_INPUT
    assert with_activity.standing is ModeloFormStanding.NEEDS_YOU


def test_a_held_answer_is_confirmed_not_asked_again(operation: PinnedAuthorityOperation) -> None:
    form = built_form(
        operation,
        "100",
        _YEAR,
        "0A",
        held={_EARLIER_NEGATIVE_BASE_BOX: Decimal("0"), _DIRECT_ESTIMATION_BOX: "N"},
        entered=frozenset({_DIRECT_ESTIMATION_BOX}),
        known_truths={_ECONOMIC_ACTIVITY: True},
    )

    assert form_casilla(form, _EARLIER_NEGATIVE_BASE_BOX).origin is ModeloFormOrigin.IMPORTED
    assert form_casilla(form, _DIRECT_ESTIMATION_BOX).origin is ModeloFormOrigin.ENTERED
    assert not {_EARLIER_NEGATIVE_BASE_BOX, _DIRECT_ESTIMATION_BOX} & _needs_you(form)


def test_the_answers_feed_the_attention_counts_of_the_form_and_its_outline(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "100", _YEAR, "0A", known_truths={_ECONOMIC_ACTIVITY: True})
    sections = {
        str(field.address.casilla_id): section.id
        for page in form.pages
        for section in page.sections
        for field in section_fields(section)
        if hasattr(field.address, "casilla_id")
    }

    assert form.counts.needs_input >= 2
    assert form.counts.needs_you >= 2
    for box in (_EARLIER_NEGATIVE_BASE_BOX, _DIRECT_ESTIMATION_BOX):
        group = next(item for item in form.outline if sections[box] in item.section_ids)
        assert group.counts.needs_you >= 1, box
        assert group.counts.needs_input >= 1, box


def test_a_declaration_recorded_as_filed_asks_nothing(operation: PinnedAuthorityOperation) -> None:
    form = built_form(
        operation,
        "100",
        _YEAR,
        "0A",
        lifecycle=CalculationRevisionState.PRESENTADO,
        known_truths={_ECONOMIC_ACTIVITY: True},
    )

    assert form.counts.needs_you == 0
    assert form.counts.needs_input == 0
    assert form_casilla(form, _EARLIER_NEGATIVE_BASE_BOX).standing is ModeloFormStanding.DONE
