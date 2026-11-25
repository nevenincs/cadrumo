"""A listed Modelo 232 statement and its verdict carry served words in the operator's language."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.config import override_settings
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.m232_obligation import (
    Modelo232Basis,
    Modelo232Ground,
    Modelo232GroundFinding,
    Modelo232GroundState,
    Modelo232ObligationFinding,
)
from ....domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232StatementState,
)
from ..results import Modelo232NoneStatementProjection, Modelo232OperationProjection, Modelo232VerdictProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EJERCICIO = filing_year_envelope().horizon
_AT = datetime(_EJERCICIO, 3, 1, 9, 0, tzinfo=UTC)


def _operation() -> Modelo232Operation:
    return Modelo232Operation(
        operation_id="a" * 32,
        ejercicio=_EJERCICIO,
        operation_kind=Modelo232OperationKind.RELATED_PARTY,
        counterparty_tax_id="B99999991",
        counterparty_name="Synthetic Related Holding",
        counterparty_country="DE",
        tipo_vinculacion="D",
        tipo_operacion="06",
        valuation_method="1A",
        direction=Modelo232Direction.PAGO,
        amount_eur=Decimal("1000.00"),
        stated_at=_AT,
    )


@pytest.mark.parametrize(
    ("language", "state", "words"),
    [
        ("en", Modelo232StatementState.ACTIVE, "In force"),
        ("en", Modelo232StatementState.WITHDRAWN, "Withdrawn"),
        ("es", Modelo232StatementState.ACTIVE, "Vigente"),
        ("ca", Modelo232StatementState.WITHDRAWN, "Retirada"),
        ("hu", Modelo232StatementState.ACTIVE, "Hatályos"),
    ],
)
def test_each_state_is_served_in_the_operators_language(
    language: str, state: Modelo232StatementState, words: str
) -> None:
    statement = Modelo232NoneStatement(
        statement_id="b" * 32, ejercicio=_EJERCICIO, note="Sin vinculadas", stated_at=_AT
    )
    if state is Modelo232StatementState.WITHDRAWN:
        statement = statement.withdrawn(_AT)
    with override_settings(cadrumo_output_language=language):
        row = Modelo232NoneStatementProjection.from_statement(statement, revision_id="r1")
    assert row.state is state
    assert row.state_label == words


def test_a_projected_operation_never_carries_the_counterpartys_identifier() -> None:
    with override_settings(cadrumo_output_language="es"):
        row = Modelo232OperationProjection.from_operation(_operation(), revision_id="r1")
    assert "B99999991" not in row.model_dump_json()
    assert row.operation_kind_label == "Operación con persona o entidad vinculada"
    assert row.direction_label == "Pago (P)"
    assert row.amount_eur.decimal == "1000.00"


def test_the_verdict_words_its_outcome_and_each_ground() -> None:
    finding = Modelo232ObligationFinding(
        ejercicio=_EJERCICIO,
        basis=Modelo232Basis.OPERATIONS_STATED,
        grounds=(
            Modelo232GroundFinding(
                Modelo232Ground.SAME_RELATED_PARTY, Modelo232GroundState.MET, Decimal("300000"), Decimal("250000")
            ),
            Modelo232GroundFinding(Modelo232Ground.TURNOVER_SHARE, Modelo232GroundState.UNDECIDED, Decimal("300000")),
        ),
        counted_operations=1,
        excluded_operations=0,
        excluded_total_eur=Decimal(0),
        turnover_eur=None,
        turnover_source=None,
    )
    with override_settings(cadrumo_output_language="en"):
        verdict = Modelo232VerdictProjection.from_finding(finding)
    assert verdict.obligation_label == "Your records show that you must file Modelo 232."
    assert verdict.basis_label == "You stated operations for this year."
    met, undecided = verdict.grounds
    assert met.state_label == "Met"
    assert met.ground_label == "Operations with one related person or entity (art. 2.1.a)"
    assert met.limit_eur is not None
    assert met.limit_eur.decimal == "250000"
    assert undecided.state_label == "Undecided"
    assert undecided.limit_eur is None
