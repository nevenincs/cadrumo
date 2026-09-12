"""Focused contracts for the authored terminal-origin expectation."""

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp, CalculationSourceLineageRole
from ..binding_terminal_origin import TerminalOriginClass, TerminalOriginExpectation
from ..relation_prefill_bindings import RelationPrefillProvider
from ..schema import BindingDefinition
from ..withholding_bindings import WithholdingProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_expectation_hydrates_a_filed_casilla_primary_origin() -> None:
    expectation = TerminalOriginExpectation.model_validate(
        {
            "source_class": "filed_modelo_casilla",
            "role": "primary",
            "cardinality": "exactly_one",
            "fingerprint": "required",
        },
    )

    assert expectation.source_class is TerminalOriginClass.FILED_MODELO_CASILLA
    assert expectation.role is CalculationSourceLineageRole.PRIMARY
    assert expectation.cardinality == "exactly_one"
    assert expectation.fingerprint == "required"


def test_expectation_round_trips_through_its_json_form() -> None:
    expectation = TerminalOriginExpectation(
        source_class=TerminalOriginClass.DETAIL_RECORD,
        role=CalculationSourceLineageRole.CONTRIBUTOR,
        cardinality="zero_or_more",
        fingerprint="optional",
    )

    assert TerminalOriginExpectation.model_validate(expectation.model_dump(mode="json")) == expectation


@pytest.mark.parametrize("source_class", list(TerminalOriginClass))
def test_every_origin_class_is_declarable(source_class: TerminalOriginClass) -> None:
    expectation = TerminalOriginExpectation(
        source_class=source_class,
        role=CalculationSourceLineageRole.PRIMARY,
        cardinality="at_least_one",
        fingerprint="optional",
    )

    assert expectation.source_class is source_class


def test_expectation_refuses_an_origin_class_outside_the_closed_set() -> None:
    with pytest.raises(ValidationError):
        TerminalOriginExpectation.model_validate(
            {
                "source_class": "sheets_pull",
                "role": "primary",
                "cardinality": "exactly_one",
                "fingerprint": "required",
            },
        )


def test_expectation_refuses_an_unknown_cardinality() -> None:
    with pytest.raises(ValidationError):
        TerminalOriginExpectation.model_validate(
            {
                "source_class": "ledger_aggregate",
                "role": "primary",
                "cardinality": "maybe_one",
                "fingerprint": "required",
            },
        )


def test_expectation_refuses_an_unknown_fingerprint_disposition() -> None:
    with pytest.raises(ValidationError):
        TerminalOriginExpectation.model_validate(
            {
                "source_class": "ledger_aggregate",
                "role": "contributor",
                "cardinality": "exactly_one",
                "fingerprint": "sometimes",
            },
        )


def _row_binding(cardinality: str) -> BindingDefinition:
    """Build a grouped row-family binding resting on one terminal origin."""
    return BindingDefinition(
        id="test.row-binding",
        provider=WithholdingProvider(
            fact="row_field",
            row_field="perceptor_tax_id",
            grouping="per_perceptor_clave",
            record="perceptor",
            data_type="text",
        ),
        value={"data_type": "text", "channel": "row_set", "row_grouping": "withholding"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        terminal_origins=(
            TerminalOriginExpectation(
                source_class=TerminalOriginClass.PERCEPTOR_OBSERVATION,
                role="primary",
                cardinality=cardinality,
                fingerprint="optional",
            ),
        ),
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-modelo-190-procedure",),
    )


def test_a_row_set_binding_refuses_an_exactly_one_terminal_origin() -> None:
    """A row family rests on however many facts the period produced, including none.

    ``exactly_one`` would make an empty row family indistinguishable from a
    missing one, collapsing the very distinction the cardinality axis carries.
    """
    with pytest.raises(ValidationError, match="cannot rest on an exactly_one terminal origin"):
        _row_binding("exactly_one")


@pytest.mark.parametrize("cardinality", ["at_least_one", "zero_or_more"])
def test_a_row_set_binding_admits_the_open_cardinalities(cardinality: str) -> None:
    """Both open cardinalities are honest statements about a row family."""
    binding = _row_binding(cardinality)

    assert binding.terminal_origins[0].cardinality == cardinality


def test_a_scalar_binding_still_admits_exactly_one() -> None:
    """The refusal is scoped to the row_set channel, not imposed on scalar values."""
    binding = BindingDefinition(
        id="test.scalar-binding",
        provider=RelationPrefillProvider(source_modelo="303", source_casilla_id="iva.cuota-devengada"),
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        terminal_origins=(
            TerminalOriginExpectation(
                source_class=TerminalOriginClass.FILED_MODELO_CASILLA,
                role="primary",
                cardinality="exactly_one",
                fingerprint="optional",
            ),
        ),
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("aeat-modelo-303-diseno-registro",),
    )

    assert binding.terminal_origins[0].cardinality == "exactly_one"
