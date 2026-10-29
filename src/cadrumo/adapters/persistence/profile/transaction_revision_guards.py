"""Encrypted SQL repository with atomic per-bucket transaction reads and writes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ....core.logging import get_logger
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import (
    Transaction,
)
from ..storage.secure_object_namespaces import (
    TRANSACTION_CATALOGUE_NAMESPACE,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.sql.secure_object_records import SecureObjectRevisionAssertion


_log = get_logger(__name__)


def resolved_transaction_row_revisions(row_revisions: Mapping[str, str | None]) -> dict[str, str] | None:
    """Refuse a revision digest when any addressed transaction lacks a revision."""
    resolved_row_revisions: dict[str, str] = {}
    for transaction_id, row_revision in row_revisions.items():
        if row_revision is None:
            return None
        resolved_row_revisions[transaction_id] = row_revision
    return resolved_row_revisions


def absent_transaction_index_assertions(
    index_key: str, include_assertions: bool
) -> tuple[SecureObjectRevisionAssertion, ...]:
    """Prepare the absent membership witness only for an assertion-bearing read."""
    from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
    from ..storage.sql.secure_object_records import SecureObjectRevisionAssertion

    assertions = (
        (
            SecureObjectRevisionAssertion(
                namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                object_key=index_key,
                expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
            ),
        )
        if include_assertions
        else ()
    )
    return assertions


def require_transaction_edit_link_identity(current: Transaction, replacement: Transaction) -> None:
    """Require linked invoice identity to be changed through its reciprocal owner."""
    old_id = current.transaction_id
    new_id = replacement.transaction_id
    if replacement.invoice_id != current.invoice_id:
        raise TransactionValidationError("invoice associations require the reciprocal link operation")
    if old_id != new_id and current.invoice_id is not None:
        raise TransactionValidationError("linked transaction identity cannot change without updating its invoice link")
