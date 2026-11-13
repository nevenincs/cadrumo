"""The Modelo 232 art. 2 grounds applied to stated operations, with the pinned registry's own thresholds.

Orden HFP/816/2017 art. 2.1.a tests "el conjunto de operaciones" with one related
person above 250.000 euros, art. 2.1.b the specific operations "de cada una de este
tipo" above 100.000 euros, art. 2.3 the operations of one type and valuation method
above 50% of the turnover. The thresholds are read from the revision that governs
each ejercicio; the law's own amounts are asserted once, against the order, and every
other amount is built from what the registry returns. Identifiers, names and amounts
are synthetic.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ....core.modelo import Modelo
from ....domain.calculations.registry.applicability_models import LedgerPayerFactDerivation
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.m232_obligation import (
    Modelo232Basis,
    Modelo232Ground,
    Modelo232GroundState,
    Modelo232Obligation,
    Modelo232ObligationFinding,
    Modelo232Thresholds,
    assess_modelo_232_obligation,
)
from ....domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)
from ..m232_registry_parameters import always_specific_operation_types, modelo_232_thresholds
from ..m232_related_party_obligation import ledger_payer_fact_derivation
from ..m232_related_party_repository import Modelo232RelatedPartyPersistenceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = tuple(filing_year_envelope().years)
_MODELO = Modelo("232")
_PERIOD = "0A"
_CENT = Decimal("0.01")
_TAX_ID_ONE = "B99999991"
_TAX_ID_TWO = "B99999992"
_NAME = "Synthetic Related Holding"
_GENERAL_TYPE = "06"
_OTHER_GENERAL_TYPE = "11"
_METHOD_ONE = "1A"
_METHOD_TWO = "1B"


def _thresholds(operation: PinnedAuthorityOperation, ejercicio: int) -> Modelo232Thresholds:
    return modelo_232_thresholds(ejercicio, operation=operation, modelo=_MODELO, period=_PERIOD)


def _operation(ejercicio: int, **overrides: object) -> Modelo232Operation:
    fields: dict[str, object] = {
        "operation_id": uuid4().hex,
        "ejercicio": ejercicio,
        "operation_kind": Modelo232OperationKind.RELATED_PARTY,
        "counterparty_tax_id": _TAX_ID_ONE,
        "counterparty_name": _NAME,
        "counterparty_country": "DE",
        "tipo_vinculacion": "D",
        "tipo_operacion": _GENERAL_TYPE,
        "valuation_method": _METHOD_ONE,
        "direction": Modelo232Direction.PAGO,
        "amount_eur": Decimal("1.00"),
        "stated_at": datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return Modelo232Operation.model_validate(fields)


def _turnover(ejercicio: int, amount: Decimal) -> Modelo232TurnoverStatement:
    return Modelo232TurnoverStatement(
        statement_id=uuid4().hex,
        ejercicio=ejercicio,
        turnover_eur=amount,
        source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
        source_reference="Synthetic ref: accounts",
        stated_at=datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC),
    )


def _none(ejercicio: int) -> Modelo232NoneStatement:
    return Modelo232NoneStatement(
        statement_id=uuid4().hex,
        ejercicio=ejercicio,
        note="Synthetic note: no dealings.",
        stated_at=datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC),
    )


def _assess(
    operation: PinnedAuthorityOperation,
    ejercicio: int,
    *operations: Modelo232Operation,
    turnover: Decimal | None = None,
    nones: tuple[Modelo232NoneStatement, ...] = (),
) -> Modelo232ObligationFinding:
    turnovers = () if turnover is None else (_turnover(ejercicio, turnover),)
    return assess_modelo_232_obligation(
        ejercicio,
        operations=operations,
        nones=nones,
        turnovers=turnovers,
        thresholds=_thresholds(operation, ejercicio),
    )


def _ground(finding: Modelo232ObligationFinding, ground: Modelo232Ground) -> Modelo232GroundState:
    return next(item.state for item in finding.grounds if item.ground is ground)


def _ample_turnover(thresholds: Modelo232Thresholds, total: Decimal) -> Decimal:
    """A turnover whose share is above ``total``, so the art. 2.3 ground cannot be met by it."""
    return total / thresholds.turnover_share + Decimal(1)


def test_the_registry_thresholds_are_the_amounts_the_order_prints(operation: PinnedAuthorityOperation) -> None:
    """Art. 2.1.a: 250.000 euros; art. 2.1.b: 100.000 euros; art. 2.3: 50%; LIS art. 18.3 5.º: intangibles (Tabla C 02)."""
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        assert thresholds.same_related_party_eur == Decimal("250000.00"), ejercicio
        assert thresholds.specific_operations_eur == Decimal("100000.00"), ejercicio
        assert thresholds.turnover_share == Decimal("0.50"), ejercicio
        assert thresholds.always_specific_types == frozenset({"02"}), ejercicio
        assert always_specific_operation_types(ejercicio, operation=operation) == frozenset({"02"}), ejercicio


def test_nothing_stated_is_undecided_even_with_a_turnover(operation: PinnedAuthorityOperation) -> None:
    for ejercicio in _YEARS:
        bare = _assess(operation, ejercicio)
        with_turnover = _assess(operation, ejercicio, turnover=Decimal("1000000.00"))
        assert bare.basis is Modelo232Basis.NOTHING_STATED, ejercicio
        assert bare.obligation is Modelo232Obligation.UNDECIDED, ejercicio
        assert with_turnover.obligation is Modelo232Obligation.UNDECIDED, ejercicio


def test_a_none_statement_is_not_owed_and_a_withdrawn_one_is_undecided(operation: PinnedAuthorityOperation) -> None:
    for ejercicio in _YEARS:
        standing = _assess(operation, ejercicio, nones=(_none(ejercicio),))
        withdrawn = _assess(
            operation,
            ejercicio,
            nones=(_none(ejercicio).withdrawn(datetime(ejercicio, 5, 1, tzinfo=UTC)),),
        )
        assert standing.obligation is Modelo232Obligation.NOT_OWED, ejercicio
        assert withdrawn.obligation is Modelo232Obligation.UNDECIDED, ejercicio


def test_a_none_statement_beside_an_operation_is_a_contradiction_that_decides_nothing(
    operation: PinnedAuthorityOperation,
) -> None:
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        above = _operation(ejercicio, amount_eur=thresholds.same_related_party_eur + _CENT)
        finding = _assess(operation, ejercicio, above, nones=(_none(ejercicio),))
        assert finding.basis is Modelo232Basis.CONTRADICTION, ejercicio
        assert finding.obligation is Modelo232Obligation.UNDECIDED, ejercicio


def test_the_per_person_total_must_exceed_the_threshold_and_adds_income_and_payment(
    operation: PinnedAuthorityOperation,
) -> None:
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        ample = _ample_turnover(thresholds, thresholds.same_related_party_eur + _CENT)
        at_threshold = _assess(
            operation, ejercicio, _operation(ejercicio, amount_eur=thresholds.same_related_party_eur), turnover=ample
        )
        half = thresholds.same_related_party_eur / 2 + _CENT
        income_and_payment = (
            _operation(ejercicio, amount_eur=half, direction=Modelo232Direction.INGRESO),
            _operation(ejercicio, amount_eur=half, direction=Modelo232Direction.PAGO),
        )
        same_person = _assess(operation, ejercicio, *income_and_payment, turnover=ample)
        two_people = _assess(
            operation,
            ejercicio,
            income_and_payment[0],
            income_and_payment[1].model_copy(update={"counterparty_tax_id": _TAX_ID_TWO}),
            turnover=ample,
        )
        assert at_threshold.obligation is Modelo232Obligation.NOT_OWED, ejercicio
        assert same_person.obligation is Modelo232Obligation.OWED, ejercicio
        assert _ground(same_person, Modelo232Ground.SAME_RELATED_PARTY) is Modelo232GroundState.MET, ejercicio
        assert two_people.obligation is Modelo232Obligation.NOT_OWED, ejercicio


def test_specific_operations_add_up_by_type_over_every_counterparty(operation: PinnedAuthorityOperation) -> None:
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        share = thresholds.specific_operations_eur / 2 + _CENT
        ample = _ample_turnover(thresholds, share * 2)
        two_parties = (
            _operation(ejercicio, amount_eur=share, specific_operation=True),
            _operation(ejercicio, amount_eur=share, specific_operation=True, counterparty_tax_id=_TAX_ID_TWO),
        )
        other_types = (
            two_parties[0],
            two_parties[1].model_copy(update={"tipo_operacion": _OTHER_GENERAL_TYPE}),
        )
        not_specific = tuple(item.model_copy(update={"specific_operation": False}) for item in two_parties)
        met = _assess(operation, ejercicio, *two_parties, turnover=ample)
        assert met.obligation is Modelo232Obligation.OWED, ejercicio
        assert _ground(met, Modelo232Ground.SPECIFIC_OPERATION_TYPE) is Modelo232GroundState.MET, ejercicio
        assert _ground(met, Modelo232Ground.SAME_RELATED_PARTY) is Modelo232GroundState.NOT_MET, ejercicio
        assert _assess(operation, ejercicio, *other_types, turnover=ample).obligation is Modelo232Obligation.NOT_OWED
        assert _assess(operation, ejercicio, *not_specific, turnover=ample).obligation is Modelo232Obligation.NOT_OWED


def test_an_intangibles_operation_counts_as_specific_whatever_the_filer_states(
    operation: PinnedAuthorityOperation,
) -> None:
    """Under the per-person threshold the sum would be general; counted as specific it exceeds the type threshold."""
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        amount = thresholds.specific_operations_eur + _CENT
        assert amount < thresholds.same_related_party_eur
        (intangible_type,) = thresholds.always_specific_types
        stated_not_specific = _operation(
            ejercicio, tipo_operacion=intangible_type, amount_eur=amount, specific_operation=False
        )
        other_type = stated_not_specific.model_copy(update={"tipo_operacion": _GENERAL_TYPE})
        ample = _ample_turnover(thresholds, amount)
        intangible = _assess(operation, ejercicio, stated_not_specific, turnover=ample)
        assert intangible.obligation is Modelo232Obligation.OWED, ejercicio
        assert _ground(intangible, Modelo232Ground.SPECIFIC_OPERATION_TYPE) is Modelo232GroundState.MET, ejercicio
        assert _assess(operation, ejercicio, other_type, turnover=ample).obligation is Modelo232Obligation.NOT_OWED


def test_the_turnover_ground_needs_a_stated_turnover_and_compares_one_type_and_method(
    operation: PinnedAuthorityOperation,
) -> None:
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        small = thresholds.same_related_party_eur / 10
        turnover = small * 2 - _CENT
        assert small > thresholds.turnover_share * turnover
        stated = _operation(ejercicio, amount_eur=small)
        undecided = _assess(operation, ejercicio, stated)
        met = _assess(operation, ejercicio, stated, turnover=turnover)
        not_met = _assess(operation, ejercicio, stated, turnover=small * 2)
        assert undecided.obligation is Modelo232Obligation.UNDECIDED, ejercicio
        assert _ground(undecided, Modelo232Ground.TURNOVER_SHARE) is Modelo232GroundState.UNDECIDED, ejercicio
        assert met.obligation is Modelo232Obligation.OWED, ejercicio
        assert _ground(met, Modelo232Ground.TURNOVER_SHARE) is Modelo232GroundState.MET, ejercicio
        assert not_met.obligation is Modelo232Obligation.NOT_OWED, ejercicio
        assert met.turnover_source is Modelo232TurnoverSource.ANNUAL_ACCOUNTS, ejercicio

        halves = (
            _operation(ejercicio, amount_eur=small / 2 + _CENT, valuation_method=_METHOD_ONE),
            _operation(ejercicio, amount_eur=small / 2 + _CENT, valuation_method=_METHOD_TWO),
        )
        same_method = tuple(item.model_copy(update={"valuation_method": _METHOD_ONE}) for item in halves)
        assert _assess(operation, ejercicio, *halves, turnover=turnover).obligation is Modelo232Obligation.NOT_OWED
        assert _assess(operation, ejercicio, *same_method, turnover=turnover).obligation is Modelo232Obligation.OWED


def test_an_excluded_operation_is_left_out_of_every_total_and_counted_apart(
    operation: PinnedAuthorityOperation,
) -> None:
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        big = thresholds.same_related_party_eur * 2
        ample = _ample_turnover(thresholds, big)
        for exclusion in Modelo232Exclusion:
            excluded = _operation(ejercicio, amount_eur=big, exclusion=exclusion)
            only_excluded = _assess(operation, ejercicio, excluded, turnover=ample)
            beside_small = _assess(operation, ejercicio, excluded, _operation(ejercicio), turnover=ample)
            assert only_excluded.obligation is Modelo232Obligation.NOT_OWED, (ejercicio, exclusion)
            assert only_excluded.counted_operations == 0
            assert only_excluded.excluded_operations == 1
            assert only_excluded.excluded_total_eur == big
            assert beside_small.obligation is Modelo232Obligation.NOT_OWED, (ejercicio, exclusion)
            assert (beside_small.counted_operations, beside_small.excluded_operations) == (1, 1)
        counted = _assess(operation, ejercicio, _operation(ejercicio, amount_eur=big), turnover=ample)
        assert counted.obligation is Modelo232Obligation.OWED, ejercicio


@pytest.mark.parametrize(
    ("kind", "ground"),
    [
        (Modelo232OperationKind.TAX_HAVEN_OPERATION, Modelo232Ground.TAX_HAVEN),
        (Modelo232OperationKind.TAX_HAVEN_HOLDING, Modelo232Ground.TAX_HAVEN),
        (Modelo232OperationKind.INTANGIBLES_REDUCTION, Modelo232Ground.INTANGIBLES_REDUCTION),
    ],
)
def test_a_tax_haven_or_intangibles_reduction_record_is_owed_whatever_its_amount(
    operation: PinnedAuthorityOperation,
    kind: Modelo232OperationKind,
    ground: Modelo232Ground,
) -> None:
    related_person = kind is Modelo232OperationKind.INTANGIBLES_REDUCTION
    fields: dict[str, object] = {
        "operation_kind": kind,
        "amount_eur": Decimal(0),
        "counterparty_tax_id": _TAX_ID_ONE if related_person else None,
        "tipo_vinculacion": "A" if related_person else None,
        "tipo_operacion": None,
        "valuation_method": None,
        "direction": None,
    }
    if related_person:
        fields.update(parent_tax_id=_TAX_ID_TWO, parent_name=_NAME)
    if kind is Modelo232OperationKind.TAX_HAVEN_OPERATION:
        fields["description"] = "Synthetic description"
    if kind is Modelo232OperationKind.TAX_HAVEN_HOLDING:
        fields["participation_percent"] = Decimal("10.00")
    for ejercicio in _YEARS:
        finding = _assess(operation, ejercicio, _operation(ejercicio, **fields))
        assert finding.obligation is Modelo232Obligation.OWED, ejercicio
        assert _ground(finding, ground) is Modelo232GroundState.MET, ejercicio


def test_the_finding_names_counts_and_amounts_but_never_a_counterparty(operation: PinnedAuthorityOperation) -> None:
    ejercicio = filing_year_envelope().horizon
    thresholds = _thresholds(operation, ejercicio)
    finding = _assess(
        operation,
        ejercicio,
        _operation(ejercicio, amount_eur=thresholds.same_related_party_eur + _CENT),
        _operation(ejercicio, counterparty_name="Another Synthetic Name", exclusion=Modelo232Exclusion.PUBLIC_OFFER),
    )
    text = repr(finding)
    assert _TAX_ID_ONE not in text
    assert _NAME not in text
    assert "Another Synthetic Name" not in text
    same_party = next(item for item in finding.grounds if item.ground is Modelo232Ground.SAME_RELATED_PARTY)
    assert same_party.largest_total_eur == thresholds.same_related_party_eur + _CENT
    assert same_party.limit_eur == thresholds.same_related_party_eur


def test_an_intangibles_operation_adds_to_the_per_person_total_of_the_same_counterparty(
    operation: PinnedAuthorityOperation,
) -> None:
    """Art. 2.1.a sums "el conjunto de operaciones" with one person; no operation is left out of it."""
    for ejercicio in _YEARS:
        thresholds = _thresholds(operation, ejercicio)
        (intangible_type,) = thresholds.always_specific_types
        general = _operation(ejercicio, amount_eur=thresholds.same_related_party_eur * Decimal("0.8"))
        intangible = _operation(
            ejercicio,
            tipo_operacion=intangible_type,
            specific_operation=True,
            amount_eur=thresholds.specific_operations_eur * Decimal("0.9"),
        )
        assert general.amount_eur + intangible.amount_eur > thresholds.same_related_party_eur
        assert intangible.amount_eur < thresholds.specific_operations_eur
        ample = _ample_turnover(thresholds, general.amount_eur + intangible.amount_eur)
        same_person = _assess(operation, ejercicio, general, intangible, turnover=ample)
        other_person = _assess(
            operation,
            ejercicio,
            general,
            intangible.model_copy(update={"counterparty_tax_id": _TAX_ID_TWO}),
            turnover=ample,
        )
        assert same_person.obligation is Modelo232Obligation.OWED, ejercicio
        assert _ground(same_person, Modelo232Ground.SAME_RELATED_PARTY) is Modelo232GroundState.MET, ejercicio
        assert _ground(same_person, Modelo232Ground.SPECIFIC_OPERATION_TYPE) is Modelo232GroundState.NOT_MET
        assert other_person.obligation is Modelo232Obligation.NOT_OWED, ejercicio


class _UnreadableStatements:
    """A reader whose storage fails, to prove an unreadable store leaves the fact unknown."""

    def load_operations(self, ejercicio: int) -> tuple[Modelo232Operation, ...]:
        raise Modelo232RelatedPartyPersistenceError("modelo_232_list_m232_operation")

    def load_none_statements(self, ejercicio: int) -> tuple[Modelo232NoneStatement, ...]:
        raise AssertionError("the operations are read first")

    def load_turnover_statements(self, ejercicio: int) -> tuple[Modelo232TurnoverStatement, ...]:
        raise AssertionError("the operations are read first")

    def revision_marker(self, ejercicios: Sequence[int]) -> str:
        raise AssertionError("the marker is not read here")


def test_unreadable_statements_leave_the_fact_unknown(operation: PinnedAuthorityOperation) -> None:
    ejercicio = filing_year_envelope().horizon
    derived = ledger_payer_fact_derivation(
        _UnreadableStatements(), ejercicio, operation=operation, modelo=_MODELO, period=_PERIOD
    )
    assert derived is LedgerPayerFactDerivation.UNKNOWN
