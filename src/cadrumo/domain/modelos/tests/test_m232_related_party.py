"""Validation of the Modelo 232 related-party statement payloads through the real models.

The coded fields are bounded by shape only here: which codes the record design
publishes is the write path's check, against the authority pinned for the
ejercicio. Names, identifiers and amounts are synthetic, and the years come from
the registry's support envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..m232_related_party import (
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232StatementState,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
    Modelo232YearGuard,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_AT = datetime(_YEAR, 4, 2, 9, 0, tzinfo=UTC)
_SYNTHETIC_ID = "X9999999Z"
_SYNTHETIC_NAME = "Synthetic Secret Name"

_RELATED: dict[str, object] = {
    "operation_id": "a" * 32,
    "ejercicio": _YEAR,
    "operation_kind": Modelo232OperationKind.RELATED_PARTY,
    "counterparty_tax_id": "de123456789",
    "counterparty_name": "  Synthetic Partner GmbH ",
    "counterparty_country": "DE",
    "tipo_vinculacion": "D",
    "tipo_operacion": "06",
    "valuation_method": "1A",
    "direction": Modelo232Direction.PAGO,
    "amount_eur": Decimal("250000.01"),
    "stated_at": _AT,
}
_INTANGIBLES: dict[str, object] = {
    **_RELATED,
    "operation_kind": Modelo232OperationKind.INTANGIBLES_REDUCTION,
    "tipo_operacion": None,
    "valuation_method": None,
    "direction": None,
}
_HAVEN_OPERATION: dict[str, object] = {
    **_RELATED,
    "operation_kind": Modelo232OperationKind.TAX_HAVEN_OPERATION,
    "counterparty_tax_id": None,
    "tipo_vinculacion": None,
    "tipo_operacion": None,
    "valuation_method": None,
    "direction": None,
    "counterparty_country": "KY",
}


def _operation(base: dict[str, object], **overrides: object) -> Modelo232Operation:
    return Modelo232Operation.model_validate({**base, **overrides})


def test_an_operation_keeps_its_stated_fields_with_the_identifier_normalised() -> None:
    operation = _operation(_RELATED, specific_operation=True, exclusion=Modelo232Exclusion.PUBLIC_OFFER)
    assert operation.counterparty_tax_id == "DE123456789"
    assert operation.counterparty_name == "Synthetic Partner GmbH"
    assert operation.counterparty_country == "DE"
    assert operation.excluded
    assert operation.active
    assert operation.identity == (_YEAR, "a" * 32)
    assert Modelo232Operation.model_validate_json(operation.model_dump_json()) == operation


def test_the_three_kinds_that_carry_fewer_fields_are_accepted_as_designed() -> None:
    assert _operation(_INTANGIBLES).tipo_operacion is None
    assert _operation(_HAVEN_OPERATION).counterparty_tax_id is None
    assert _operation(_HAVEN_OPERATION, operation_kind=Modelo232OperationKind.TAX_HAVEN_HOLDING).amount_eur > 0


def test_a_code_the_design_does_not_publish_is_still_a_readable_row() -> None:
    """Which codes exist is the write path's check, so a stored row never fails a read over a catalogue."""
    operation = _operation(_RELATED, tipo_vinculacion="Z", tipo_operacion="99", valuation_method="9Z")
    assert Modelo232Operation.model_validate_json(operation.model_dump_json()) == operation
    assert operation.withdrawn(_AT + timedelta(days=1)).tipo_operacion == "99"


def test_the_optional_design_fields_are_accepted_only_where_the_design_asks_them() -> None:
    assert _operation(_INTANGIBLES, parent_tax_id="de999", parent_name="Synthetic Parent").parent_tax_id == "DE999"
    assert _operation(_HAVEN_OPERATION, description="Synthetic services").description == "Synthetic services"
    holding = _operation(
        _HAVEN_OPERATION, operation_kind=Modelo232OperationKind.TAX_HAVEN_HOLDING, participation_percent=Decimal("25.5")
    )
    assert holding.participation_percent == Decimal("25.5")
    for base, overrides in (
        (_RELATED, {"description": "Synthetic"}),
        (_RELATED, {"participation_percent": Decimal("1")}),
        (_RELATED, {"parent_tax_id": "B1", "parent_name": "N"}),
        (_INTANGIBLES, {"parent_tax_id": "B1"}),
        (_INTANGIBLES, {"parent_name": "N"}),
        (_HAVEN_OPERATION, {"description": "D" * 51}),
        (_HAVEN_OPERATION, {"operation_kind": Modelo232OperationKind.TAX_HAVEN_HOLDING, "description": "D"}),
        (
            _HAVEN_OPERATION,
            {"operation_kind": Modelo232OperationKind.TAX_HAVEN_HOLDING, "participation_percent": Decimal("100.01")},
        ),
        (_HAVEN_OPERATION, {"participation_percent": Decimal("1")}),
    ):
        with pytest.raises(ValidationError):
            _operation(base, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"tipo_vinculacion": "d"},
        {"tipo_operacion": "6"},
        {"valuation_method": "1a"},
        {"valuation_method": "1"},
        {"direction": None},
        {"direction": "X"},
        {"amount_eur": Decimal("-0.01")},
        {"amount_eur": Decimal("10.001")},
        {"counterparty_name": "   "},
        {"counterparty_name": ""},
        {"counterparty_name": "N" * 61},
        {"counterparty_tax_id": ""},
        {"counterparty_tax_id": "1" * 16},
        {"counterparty_tax_id": None},
        {"tipo_vinculacion": None},
        {"tipo_operacion": None},
        {"valuation_method": None},
        {"counterparty_country": "de"},
        {"counterparty_country": "D"},
        {"operation_id": "not-an-id"},
        {"ejercicio": 99},
        {"state": Modelo232StatementState.WITHDRAWN},
        {"withdrawn_at": _AT + timedelta(days=1)},
        {"state": Modelo232StatementState.WITHDRAWN, "withdrawn_at": _AT - timedelta(days=1)},
    ],
    ids=lambda overrides: ",".join(overrides),
)
def test_an_incoherent_related_party_operation_is_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _operation(_RELATED, **overrides)


