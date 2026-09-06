"""Every persisted ledger field an operator can set is visible to the no-op guard.

``mutation_signature`` decides whether an edit changed anything. Two equal
signatures make the update a no-op and the caller refuses it with "manual
ledger update must change at least one ledger field" — so a persisted field
missing from the tuple is not merely uncompared. An edit touching ONLY that
field is REJECTED and the operator's correction is dropped on the floor.

``recargo_amount`` and ``deduction_fact_kind`` were both absent while
``_transaction_from_command`` persisted them, and both are Modelo 303 figures.
An operator correcting a recargo de equivalencia was told nothing had changed.

The two projections in ``actions_common`` are maintained by hand and agree only
because someone keeps them agreeing; this compares them mechanically so a
thirty-second field added to one and not the other is a red result rather than
a silently unsaveable field.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .. import actions_common
from ..actions_common import mutation_signature

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The one field the signature may omit. ``classified_by`` is provenance a write
#: stamps rather than a value the operator set, so comparing it would make every
#: re-classification look like a change and defeat the guard entirely.
_DELIBERATE_EXCLUSIONS = frozenset({"classified_by"})


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="p1",
        booked_date=date(2026, 3, 1),
        value_date=None,
        amount=Decimal("100.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="compra",
        provenance=RawProvenance(
            source_path=Path("x"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 3, 1, tzinfo=UTC),
            provider_name="t",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2026, 3, 1, tzinfo=UTC),
            "modified_at": datetime(2026, 3, 1, tzinfo=UTC),
        },
    )


def _signature_fields() -> set[str]:
    """The attribute names ``mutation_signature`` folds into its tuple."""
    tree = ast.parse(inspect.getsource(actions_common.mutation_signature).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            return {element.attr for element in node.value.elts if isinstance(element, ast.Attribute)}
    raise AssertionError("mutation_signature no longer returns a tuple literal")


def _persisted_fields() -> set[str]:
    """The keys of the sibling full-field projection over the same record."""
    tree = ast.parse(inspect.getsource(actions_common._transaction_idempotency_fields).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return {key.value for key in node.value.keys if isinstance(key, ast.Constant)}
    raise AssertionError("_transaction_idempotency_fields no longer returns a dict literal")


def test_no_persisted_field_is_invisible_to_the_no_op_guard() -> None:
    """A field the guard cannot see is a field the operator cannot edit alone."""
    invisible = _persisted_fields() - _signature_fields() - _DELIBERATE_EXCLUSIONS

    assert not invisible, f"persisted ledger fields an edit could not save on their own: {sorted(invisible)}"


def test_the_signature_claims_no_field_the_record_does_not_persist() -> None:
    """Drift in the other direction: comparing something nothing writes."""
    assert not _signature_fields() - _persisted_fields()


def test_the_exclusion_is_real_rather_than_a_stale_name() -> None:
    """Guard the allowance itself, so it cannot silently cover a renamed field."""
    assert _persisted_fields() >= _DELIBERATE_EXCLUSIONS


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recargo_amount", Decimal("5.20")),
        ("taxable_base", Decimal("82.64")),
        ("notes", "corrección del recargo"),
    ],
)
def test_changing_one_field_alone_registers_as_a_change(field: str, value: object) -> None:
    """The behaviour the field list exists to produce, at the recargo that was broken."""
    transaction = _transaction()

    assert mutation_signature(transaction) != mutation_signature(transaction.model_copy(update={field: value}))


def test_an_untouched_row_is_still_a_no_op() -> None:
    """The guard must keep refusing genuine no-ops, or it stops being a guard."""
    transaction = _transaction()

    assert mutation_signature(transaction) == mutation_signature(transaction.model_copy())
