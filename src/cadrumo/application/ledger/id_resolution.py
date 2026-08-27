"""Transaction-id prefix resolution and display-id width computation.

Provides the cross-cutting helpers required by the ledger CLI surface to
deliver the dual `full_id` / `display_id` identity contract and the stable
operator lineage handle across edits:

- :func:`compute_display_id_width` returns the minimum prefix width that
  keeps every transaction id in the supplied set uniquely addressable,
  with a floor of :data:`MINIMUM_DISPLAY_ID_WIDTH`. The width grows
  automatically as the bucket fills; it is never hard-coded to 8.
- :func:`resolve_transaction_id` accepts a user-supplied prefix and
  returns the matching canonical 64-character hash, raising
  :exc:`cadrumo.domain.transactions.TransactionIdPrefixError` on
  zero-match or ambiguous-prefix conditions.
- :func:`resolve_lineage_transaction_id` extends that resolver with a
  read-side lineage lookup: when a prefix names no *live* row but it
  (or an unambiguous prefix of it) names a superseded id in some live
  row's edit-lineage chain, the resolver returns that current row's id,
  so an old handle written down before an edit keeps answering.

The matching rule: a prefix matches a full id when the full id starts
with the prefix (lowercase, hex). A prefix that equals a full id resolves
trivially. Empty input and non-hex characters are refused.

Lineage resolution is a *read-side lookup convenience over the
authoritative content-addressed id*, not a change to how ids are minted.
The content hash (see
:func:`cadrumo.domain.transactions.derive_transaction_id`) remains the single
authority for storage, audit, and machine consumers; this module never
freezes an id across an edit. It only lets a historical handle resolve to
the row that now carries the edited content.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...domain.transactions import Transaction, TransactionCatalogue, TransactionIdPrefixError
from .actions_common import transaction_modelo_source_ids

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
        raise TransactionIdPrefixError(
            translated_message="application.ledger.errors.transaction_id_prefix_empty",
        )
    if not _HEX_ALPHABET.issuperset(normalized):
        raise TransactionIdPrefixError(
            translated_message="application.ledger.errors.transaction_id_prefix_non_hex",
            context={"prefix": repr(prefix)},
        )
    if len(normalized) > _FULL_ID_LENGTH:
        raise TransactionIdPrefixError(
            translated_message="application.ledger.errors.transaction_id_prefix_too_long",
            context={"prefix": repr(prefix), "max_length": _FULL_ID_LENGTH},
        )
    matches: list[str] = sorted(tx_id for tx_id in transaction_ids if tx_id.startswith(normalized))
    if not matches:
        raise TransactionIdPrefixError(
            translated_message="application.ledger.errors.transaction_id_prefix_no_match",
            context={"prefix": repr(prefix)},
        )
    if len(matches) > 1:
        joined = ", ".join(matches)
        raise TransactionIdPrefixError(
            translated_message="application.ledger.errors.transaction_id_prefix_ambiguous",
            context={"prefix": repr(prefix), "count": len(matches), "matches": joined},
        )
    return matches[0]


def _lineage_handles(transaction: Transaction) -> tuple[str, ...]:
    """Return every id that addresses ``transaction`` across its edit lineage.

    Reuses the finalized-modelo guard's lineage walker
    (:func:`cadrumo.application.ledger.actions_common.transaction_modelo_source_ids`)
    so the read-side handle set and the write-side guard set are computed
    by one authority: the transaction's own current id plus every
    ``previous_transaction_id`` recorded in its
    :class:`cadrumo.domain.transactions.TransactionEditLineageEntry` chain.
    """
    return transaction_modelo_source_ids(transaction)


def resolve_lineage_transaction_id(prefix: str, catalogue: TransactionCatalogue) -> str:
    """Resolve ``prefix`` to a live row, following edit lineage when needed.

    The resolution order is:

    1. Try :func:`resolve_transaction_id` against the live catalogue ids.
       A current id, a split parent left in the catalogue, an archived
       merged child, or an unambiguous prefix of any of them resolves
       here unchanged. This preserves the existing resolver's behaviour
       exactly for every handle that names a row still in the catalogue.
    2. When step 1 finds no live row, treat ``prefix`` as a *historical*
       handle and walk every live row's edit-lineage chain. An
       ``update`` that edits an id-affecting fact re-derives the
       content-addressed id and removes the old id from the catalogue,
       recording it as a ``previous_transaction_id`` on the heir's
       :class:`cadrumo.domain.transactions.TransactionEditLineageEntry`
       chain. If ``prefix`` (or an unambiguous prefix of it) names a
       superseded id in exactly one live row's lineage, that row's
       *current* id is returned.

    This is a read-side lookup convenience over the authoritative
    content-addressed id: the id is never frozen across an edit, and the
    content hash stays the single storage/audit authority. The lineage
    chain is the same substrate the finalized-modelo guard already walks,
    so no new storage is introduced.

    Args:
        prefix: A user-supplied prefix or full id. Lowercase hex.
        catalogue: The active bucket's loaded
            :class:`cadrumo.domain.transactions.TransactionCatalogue`.

    Returns:
        The unique full transaction id of the live row that ``prefix``
        addresses — directly, or through its edit lineage.

    Raises:
        TransactionIdPrefixError: When ``prefix`` is empty, non-hex, too
            long, names no live row and no lineage handle, or matches
            more than one live row or lineage row ambiguously.
    """
    live_ids = tuple(transaction.transaction_id for transaction in catalogue.values())
    try:
        return resolve_transaction_id(prefix, live_ids)
    except TransactionIdPrefixError as live_error:
        if live_error.translated_message != "application.ledger.errors.transaction_id_prefix_no_match":
            # Empty / non-hex / too-long / ambiguous-live: the prefix is
            # malformed or already ambiguous over live rows. Lineage
            # resolution cannot make it less ambiguous, so surface the
            # original refusal unchanged. Discriminate on the typed error key
            # rather than the rendered (now localised) message text.
            raise
        normalized = prefix.strip().lower()
        heirs: dict[str, str] = {}
        for transaction in catalogue.values():
            for handle in _lineage_handles(transaction):
                if handle == transaction.transaction_id:
                    continue
                if handle.startswith(normalized):
                    heirs[handle] = transaction.transaction_id
        current_ids = {transaction.transaction_id for transaction in catalogue.values()}
        resolved = {current for current in heirs.values() if current in current_ids}
        if not resolved:
            raise
        if len(resolved) > 1:
            joined = ", ".join(sorted(resolved))
            raise TransactionIdPrefixError(
                translated_message="application.ledger.errors.transaction_id_prefix_ambiguous",
                context={"prefix": repr(prefix), "count": len(resolved), "matches": joined},
            ) from live_error
        return next(iter(resolved))


__all__ = [
    "MINIMUM_DISPLAY_ID_WIDTH",
    "compute_display_id_width",
    "resolve_lineage_transaction_id",
    "resolve_transaction_id",
]
