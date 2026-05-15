"""Transaction-id prefix resolution and display-id width computation.

Provides the two cross-cutting helpers required by the ledger CLI surface
to deliver the dual `full_id` / `display_id` identity contract:

- :func:`compute_display_id_width` returns the minimum prefix width that
  keeps every transaction id in the supplied set uniquely addressable,
  with a floor of :data:`MINIMUM_DISPLAY_ID_WIDTH`. The width grows
  automatically as the bucket fills; it is never hard-coded to 8.
- :func:`resolve_transaction_id` accepts a user-supplied prefix and
  returns the matching canonical 64-character hash, raising
  :exc:`aeat.domain.transactions.TransactionIdPrefixError` on
  zero-match or ambiguous-prefix conditions.

The matching rule: a prefix matches a full id when the full id starts
with the prefix (lowercase, hex). A prefix that equals a full id resolves
trivially. Empty input and non-hex characters are refused.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...domain.transactions import TransactionIdPrefixError

MINIMUM_DISPLAY_ID_WIDTH = 8
_FULL_ID_LENGTH = 64
_HEX_ALPHABET = frozenset("0123456789abcdef")


def compute_display_id_width(transaction_ids: Iterable[str]) -> int:
    """Return the minimum unique-prefix width over ``transaction_ids``.

    Args:
        transaction_ids: Full 64-character hex transaction ids drawn from
            the active bucket.

    Returns:
        The smallest width ``w`` such that every id's first ``w``
        characters uniquely identify it within the supplied set, capped
        below by :data:`MINIMUM_DISPLAY_ID_WIDTH` and above by
        :data:`_FULL_ID_LENGTH`.
    """

    ids = tuple(transaction_ids)
    if not ids:
        return MINIMUM_DISPLAY_ID_WIDTH
    for width in range(MINIMUM_DISPLAY_ID_WIDTH, _FULL_ID_LENGTH + 1):
        prefixes = {tx_id[:width] for tx_id in ids}
        if len(prefixes) == len(set(ids)):
            return width
    return _FULL_ID_LENGTH


def resolve_transaction_id(prefix: str, transaction_ids: Iterable[str]) -> str:
    """Resolve ``prefix`` to a single full transaction id.

    Args:
        prefix: A user-supplied prefix or full id. Lowercase hex.
        transaction_ids: The full ids known to the active bucket.

    Returns:
        The unique full transaction id matching ``prefix``.

    Raises:
        TransactionIdPrefixError: When ``prefix`` is empty, contains
            non-hex characters, matches no transaction, or matches more
            than one transaction. The error message lists all collision
            candidates so the operator can disambiguate by lengthening
            their prefix.
    """

    normalized = (prefix or "").strip().lower()
    if not normalized:
        raise TransactionIdPrefixError("transaction id prefix is empty")
    if not _HEX_ALPHABET.issuperset(normalized):
        raise TransactionIdPrefixError(f"transaction id prefix {prefix!r} contains non-hex characters")
    if len(normalized) > _FULL_ID_LENGTH:
        raise TransactionIdPrefixError(f"transaction id prefix {prefix!r} is longer than {_FULL_ID_LENGTH} characters")
    matches: tuple[str, ...] = tuple(sorted(tx_id for tx_id in transaction_ids if tx_id.startswith(normalized)))
    if not matches:
        raise TransactionIdPrefixError(f"no transaction matches id prefix {prefix!r}")
    if len(matches) > 1:
        joined = ", ".join(matches)
        raise TransactionIdPrefixError(
            f"transaction id prefix {prefix!r} matches {len(matches)} transactions: {joined}"
        )
    return matches[0]


__all__ = [
    "MINIMUM_DISPLAY_ID_WIDTH",
    "compute_display_id_width",
    "resolve_transaction_id",
]
