"""Formula explanations disclose the stored operands and result without calculating again."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.calculations.registry.schema_surfaces import CasillaConstraints
from ..casilla_help import build_casilla_help_card
from ..value_presentation import VALUE_ABSENT_LOCALE_KEY

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ON = date(2026, 3, 31)


def _calculated(operation: PinnedAuthorityOperation, income: str, expenses: str):
    snapshot = operation.snapshot("130", filing_year=2026, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal(income),
            "02": Decimal(expenses),
            "06": Decimal(0),
            "08": Decimal(0),
            "10": Decimal(0),
            "16": Decimal(0),
            "18": Decimal(0),
        },
        binding_values={
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal(income) - Decimal(expenses),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal(0),
        },
        date_context={"filing_period": _ON},
    )
    return snapshot, {str(item.casilla_id): item for item in result.observations}


def _formula(
    operation: PinnedAuthorityOperation,
    snapshot: RegistrySnapshot,
    observation: CasillaObservation | None,
    casilla: str,
    language: OutputLanguage = OutputLanguage.EN,
):
    card = build_casilla_help_card(
        casilla,
        snapshot=snapshot,
        operation=operation,
        language=language,
        on=_ON,
        observation=observation,
    )
    assert card.formula is not None
    return card.formula


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (OutputLanguage.EN, "[01] 1,234.56\u00a0€ − [02] 234.56\u00a0€ = 1,000.00\u00a0€"),
        (OutputLanguage.ES, "[01] 1.234,56\u00a0€ − [02] 234,56\u00a0€ = 1.000,00\u00a0€"),
        (OutputLanguage.CA, "[01] 1.234,56\u00a0€ − [02] 234,56\u00a0€ = 1.000,00\u00a0€"),
        (OutputLanguage.HU, "[01] 1\u00a0234,56\u00a0€ − [02] 234,56\u00a0€ = 1\u00a0000,00\u00a0€"),
    ],
)
def test_the_official_subtraction_shows_its_recorded_values_in_every_language(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    expected: str,
) -> None:
    snapshot, observations = _calculated(operation, "1234.56", "234.56")

    formula = _formula(operation, snapshot, observations["03"], "03", language)

    assert formula.values_text == expected
    assert formula.text == "[03] = [01] − [02]"


def test_a_zero_instalment_shows_the_negative_income_and_the_zero_floor(operation: PinnedAuthorityOperation) -> None:
    snapshot, observations = _calculated(operation, "1000", "2000")

    formula = _formula(operation, snapshot, observations["04"], "04")

    assert formula.values_text == "max(0, 20 % of [03] −1,000.00\u00a0€) = 0.00\u00a0€"


def test_a_held_zero_and_an_absent_operand_never_share_a_spelling(operation: PinnedAuthorityOperation) -> None:
    snapshot, observations = _calculated(operation, "0", "0")
    held = _formula(operation, snapshot, observations["03"], "03")
    incomplete = observations["03"].model_copy(
        update={
            "operand_refs": ("01",),
            "operand_casilla_refs": ("01",),
            "operand_values": (Decimal(0),),
        }
    )
    missing = _formula(operation, snapshot, incomplete, "03")

    assert held.values_text == "[01] 0.00\u00a0€ − [02] 0.00\u00a0€ = 0.00\u00a0€"
    absent = lookup_translation(VALUE_ABSENT_LOCALE_KEY, locale="en")
    assert missing.values_text == f"[01] 0.00\u00a0€ − [02] {absent} = 0.00\u00a0€"


def test_no_calculation_or_a_different_formula_supplies_no_values(operation: PinnedAuthorityOperation) -> None:
    snapshot, observations = _calculated(operation, "1234.56", "234.56")

    assert _formula(operation, snapshot, None, "03").values_text is None
    assert _formula(operation, snapshot, observations["04"], "03").values_text is None
    assert (
        _formula(operation, snapshot, observations["03"].model_copy(update={"formula_id": None}), "03").values_text
        is None
    )


def test_an_unpaired_or_ambiguous_trace_never_assigns_a_value_to_the_wrong_operand(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot, observations = _calculated(operation, "1234.56", "234.56")
    unpaired = observations["03"].model_copy(update={"operand_values": (Decimal("1234.56"),)})
    ambiguous = observations["03"].model_copy(
        update={
            "operand_refs": ("01", "01"),
            "operand_casilla_refs": ("01", "01"),
            "operand_values": (Decimal(1), Decimal(2)),
        }
    )

    assert _formula(operation, snapshot, unpaired, "03").values_text is None
    assert _formula(operation, snapshot, ambiguous, "03").values_text is None


def test_the_explanation_preserves_operand_precision_and_the_saved_result(operation: PinnedAuthorityOperation) -> None:
    snapshot, observations = _calculated(operation, "1000.005", "500.001")
    # The formula rounds its result; presentation must not rerun arithmetic
    # over the displayed operands or round the operands themselves.
    formula = _formula(operation, snapshot, observations["03"], "03")

    assert formula.values_text == "[01] 1,000.005\u00a0€ − [02] 500.001\u00a0€ = 500.00\u00a0€"


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_a_conditional_deduction_shows_its_saved_income_without_exposing_binding_ids(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> None:
    snapshot, observations = _calculated(operation, "1000", "2000")

    formula = _formula(operation, snapshot, observations["13"], "13", language)

    assert formula.values_text is not None
    assert "€" in formula.values_text
    assert not any(key in formula.values_text for key in observations["13"].operand_refs if len(key) > 3)
    # The deduction table uses the preceding year's income of EUR 13,000.
    # Its saved input must remain visible even though no box carries it.
    assert "13" in formula.values_text
    assert formula.values_text.endswith("€")


def test_a_complex_rule_reports_its_trace_as_inputs_not_guessed_arithmetic(operation: PinnedAuthorityOperation) -> None:
    snapshot, observations = _calculated(operation, "1000", "500")
    # An isolated typed rule that the arithmetic renderer cannot spell out.
    # The trace remains separately worded rather than inventing an operator.
    formula = next(item for item in snapshot.revision.formulas if item.target_casilla_id == "03")
    rule = formula.model_copy(
        update={
            "expression": FormulaExpression(
                op="lookup_bracket",
                args=(FormulaExpression(casilla_id="01"), FormulaExpression(literal=Decimal(0))),
            )
        }
    )
    snapshot = snapshot.model_copy(
        update={
            "revision": snapshot.revision.model_copy(
                update={
                    "formulas": tuple(rule if item.id == formula.id else item for item in snapshot.revision.formulas),
                }
            )
        }
    )

    explanation = _formula(operation, snapshot, observations["03"], "03")

    assert explanation.values_text == "Values used: [01] 1,000.00\u00a0€ · [02] 500.00\u00a0€. Result: 500.00\u00a0€."


def test_a_declared_fraction_keeps_its_percentage_unit_in_a_formula(operation: PinnedAuthorityOperation) -> None:
    snapshot, observations = _calculated(operation, "0", "0")
    formula = next(item for item in snapshot.revision.formulas if item.target_casilla_id == "03")
    copy = formula.model_copy(
        update={"expression": FormulaExpression(op="copy", args=(FormulaExpression(casilla_id="01"),))}
    )
    casillas = tuple(
        item.model_copy(
            update={
                "data_type": CasillaDataType.RATIO,
                "constraints": CasillaConstraints(
                    max_value=Decimal(1), legal_refs=item.legal_refs, source_refs=item.source_refs
                ),
            }
        )
        if item.id in {"01", "03"}
        else item
        for item in snapshot.revision.casillas
    )
    snapshot = snapshot.model_copy(
        update={
            "revision": snapshot.revision.model_copy(
                update={
                    "casillas": casillas,
                    "formulas": tuple(copy if item.id == formula.id else item for item in snapshot.revision.formulas),
                }
            )
        }
    )
    observation = observations["03"].model_copy(
        update={
            "value": Decimal("0.21"),
            "operand_refs": ("01",),
            "operand_casilla_refs": ("01",),
            "operand_values": (Decimal("0.21"),),
        }
    )

    explanation = _formula(operation, snapshot, observation, "03")

    assert explanation.values_text == "[01] 21\u00a0% = 21\u00a0%"
