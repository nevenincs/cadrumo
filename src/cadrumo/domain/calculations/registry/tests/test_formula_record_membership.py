"""A missing row is not zero; a source-proven unused row can bypass its amounts."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingSourceKind
from ...record_row_membership import ClosedRecordRowSet, RecordRowMembership
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot, evaluate_expression
from ..formula_runtime_ops import UnresolvedFormulaDependencyError
from ..schema_formula import FormulaExpression
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_COUNTRY = "modelo-369-exterior-fichero.3-prestaciones-de-servicios-codigo-de-pais-em-de-consumo-1"
_QUOTA = "modelo-369-exterior-fichero.3-prestaciones-de-servicios-cuota-iva-1"


def _unused(binding: str = _COUNTRY) -> FormulaExpression:
    return FormulaExpression(op="record_row_unused", args=(FormulaExpression(binding=binding),))


def _evaluate(expression: FormulaExpression, *, occupancy=None, amounts=None, texts=None, dates=None, booleans=None):
    return evaluate_expression(
        expression,
        values={},
        binding_values=amounts or {},
        enum_binding_values=texts or {},
        date_binding_values=dates or {},
        boolean_binding_values=booleans or {},
        record_row_occupancy=occupancy,
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
    )


def test_unknown_empty_occupied_and_zero_have_distinct_membership() -> None:
    with pytest.raises(UnresolvedFormulaDependencyError):
        _evaluate(_unused())
    with pytest.raises(UnresolvedFormulaDependencyError):
        _evaluate(_unused(), texts={_COUNTRY: ""})
    assert _evaluate(_unused(), occupancy={_COUNTRY: False}) == 1
    assert _evaluate(_unused(), occupancy={_COUNTRY: True}) == 0
    assert _evaluate(_unused(), texts={_COUNTRY: "DE"}) == 0
    assert _evaluate(_unused(_QUOTA), amounts={_QUOTA: Decimal(0)}) == 0
    assert _evaluate(_unused(), booleans={_COUNTRY: False}) == 0
    assert _evaluate(_unused(), dates={_COUNTRY: date(2025, 9, 30)}) == 0


@pytest.mark.parametrize("channel", ["amounts", "texts", "dates", "booleans"])
def test_unused_row_refuses_a_supplied_value_in_every_channel(channel):
    values = {
        "amounts": Decimal(0),
        "texts": "DE",
        "dates": date(2025, 9, 30),
        "booleans": False,
    }
    with pytest.raises(RegistryValidationError, match="unused record row"):
        _evaluate(_unused(), occupancy={_COUNTRY: False}, **{channel: {_COUNTRY: values[channel]}})


def test_only_proven_unused_rows_bypass_missing_required_amounts() -> None:
    expression = FormulaExpression(
        op="if_then_else",
        args=(_unused(), FormulaExpression(literal=Decimal(0)), FormulaExpression(binding=_QUOTA)),
    )
    assert _evaluate(expression, occupancy={_COUNTRY: False}) == 0
    assert _evaluate(expression, occupancy={_COUNTRY: True}, amounts={_QUOTA: Decimal("190")}) == 190
    with pytest.raises(RegistryValidationError):
        _evaluate(expression, occupancy={_COUNTRY: True})
    with pytest.raises(UnresolvedFormulaDependencyError):
        _evaluate(expression)
    with pytest.raises(RegistryValidationError, match="unused record row"):
        _evaluate(expression, occupancy={_COUNTRY: False}, texts={_COUNTRY: "DE"})


@pytest.mark.parametrize(
    "args",
    [
        (),
        (FormulaExpression(literal=Decimal(0)),),
        (FormulaExpression(casilla_id="01"),),
        (_unused(),),
        (_unused(), _unused()),
    ],
)
def test_row_predicate_requires_one_binding_leaf(args) -> None:
    with pytest.raises((ValidationError, RegistryValidationError)):
        FormulaExpression(op="record_row_unused", args=args)


@pytest.mark.parametrize("occupied", [False, True])
def test_snapshot_runtime_consumes_closed_source_evidence(occupied: bool) -> None:
    snapshot = published_snapshot("369", filing_year=2025, period="EXT-3T")
    formula = snapshot.revision.formulas[0].model_copy(
        update={
            "expression": FormulaExpression(
                op="if_then_else",
                args=(_unused(), FormulaExpression(literal=Decimal(0)), FormulaExpression(binding=_QUOTA)),
            )
        }
    )
    snapshot = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"formulas": (formula,)})})
    evidence = ClosedRecordRowSet(
        record_id="modelo-369-exterior-t36901",
        bucket_id="fictional-profile",
        work_unit_id="a" * 64,
        registry_snapshot_ref=snapshot.snapshot_ref,
        authority_generation="b" * 64,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        source_ref="fictional-source",
        source_fingerprint="c" * 64,
        rows=(RecordRowMembership(row_index=1, binding_ids=(_COUNTRY, _QUOTA), occupied=occupied),),
    )
    values = {_QUOTA: Decimal("190")} if occupied else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={},
        binding_values=values,
        closed_record_row_sets=(evidence,),
    )
    assert result.values[formula.target_casilla_id] == (Decimal("190") if occupied else Decimal(0))
    unknown = calculate_registry_snapshot(snapshot, inputs={}, date_context={}, binding_values={})
    assert formula.target_casilla_id not in unknown.values

    other_period = evidence.model_copy(
        update={"registry_snapshot_ref": evidence.registry_snapshot_ref.model_copy(update={"period": "EXT-2T"})}
    )
    with pytest.raises(RegistryValidationError, match="different registry snapshot"):
        calculate_registry_snapshot(snapshot, inputs={}, date_context={}, closed_record_row_sets=(other_period,))
    wrong_record = evidence.model_copy(update={"record_id": "corrections"})
    with pytest.raises(RegistryValidationError, match="declared fixed record slot"):
        calculate_registry_snapshot(snapshot, inputs={}, date_context={}, closed_record_row_sets=(wrong_record,))
