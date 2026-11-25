"""Modelo 130 amendment refusal, stated-binding and legacy-correction channels against the published registry."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.identifiers import canonical_decimal_string
from ....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentIdentity
from ....domain.modelos.filing_record import FilingDeclarationKind
from ..calculation_helpers import amendment_prior_paid_values, calculate_amendment
from .test_amendment_calculation import _box, _source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _snapshot(operation: PinnedAuthorityOperation, period: str) -> RegistrySnapshot:
    return operation.snapshot("130", filing_year=filing_year_envelope().horizon, period=period)


def test_an_override_contradicting_a_confirmed_prior_payment_is_refused(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _snapshot(operation, "1T")
    source = _source(snapshot)
    prior_paid = amendment_prior_paid_values(
        baseline_revision=source,
        snapshot=snapshot,
        amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )
    assert prior_paid
    key, paid = next(iter(prior_paid.items()))
    with pytest.raises(ValueError, match="conflicts with confirmed prior-paid value"):
        calculate_amendment(
            source_revision=source,
            overrides={key: paid + Decimal("1")},
            prior_paid_values=prior_paid,
            snapshot=snapshot,
        )
    agreeing = calculate_amendment(
        source_revision=source,
        overrides={key: paid},
        prior_paid_values=prior_paid,
        snapshot=snapshot,
    )
    assert agreeing.casilla_values[key] == paid


def test_a_stated_binding_is_saved_and_recalculates_its_dependants(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _snapshot(operation, "1T")
    source = _source(snapshot)
    corrected = calculate_amendment(
        source_revision=source,
        overrides={},
        prior_paid_values={},
        snapshot=snapshot,
        binding_overrides={"modelo-130-estimacion-directa-modalidad": "directa_normal"},
    )
    assert corrected.binding_overrides["modelo-130-estimacion-directa-modalidad"] == "directa_normal"
    assert source.binding_overrides["modelo-130-estimacion-directa-modalidad"] == "directa_simplificada"
    # Directa normal carries no difícil-justificación provision, so casilla 02 falls back
    # to the deductible expenses alone, where the simplified source added the provision.
    assert source.casilla_values[_box("02")] > Decimal("4982")
    assert corrected.casilla_values[_box("02")] == Decimal("4982")


@pytest.mark.parametrize("imported", [False, True], ids=["calculated", "imported-scalar-replay"])
def test_a_stated_binding_reaches_its_bound_casilla_over_the_saved_figure(
    operation: PinnedAuthorityOperation,
    imported: bool,
) -> None:
    snapshot = _snapshot(operation, "1T")
    source = _source(snapshot, imported=imported)
    assert source.casilla_values[_box("gastos-deducibles-previos")] == Decimal("4982")
    corrected = calculate_amendment(
        source_revision=source,
        overrides={},
        prior_paid_values={},
        snapshot=snapshot,
        binding_overrides={
            "modelo-130-estimacion-directa-modalidad": "directa_normal",
            "modelo-130-actividad-economica-gastos-cumulative": "3982",
        },
    )
    # The stated expenses replace the saved 4982 in their bound casilla; directa normal adds
    # no provision, so box 02 is 3982, box 03 is 8840 - 3982 with no art. 32.1 reduction,
    # and box 04 is 20 per cent of box 03.
    assert corrected.casilla_values[_box("gastos-deducibles-previos")] == Decimal("3982")
    assert corrected.casilla_values[_box("02")] == Decimal("3982")
    assert corrected.casilla_values[_box("03")] == Decimal("4858")
    assert corrected.casilla_values[_box("04")] == Decimal("971.60")
    assert corrected.binding_overrides["modelo-130-actividad-economica-gastos-cumulative"] == "3982"


@pytest.mark.parametrize("shift", [Decimal("7"), Decimal("0")], ids=["changed", "unchanged"])
def test_a_legacy_amendment_without_operator_layer_recovers_changed_formula_values_as_authored(
    operation: PinnedAuthorityOperation,
    shift: Decimal,
) -> None:
    snapshot = _snapshot(operation, "1T")
    imported = _source(snapshot, imported=True)
    observations = tuple(
        observation.model_copy(update={"value": observation.value + shift})
        if observation.casilla_id == "07" and isinstance(observation.value, Decimal)
        else observation
        for observation in imported.observations
    )
    legacy = imported.model_copy(
        update={
            "amendment_identity": CalculationRevisionAmendmentIdentity(
                kind=FilingDeclarationKind.COMPLEMENTARIA,
                amends_filing_record_id="b" * 64,
                m303_rectificativa_motive=None,
            ),
            "observations": observations,
        }
    )
    corrected = calculate_amendment(
        source_revision=legacy,
        overrides={_box("01"): Decimal("9000")},
        prior_paid_values={},
        snapshot=snapshot,
    )
    assert corrected.operator_layer is not None
    authored = dict(corrected.operator_layer.decimal_casilla_inputs)
    expected = {_box("01"): "9000"}
    if shift:
        expected[_box("07")] = canonical_decimal_string(imported.casilla_values[_box("07")] + shift)
        assert corrected.casilla_values[_box("07")] == imported.casilla_values[_box("07")] + shift
    assert authored == expected
