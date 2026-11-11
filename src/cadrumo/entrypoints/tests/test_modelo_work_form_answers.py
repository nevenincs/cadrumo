"""A first-quarter Modelo 130 can be given the earlier-filing answers its calculation needs, through its own form.

The quarter calculated without the previous year's activity income and the
earlier negative results cannot work out boxes 13 and 15, so box 19 stays
open. Its layout prints no field for either answer, so the form serves them
among its answers. Driven over real encrypted storage through the production
calculation and edit executors and read back through the form loading service:
the answers the form serves are submitted at the edit address each field
names, and after a recalculation boxes 13, 15 and 19 hold figures.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.entrypoints.tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAdmittedV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ...application.modelo.work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormStanding,
)
from ...application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOutlineKind,
    ModeloWorkForm,
)
from ...application.modelo.work_form_service import load_modelo_work_form
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ..adapter_composition import profile_adapter_composition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PREVIOUS_YEAR_INCOME = "irpf.previous_year_economic_activity_net_income"
_EARLIER_NEGATIVE_RESULTS = "modelo-130-resultados-negativos-anteriores"
#: What the filer answers, by the box whose field takes it: the earlier year's income above the 12,000 euro
#: ceiling of box 13's reduction, no earlier negative results, and no earlier payments for box 05.
_GIVEN = {_PREVIOUS_YEAR_INCOME: "13000", _EARLIER_NEGATIVE_RESULTS: "0"}
_EARLIER_PAYMENTS_BOX = "05"
_FACTS = RENTA_UNMARRIED_TAXPAYER_FACTS


@contextmanager
def _bare_quarter(tmp_path: Path) -> Generator[SeededOperatorWork]:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="130", filing_year=_YEAR, period_code="1T", extra_facts=_FACTS
        ) as quarter,
    ):
        quarter.recalculate()
        yield quarter


def _form(work: SeededOperatorWork) -> ModeloWorkForm:
    admission = work.admit()
    assert isinstance(admission, ModeloEditAdmittedV1)
    return load_modelo_work_form(
        work.work_unit.bucket_id,
        work.work_unit.modelo,
        work.work_unit.filing_year,
        work.work_unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=admission,
        language=OutputLanguage.EN,
    ).form


def _boxed(form: ModeloWorkForm, box: str) -> ModeloFormField:
    return next(field for field in form.fields() if field.box == box)


def _answer(form: ModeloWorkForm, binding_id: str) -> ModeloFormField:
    return next(field for field in form.answers if field.address == ModeloFormBindingAddressV1(binding_id=binding_id))


def _intent(field: ModeloFormField, value: str) -> ModeloBindingEditIntentV1:
    """The change a frontend submits for ``field``: at the edit address the form names, never one it guesses."""
    address = field.edit_address
    assert isinstance(address, ModeloFormBindingAddressV1)
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=address.binding_id),
        kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
        value=value,
    )


def test_the_quarter_serves_the_answers_its_open_boxes_need_as_editable_fields(tmp_path: Path) -> None:
    with _bare_quarter(tmp_path) as quarter:
        form = _form(quarter)

        assert {_boxed(form, box).origin for box in ("13", "15")} == {ModeloFormOrigin.CALCULATION_FAILED}
        assert "19" not in quarter.require_head().casilla_values
        assert [group.kind for group in form.outline].count(ModeloFormOutlineKind.ANSWERS) == 1
        for binding_id in _GIVEN:
            answer = _answer(form, binding_id)
            assert answer.editability in {
                ModeloFormEditability.EDITABLE_OVERRIDE,
                ModeloFormEditability.OVERRIDABLE_SOURCE,
            }
            assert answer.edit_address == answer.address
            assert answer.value is None
            assert answer.standing is ModeloFormStanding.NEEDS_YOU


def test_answering_through_the_form_lets_the_quarter_work_out_its_result(tmp_path: Path) -> None:
    with _bare_quarter(tmp_path) as quarter:
        form = _form(quarter)
        intents = (
            *(_intent(_answer(form, binding_id), value) for binding_id, value in _GIVEN.items()),
            _intent(_boxed(form, _EARLIER_PAYMENTS_BOX), "0"),
        )

        applied = quarter.apply(binding=intents)
        assert applied.refusal is None
        head = quarter.recalculate()

        assert head.casilla_values["13"] == Decimal("0")
        assert head.casilla_values["15"] == Decimal("0")
        assert "19" in head.casilla_values
        answered = _form(quarter)
        assert answered.counts.could_not_calculate == 0
        for binding_id, value in _GIVEN.items():
            answer = _answer(answered, binding_id)
            assert answer.origin is ModeloFormOrigin.ENTERED
            assert answer.value == Decimal(value)
        assert _boxed(answered, "19").value == head.casilla_values["19"]
