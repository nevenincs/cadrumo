"""The idempotency guard's field set must stay complete and aligned by construction.

The manual ledger add is idempotent-guarded: a retry carrying the same
idempotency key and identical content returns the stored row as a no-op. That
guarantee is only as good as the field set the match compares. A persisted field
missing from the comparison makes a retry that changes ONLY that field look
identical, so the guard returns the old row unchanged and the new value is
dropped without a refusal, a notice, or a non-zero exit -- the operator is told
the write succeeded.

That is not hypothetical. This guard has already lost a field once: a no-op
match that omitted the recargo and the source jurisdiction silently discarded
both on retry, and the fix was to extend the mapping by hand.

The comparison is built from two hand-maintained parallel mappings folded into
POSITIONAL tuples. That shape carries two distinct failure modes and nothing in
the tree pinned either. The mapping's own docstring offers "a single greppable
site" as the safeguard -- greppability is a property of a reader who thinks to
grep, and the field that went missing last time sat in a mapping just as
greppable. These gates make the two claims structural rather than remembered.

Both assertions derive their expected set from the models themselves, never from
a hand-copied list, so a field added to the command model reddens this gate
until someone decides where it belongs -- rather than passing because a second
list was updated to agree with the first.
"""

from __future__ import annotations

import pytest

from ..actions_common import _command_idempotency_fields, _transaction_idempotency_fields
from ..actions_manual import _transaction_from_command
from ._action_test_support import (
    UTC,
    Decimal,
    ManualLedgerTransactionCommand,
    TransactionDirection,
    date,
    datetime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The four command fields the projection deliberately omits, each with the reason
# the projection's own docstring states. Transcribed here so a future author must
# justify an addition rather than quietly grow the set: none of them is content a
# retry could silently drop.
_DELIBERATE_EXCLUSIONS: dict[str, str] = {
    # Scopes the lookup rather than describing the movement: a differing bucket
    # yields a different row, not a false match.
    "bucket_id": "scopes the lookup, not the movement",
    # Provenance of the invocation, not of the movement. Stamped once at creation
    # and deliberately not re-stamped, so folding them in would turn a benign
    # retry from another entry point into a spurious conflict.
    "actor": "invocation provenance, not movement content",
    "source_command": "invocation provenance, not movement content",
    # The match key itself: the stored row was already resolved by the clock-free
    # provider id derived from it, so both sides are equal by construction.
    "idempotency_key": "the match key itself",
}

# The one command field whose projection key is deliberately renamed:
# ``classified_by_override`` is projected as the EFFECTIVE ``classified_by``
# value a write would persist, which is what the stored transaction carries.
_RENAMED_FIELD = "classified_by_override"
_RENAMED_KEY = "classified_by"


def test_the_two_projections_share_one_ordered_key_sequence() -> None:
    """Both sides project the same keys in the same order.

    The guard compares POSITIONAL tuples folded from these mappings, so key
    order is load-bearing in a way it never looks. A key inserted into one
    mapping and not the other does not fail loudly at that key: it shifts every
    later field by one and starts comparing amounts against currencies. Equal
    key SETS would not catch that, which is why this asserts the ordered
    sequence.

    The transaction side is built by the production builder the guard's own
    caller uses, so it is the real record shape rather than a hand-assembled
    stand-in -- while staying free of storage and of the registry, neither of
    which this property depends on.
    """
    command = _a_command()
    transaction = _transaction_from_command(command, occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC))

    command_keys = tuple(_command_idempotency_fields(command))
    transaction_keys = tuple(_transaction_idempotency_fields(transaction))

    assert command_keys == transaction_keys, (
        "the two idempotency projections have drifted; the positional fold will compare "
        f"misaligned fields.\n  command:     {command_keys}\n  transaction: {transaction_keys}"
    )


def test_every_command_field_is_compared_or_deliberately_excluded() -> None:
    """No persisted command field escapes the no-op comparison unnoticed.

    The expected set is derived from the command model, so adding a field to the
    model reddens this gate until the author either projects it or records it as
    a deliberate exclusion with a reason. That is the point: the previous loss
    happened because a field was added and the mapping was not, and nothing in
    the tree noticed.
    """
    model_fields = set(ManualLedgerTransactionCommand.model_fields)
    projected = set(_command_idempotency_fields(_a_command()))

    # Undo the one deliberate rename so the comparison is against model names.
    assert _RENAMED_KEY in projected, f"the {_RENAMED_FIELD} projection key was renamed again"
    projected.discard(_RENAMED_KEY)
    projected.add(_RENAMED_FIELD)

    unaccounted = model_fields - projected - set(_DELIBERATE_EXCLUSIONS)
    assert not unaccounted, (
        "these persisted command fields are absent from the idempotency comparison, so a retry "
        f"changing only one of them would be treated as a no-op and silently dropped: {sorted(unaccounted)}"
    )

    # A projection key naming nothing on the model is a stale entry comparing a
    # field the command no longer carries.
    stale = projected - model_fields
    assert not stale, f"the projection names fields the command model no longer has: {sorted(stale)}"

    # An exclusion naming nothing on the model means a renamed field is hiding
    # inside the allowlist while its new name goes uncompared.
    dangling = set(_DELIBERATE_EXCLUSIONS) - model_fields
    assert not dangling, f"these documented exclusions name no field on the command model: {sorted(dangling)}"


def _a_command() -> ManualLedgerTransactionCommand:
    """Return a command carrying only its required fields.

    The VALUES are irrelevant to both gates -- they compare key sets and key
    order, which the projection builds the same way for any command. Building
    the minimum keeps the fixture from quietly becoming a second, drifting
    declaration of the field set.
    """
    return ManualLedgerTransactionCommand(
        bucket_id="29292929-2929-4929-8929-292929292929",
        booked_date=date(2026, 5, 2),
        value_date=date(2026, 5, 3),
        amount=Decimal("121.00"),
        currency="EUR",
        direction=TransactionDirection.OUTGOING,
        counterparty="Proveedor SL",
        description="material oficina",
        actor="operator-A",
        source_command="aeat app ledger add",
    )
