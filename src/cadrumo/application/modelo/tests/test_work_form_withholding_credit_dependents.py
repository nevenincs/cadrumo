"""The work form serves, for each withholding credit, the numbered boxes the calculation works out from it.

The forms are built by the real builder over the published Modelo 100 registry
of the newest edition it authors. The cases a published edition does not hold
are made by re-pointing its own formulas: a total that reads a credit only
through a working figure the form prints no number for, a credit no formula
reads, and a formula the revision declares but does not carry.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.runtime_graph import expression_casilla_refs
from ....domain.calculations.registry.schema import FormulaDefinition, RegistrySnapshot
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormCasillaAddressV1, ModeloFormCredit, ModeloWorkForm
from ..workbench_projection import project_modelo_workbench_form
from .work_form_fixture import built_form, form_snapshot, read_before_calculation, uncalculated_review

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "100"
_PERIOD = "0A"


def _year() -> int:
    return newest_authored_edition(_MODELO)


def _casilla_ids(addresses: tuple[ModeloFormCasillaAddressV1, ...] | None) -> list[str]:
    assert addresses is not None
    return [str(address.casilla_id) for address in addresses]


def _credit_ids(form: ModeloWorkForm) -> list[str]:
    return [
        str(credit.address.casilla_id)
        for credit in form.withholding_credits
        if isinstance(credit.address, ModeloFormCasillaAddressV1)
    ]


def _credit(form: ModeloWorkForm, casilla_id: str) -> ModeloFormCredit:
    return next(
        credit
        for credit in form.withholding_credits
        if isinstance(credit.address, ModeloFormCasillaAddressV1) and str(credit.address.casilla_id) == casilla_id
    )


def _direct_readers(snapshot: RegistrySnapshot, casilla_id: str) -> list[str]:
    formulas = {formula.id: formula for formula in snapshot.revision.formulas}
    return [
        str(casilla.id)
        for casilla in snapshot.revision.casillas
        if casilla.formula is not None and casilla_id in expression_casilla_refs(formulas[casilla.formula].expression)
    ]


def _repointed(expression: FormulaExpression, source: str, target: FormulaExpression) -> FormulaExpression:
    """``expression`` with every leaf reading casilla ``source`` replaced by ``target``."""
    if expression.casilla_id == source:
        return target
    if not expression.args:
        return expression
    return expression.model_copy(update={"args": tuple(_repointed(arg, source, target) for arg in expression.args)})


def _adapted_form(
    operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot, *, formulas: tuple[FormulaDefinition, ...]
) -> ModeloWorkForm:
    adapted = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"formulas": formulas})})
    year = _year()
    return build_modelo_work_form(
        review=uncalculated_review(
            adapted, operation, modelo=_MODELO, filing_year=year, period=Period.from_year_and_code(year, _PERIOD)
        ),
        snapshot=adapted,
        layout=operation.form_layout(_MODELO, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def _numbered(form: ModeloWorkForm) -> dict[str, str]:
    return {
        str(field.address.casilla_id): field.box
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and field.box is not None
    }


def test_a_credit_a_total_reads_directly_lists_that_total_and_the_settlement(
    operation: PinnedAuthorityOperation,
) -> None:
    year = _year()
    form = built_form(operation, _MODELO, year, _PERIOD)
    snapshot = form_snapshot(operation, _MODELO, year, _PERIOD)
    numbered = _numbered(form)
    assert form.result is not None
    settlement = str(form.result.casilla_id)

    assert form.withholding_credits
    for credit_id in _credit_ids(form):
        dependents = _casilla_ids(_credit(form, credit_id).dependents)
        readers = [reader for reader in _direct_readers(snapshot, credit_id) if reader in numbered]
        assert readers
        assert set(readers) <= set(dependents)
        assert settlement in dependents
        assert set(dependents) <= set(numbered)
        assert not set(dependents) & set(_credit_ids(form))
        order = list(numbered)
        assert dependents == sorted(dependents, key=order.index)


def test_the_public_read_serves_the_credits_as_the_form_holds_them(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, _MODELO, _year(), _PERIOD)

    projection = project_modelo_workbench_form(
        UUID("13000000-0000-4000-8000-000000000455"), form.work_unit_id, read_before_calculation(form, operation)
    )

    assert projection.form.form.withholding_credits == form.withholding_credits
    assert projection.form.form.withholding_credits_heading == form.withholding_credits_heading
    assert form.withholding_credits_heading is not None


def test_a_credit_read_only_through_a_working_figure_still_lists_the_total_reading_that_figure(
    operation: PinnedAuthorityOperation,
) -> None:
    year = _year()
    form = built_form(operation, _MODELO, year, _PERIOD)
    snapshot = form_snapshot(operation, _MODELO, year, _PERIOD)
    numbered = _numbered(form)
    credit_id = _credit_ids(form)[0]
    total_id = next(reader for reader in _direct_readers(snapshot, credit_id) if reader in numbered)
    read = {
        str(operand)
        for formula in snapshot.revision.formulas
        for operand in expression_casilla_refs(formula.expression)
    }
    figure = next(
        casilla
        for casilla in snapshot.revision.casillas
        if casilla.formula is not None and str(casilla.id) not in numbered and str(casilla.id) not in read
    )
    figure_leaf = FormulaExpression(casilla_id=figure.id)
    credit_leaf = FormulaExpression(casilla_id=credit_id)
    total_formula = next(casilla.formula for casilla in snapshot.revision.casillas if str(casilla.id) == total_id)
    formulas = tuple(
        formula.model_copy(update={"expression": _repointed(formula.expression, credit_id, figure_leaf)})
        if formula.id == total_formula
        else formula.model_copy(update={"expression": credit_leaf})
        if formula.id == figure.formula
        else formula
        for formula in snapshot.revision.formulas
    )

    adapted = _adapted_form(operation, snapshot, formulas=formulas)

    assert total_id not in _direct_readers(
        snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"formulas": formulas})}),
        credit_id,
    )
    dependents = _casilla_ids(_credit(adapted, credit_id).dependents)
    assert total_id in dependents
    assert str(figure.id) not in dependents
    assert _casilla_ids(_credit(adapted, credit_id).dependents) == _casilla_ids(_credit(form, credit_id).dependents)


def test_a_credit_no_formula_reads_lists_no_box_while_the_others_keep_theirs(
    operation: PinnedAuthorityOperation,
) -> None:
    year = _year()
    form = built_form(operation, _MODELO, year, _PERIOD)
    snapshot = form_snapshot(operation, _MODELO, year, _PERIOD)
    unread, *others = _credit_ids(form)
    zero = FormulaExpression(literal=Decimal(0))
    formulas = tuple(
        formula.model_copy(update={"expression": _repointed(formula.expression, unread, zero)})
        for formula in snapshot.revision.formulas
    )

    adapted = _adapted_form(operation, snapshot, formulas=formulas)

    assert _credit(adapted, unread).dependents == ()
    for other in others:
        assert _casilla_ids(_credit(adapted, other).dependents) == _casilla_ids(_credit(form, other).dependents)


def test_a_formula_the_revision_does_not_carry_leaves_every_credit_unknown_not_empty(
    operation: PinnedAuthorityOperation,
) -> None:
    year = _year()
    form = built_form(operation, _MODELO, year, _PERIOD)
    snapshot = form_snapshot(operation, _MODELO, year, _PERIOD)
    assert form.result is not None
    settled = form.result.casilla_id
    settlement = next(casilla.formula for casilla in snapshot.revision.casillas if casilla.id == settled)
    formulas = tuple(formula for formula in snapshot.revision.formulas if formula.id != settlement)

    adapted = _adapted_form(operation, snapshot, formulas=formulas)

    assert _credit_ids(adapted) == _credit_ids(form)
    assert all(credit.dependents is None for credit in adapted.withholding_credits)