@pytest.mark.parametrize(
    ("base", "overrides"),
    [
        (_INTANGIBLES, {"tipo_operacion": "06"}),
        (_INTANGIBLES, {"valuation_method": "1A"}),
        (_INTANGIBLES, {"specific_operation": True}),
        (_INTANGIBLES, {"exclusion": Modelo232Exclusion.CONSOLIDATION_GROUP}),
        (_INTANGIBLES, {"counterparty_tax_id": None}),
        (_HAVEN_OPERATION, {"counterparty_tax_id": "B00000001"}),
        (_HAVEN_OPERATION, {"tipo_vinculacion": "D"}),
        (_HAVEN_OPERATION, {"exclusion": Modelo232Exclusion.AIE_OR_REGISTERED_UTE}),
        (_HAVEN_OPERATION, {"specific_operation": True}),
    ],
    ids=lambda value: ",".join(value) if isinstance(value, dict) else "",
)
def test_a_field_the_design_does_not_ask_of_a_kind_is_refused(
    base: dict[str, object], overrides: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        _operation(base, **overrides)


def test_a_withdrawn_operation_states_when_it_was_taken_back() -> None:
    later = _AT + timedelta(days=1)
    withdrawn = _operation(_RELATED).withdrawn(later)
    assert not withdrawn.active
    assert withdrawn.withdrawn_at == later
    assert Modelo232Operation.model_validate_json(withdrawn.model_dump_json()) == withdrawn


def test_a_refused_operation_never_echoes_what_was_entered() -> None:
    with pytest.raises(ValidationError) as refused:
        _operation(
            _RELATED,
            counterparty_tax_id=_SYNTHETIC_ID,
            counterparty_name=_SYNTHETIC_NAME,
            amount_eur=Decimal("-123456.78"),
        )
    text = str(refused.value) + repr(refused.value.errors(include_input=False))
    for secret in (_SYNTHETIC_ID, _SYNTHETIC_NAME, "123456.78"):
        assert secret not in text


def test_a_none_statement_needs_an_answerable_note_and_a_coherent_withdrawal() -> None:
    statement = Modelo232NoneStatement(statement_id="b" * 32, ejercicio=_YEAR, note="Synthetic note.", stated_at=_AT)
    withdrawn = statement.withdrawn(_AT + timedelta(days=1))
    assert statement.active
    assert not withdrawn.active
    assert Modelo232NoneStatement.model_validate_json(withdrawn.model_dump_json()) == withdrawn
    for bad in (
        {"note": "   "},
        {"note": ""},
        {"state": Modelo232StatementState.WITHDRAWN},
        {"withdrawn_at": _AT},
        {"state": Modelo232StatementState.WITHDRAWN, "withdrawn_at": _AT - timedelta(seconds=1)},
        {"statement_id": "short"},
    ):
        with pytest.raises(ValidationError):
            Modelo232NoneStatement.model_validate(
                {"statement_id": "b" * 32, "ejercicio": _YEAR, "note": "ok", "stated_at": _AT, **bad}
            )


def test_a_turnover_statement_names_its_source_and_stays_non_negative() -> None:
    statement = Modelo232TurnoverStatement(
        statement_id="c" * 32,
        ejercicio=_YEAR,
        turnover_eur=Decimal("0.00"),
        source=Modelo232TurnoverSource.OPERATOR_ESTIMATE,
        source_reference="Synthetic ref",
        stated_at=_AT,
    )
    assert statement.active
    assert Modelo232TurnoverStatement.model_validate_json(statement.model_dump_json()) == statement
    base = statement.model_dump()
    for bad in (
        {"turnover_eur": Decimal("-1.00")},
        {"turnover_eur": Decimal("1.005")},
        {"source_reference": " "},
        {"source_reference": ""},
        {"source": "unknown_source"},
        {"state": Modelo232StatementState.WITHDRAWN},
    ):
        with pytest.raises(ValidationError):
            Modelo232TurnoverStatement.model_validate({**base, **bad})


def test_the_year_guard_counts_every_write_of_its_ejercicio() -> None:
    guard = Modelo232YearGuard(ejercicio=_YEAR, counter=1)
    assert guard.advanced().counter == 2
    assert guard.identity == _YEAR
    with pytest.raises(ValidationError):
        Modelo232YearGuard(ejercicio=_YEAR, counter=0)
