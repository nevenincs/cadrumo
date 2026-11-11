"""The form asks for the answers a calculation refuses to run without, instead of presenting them as optional.

Every expectation about what the engine refuses without is read from the engine
itself: the 2025 Modelo 100 is calculated over the published registry with one
answer left out, and the refusal names the binding. The form is then built by
the real builder, and must ask for exactly the boxes those refusals belong to --
the earlier year's negative base (1388) always. The normal direct
estimation answer (0168) is derived from the profile's estimation regime, so the
form never asks for it although the engine still refuses a calculation without it.
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
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.modelo_100_registry_support import neutral_binding_values
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ..calculation_required_inputs import calculation_required_inputs
from ..work_form_field_vocabulary import (
    ModeloFormOrigin,
    ModeloFormStanding,
)
from ..work_form_models import (
    ModeloWorkForm,
    section_fields,
)
from .work_form_fixture import built_form, form_casilla, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_SALARY: CasillaId = validated_casilla_id("0003", surface="_SALARY")
_EARLIER_NEGATIVE_BASE_BOX = "1388"
_EARLIER_NEGATIVE_BASE: BindingId = "renta-base-liquidable-negativa-general-anterior"
#: The pending stocks of the three older origin years, each carried from its own box of the prior return.
_OLDER_NEGATIVE_BASES: dict[str, BindingId] = {
    "1380": "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
    "1382": "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "1385": "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
}
_NEGATIVE_BASE_BOXES = frozenset({_EARLIER_NEGATIVE_BASE_BOX, *_OLDER_NEGATIVE_BASES})
_DIRECT_ESTIMATION_BOX = "0168"
_DIRECT_ESTIMATION: BindingId = "renta-modelo-100-estimacion-directa-es-normal"
_ECONOMIC_ACTIVITY: BindingId = "renta-profile-has-economic-activity"
_DIRECT_REGIME: BindingId = "renta-profile-estimacion-directa"


def _calculation_snapshot(operation: PinnedAuthorityOperation, year: int = _YEAR) -> RegistrySnapshot:
    return operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate_without(
    snapshot: RegistrySnapshot, *, activity: bool, omitted: BindingId | None, year: int = _YEAR, directa: bool = True
) -> None:
    """Run the engine over every binding's neutral answer, leaving ``omitted`` unanswered."""
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    booleans[_ECONOMIC_ACTIVITY] = activity
    booleans[_DIRECT_ESTIMATION] = True
    booleans[_DIRECT_REGIME] = directa
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
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


def _refused_binding(snapshot: RegistrySnapshot, *, activity: bool, omitted: BindingId, year: int = _YEAR) -> str:
    with pytest.raises(RegistryValidationError) as refused:
        _calculate_without(snapshot, activity=activity, omitted=omitted, year=year)
    assert refused.value.translated_message in {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
    }
    return str((refused.value.context or {}).get("binding_id"))


# -- what the engine refuses without -------------------------------------------


def test_the_engine_runs_when_every_answer_is_given(operation: PinnedAuthorityOperation) -> None:
    _calculate_without(_calculation_snapshot(operation), activity=True, omitted=None)


def test_the_engine_refuses_without_any_earlier_negative_base_whoever_the_filer_is(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _calculation_snapshot(operation)

    for binding_id in (_EARLIER_NEGATIVE_BASE, *_OLDER_NEGATIVE_BASES.values()):
        for activity in (True, False):
            assert _refused_binding(snapshot, activity=activity, omitted=binding_id) == binding_id


def test_the_engine_refuses_without_the_direct_estimation_answer_only_for_a_filer_with_an_activity(
    operation: PinnedAuthorityOperation,
) -> None:
    """An employee or an objetiva filer calculates without the modality and a direct filer still needs it, in every supported year."""
    support = published_supported_filing_years()
    assert support is not None
    checked = 0
    for year in sorted(support.years):
        try:
            snapshot = _calculation_snapshot(operation, year)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        assert _refused_binding(snapshot, activity=True, omitted=_DIRECT_ESTIMATION, year=year) == _DIRECT_ESTIMATION
        _calculate_without(snapshot, activity=False, omitted=_DIRECT_ESTIMATION, year=year)
        # An estimacion objetiva filer has an activity but no direct-estimation block, so no modality is read.
        _calculate_without(snapshot, activity=True, omitted=_DIRECT_ESTIMATION, year=year, directa=False)
        checked += 1
    assert checked


# -- what the registry says the form must ask for -------------------------------


def test_the_inputs_named_are_the_ones_the_engine_refused_without(operation: PinnedAuthorityOperation) -> None:
    revision = _calculation_snapshot(operation).revision

    def named(truths: dict[str, bool] | None) -> set[str]:
        return {
            str(item)
            for item in calculation_required_inputs(revision, registry_period="0A", known_truths=truths).casilla_ids
        }

    assert named(None) == _NEGATIVE_BASE_BOXES
    assert named({_ECONOMIC_ACTIVITY: False}) == _NEGATIVE_BASE_BOXES
    assert named({_ECONOMIC_ACTIVITY: True}) == _NEGATIVE_BASE_BOXES


def test_a_carry_between_periods_of_one_year_is_not_named(operation: PinnedAuthorityOperation) -> None:
    """Modelo 130's earlier instalments are produced by this campaign's own declarations; the form waits for them."""
    revision = form_snapshot(operation, "130", _YEAR, "2T").revision

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

    for box in sorted(_NEGATIVE_BASE_BOXES):
        field = form_casilla(form, box)
        assert field.origin is ModeloFormOrigin.NEEDS_INPUT, box
        assert field.standing is ModeloFormStanding.NEEDS_YOU, box
        # Verification's own set is unchanged: the form asks for what the calculation needs, not more of the check.
        assert not field.required, box
    assert _needs_you(form) >= _NEGATIVE_BASE_BOXES


def test_the_direct_estimation_answer_is_never_asked_because_the_profile_derives_it(
    operation: PinnedAuthorityOperation,
) -> None:
    for truths in (None, {_ECONOMIC_ACTIVITY: False}, {_ECONOMIC_ACTIVITY: True}):
        field = form_casilla(built_form(operation, "100", _YEAR, "0A", known_truths=truths), _DIRECT_ESTIMATION_BOX)

        assert field.origin is not ModeloFormOrigin.NEEDS_INPUT, truths
        assert field.standing is not ModeloFormStanding.NEEDS_YOU, truths


def test_a_held_answer_is_confirmed_not_asked_again(operation: PinnedAuthorityOperation) -> None:
    form = built_form(
        operation,
        "100",
        _YEAR,
        "0A",
        held=dict.fromkeys(_NEGATIVE_BASE_BOXES, Decimal("0")),
        known_truths={_ECONOMIC_ACTIVITY: True},
    )

    for box in _NEGATIVE_BASE_BOXES:
        assert form_casilla(form, box).origin is ModeloFormOrigin.IMPORTED, box
    assert not _NEGATIVE_BASE_BOXES & _needs_you(form)


def test_the_answers_feed_the_attention_counts_of_the_form_and_its_outline(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "100", _YEAR, "0A", known_truths={_ECONOMIC_ACTIVITY: True})
    sections = {
        str(field.address.casilla_id): section.id
        for page in form.pages
        for section in page.sections
        for field in section_fields(section)
        if hasattr(field.address, "casilla_id")
    }

    assert form.counts.needs_input >= 1
    assert form.counts.needs_you >= 1
    for box in (_EARLIER_NEGATIVE_BASE_BOX,):
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
