"""A saver's stored return is refused at verify once the ledger rows its savings boxes rest on move.

The interest box is calculated from the ledger rows linked to a savings position.
Those rows are the calculation's contributors, so a later change to one of them,
an unlinked row, or a newly linked row leaves the stored box unsupported and
verify reports the ledger drift. A row the savings family never read moves
nothing.

Real encrypted store, real registered operations, real calculate and verify.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.manual_update import update_manual_transaction_fields
from cadrumo.application.ledger.models import ManualLedgerTransactionPatch
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.tests.savings_link_rows import savings_row
from cadrumo.entrypoints.ledger_action_composition import compose_ledger_action_ports
from cadrumo.tests.env_scope import ready_clave_settings

from ....application.aggregation.tests.capital_mobiliario_position_support import (
    DEPOSIT,
    SavingsPosition,
    linked_row,
    position_facts,
)
from .m130_m100_annual_support import BUCKET_ID, OPERATOR_SCOPE_PORTS, TAX_ID, YEAR, verify_revision_for_test
from .renta_persona_support import (
    PAYER_A,
    PAYER_B,
    Persona,
    calculate_annual,
    record_certificate,
    register_refund_account,
    seed_profile,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

__all__ = ["secure_objects"]

_SAVER = Persona(categories="trabajo,capital_mobiliario")
_INTEREST = validated_casilla_id("0027")
_DEPOSIT = SavingsPosition("deposito", PAYER_B, "Banco Sintetico", share="100.00", since=date(YEAR - 1, 1, 1))
_CLASSIFIED_AT = datetime(YEAR, 7, 1, 9, 0, tzinfo=UTC)
_DRIFT_KEY_PREFIX = "application.modelo.findings.ledger_snapshot_drift"


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _classified(row: Transaction) -> Transaction:
    return _revalidated(
        row,
        business_classification=BusinessClassification.PERSONAL,
        classified_at=_CLASSIFIED_AT,
        classified_by="manual",
    )


def _revalidated(row: Transaction, **changes: object) -> Transaction:
    """Return ``row`` with ``changes`` applied, validated again and keeping its identity."""
    return Transaction.model_validate({**row.model_dump(), **changes, "transaction_id": row.transaction_id})


def _interest_row(row_id: str, amount: str, *, on: date) -> Transaction:
    return _classified(linked_row(row_id, DEPOSIT, "intereses", amount, on=on))


def _first() -> Transaction:
    return _interest_row("deposit-interest-h1", "200.00", on=date(YEAR, 6, 30))


def _second() -> Transaction:
    return _interest_row("deposit-interest-h2", "124.00", on=date(YEAR, 12, 31))


def _groceries() -> Transaction:
    """An unlinked personal payment no Renta source family reads."""
    base = savings_row(provider_id="groceries")
    raw = base.raw.model_copy(update={"amount": Decimal("50.00"), "booked_date": date(YEAR, 3, 14)})
    return _classified(savings_row(provider_id="groceries", raw=raw, direction=TransactionDirection.OUTGOING))


def _store(objects: SecureObjectRepository) -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)


def _calculate(
    objects: SecureObjectRepository, directory: Path, operation: PinnedAuthorityOperation
) -> CalculationRevision:
    seed_profile(_SAVER, extra_facts=position_facts({DEPOSIT: _DEPOSIT}))
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="3000.00",
        importe_integro="24000.00",
    )
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_B,
        income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
        retencion="76.00",
        importe_integro="400.00",
    )
    _store(objects).save(TransactionCatalogue.from_transactions((_first(), _second(), _groceries())))
    register_refund_account(objects)
    return calculate_annual(objects)


def _drift_keys(revision: CalculationRevision) -> list[str]:
    report = verify_revision_for_test(
        revision.calculation_revision_id,
        actor="savings-drift",
        workflow_profile=workflow_profile(_SAVER),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    return [
        finding.message_locale_key
        for finding in report.findings
        if finding.message_locale_key.startswith(_DRIFT_KEY_PREFIX)
    ]


def _replace(objects: SecureObjectRepository, row: Transaction) -> None:
    store = _store(objects)
    rows = {item.transaction_id: item for item in store.load().values()}
    rows[row.transaction_id] = row
    store.save(TransactionCatalogue.from_transactions(tuple(rows.values())))


def _edit_amount(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, row: Transaction, amount: str
) -> None:
    """Change a row's amount through the ledger's own edit door, which writes the row's next revision."""
    update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=row.transaction_id,
        patch=ManualLedgerTransactionPatch(amount=Decimal(amount)),
        actor="savings-drift",
        source_command="aeat app ledger edit",
        ports=compose_ledger_action_ports(bucket_id=BUCKET_ID, operation=operation, objects=objects),
    )


def _change_a_linked_amount(objects: SecureObjectRepository, operation: PinnedAuthorityOperation) -> None:
    """The edit retires the consumed row and links its next revision, so both sides of the drift show."""
    _edit_amount(objects, operation, _first(), "210.00")


def _unlink_a_row(objects: SecureObjectRepository, operation: PinnedAuthorityOperation) -> None:
    del operation
    _replace(objects, _revalidated(_second(), posicion_ref=None, concepto_capital_mobiliario=None))


def _link_a_new_row(objects: SecureObjectRepository, operation: PinnedAuthorityOperation) -> None:
    del operation
    _replace(objects, _interest_row("deposit-interest-bonus", "10.00", on=date(YEAR, 9, 30)))


@pytest.fixture
def calculated(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> CalculationRevision:
    revision = _calculate(secure_objects, tmp_path, operation)
    assert Decimal(revision.casilla_values[_INTEREST]) == Decimal("400.00")
    assert {_first().transaction_id, _second().transaction_id} <= set(revision.source_transaction_ids)
    assert _groceries().transaction_id not in revision.source_transaction_ids
    return revision


def test_the_untouched_ledger_leaves_the_savings_return_current(calculated: CalculationRevision) -> None:
    assert _drift_keys(calculated) == []


@pytest.mark.parametrize(
    ("move", "expected"),
    [
        (_change_a_linked_amount, f"{_DRIFT_KEY_PREFIX}_with_added"),
        (_unlink_a_row, f"{_DRIFT_KEY_PREFIX}_changed"),
        (_link_a_new_row, f"{_DRIFT_KEY_PREFIX}_added"),
    ],
    ids=["linked-amount-changed", "row-unlinked", "row-newly-linked"],
)
def test_a_move_in_the_rows_the_savings_boxes_rest_on_is_reported_as_ledger_drift(
    calculated: CalculationRevision,
    secure_objects: SecureObjectRepository,
    move: Callable[[SecureObjectRepository, PinnedAuthorityOperation], None],
    expected: str,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    move(secure_objects, operation)

    keys = _drift_keys(calculated)
    assert keys == [expected], keys


def test_a_change_to_a_row_the_savings_family_never_read_is_not_drift(
    calculated: CalculationRevision, secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _edit_amount(secure_objects, operation, _groceries(), "75.00")

    assert _drift_keys(calculated) == []
