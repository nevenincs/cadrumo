"""Cross-format re-import identity of a bank movement: normalised narratives, fingerprints and day keys."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...core.hashing import content_hash_hex
from ...core.text_fold import fold_diacritics
from ..identifiers import canonical_decimal_string
from .enums import TransactionDirection

if TYPE_CHECKING:
    from .models import Transaction
    from .raw_transaction import RawTransaction


_REFERENCE_NOISE = re.compile(r"[^0-9a-z]+")


def normalise_movement_reference(value: str) -> str:
    """Return a provider-agnostic normalised form of a transaction narrative.

    OFX and CSV exports of the same bank movement describe it with
    different verbatim narratives (an OFX ``MEMO`` versus a CSV
    reference column), and a later manual edit may further reword the
    description. Cross-format and post-edit deduplication therefore
    cannot key on the raw narrative.

    This collapses a narrative to a stable comparison token: Unicode
    is NFKD-decomposed and combining accents are dropped (``Ó`` -> ``o``),
    the result is lower-cased, and every run of non-alphanumeric
    characters is squeezed out. Two narratives that differ only in
    accents, casing, punctuation, or whitespace map to the same token.
    """
    stripped = fold_diacritics(value)
    return _REFERENCE_NOISE.sub("", stripped.casefold())


def derive_import_fingerprint(
    raw: RawTransaction,
    *,
    direction: TransactionDirection | str | None = None,
    own_account_id: str | None = None,
) -> str:
    """Return the stable cross-format import-dedup fingerprint for a raw row.

    Unlike :func:`~.models.derive_transaction_id` — which keys on the provider
    identifier and the verbatim narrative and therefore changes when a
    transaction is edited or re-exported in a different file format —
    this fingerprint keys only on the *movement identity* an operator
    would recognise: the effective date, amount magnitude, currency,
    direction, and the normalised narrative (see
    :func:`normalise_movement_reference`).

    The fingerprint is stamped onto :class:`Transaction` at import time
    and carried verbatim through every later edit, so re-importing the
    same statement (or the same movements exported as a different file
    format) recognises the row as already present. Import callers that
    have parsed flow direction must pass it; callers without a parse-boundary
    direction receive an explicit ``UNSPECIFIED`` discriminator. A row bound to
    an own account folds that account in, so identical movements on two own
    accounts are not mistaken for a re-import; an unbound row's fingerprint is
    unchanged.
    """
    effective_value_date = raw.value_date or raw.booked_date
    if isinstance(direction, TransactionDirection):
        direction_value = direction.value
    elif direction is None:
        direction_value = "UNSPECIFIED"
    else:
        direction_value = direction
    payload: dict[str, str] = {
        "amount": canonical_decimal_string(raw.amount),
        "currency": raw.currency,
        "direction": direction_value,
        "reference": normalise_movement_reference(raw.description),
        "value_date": effective_value_date.isoformat(),
    }
    if own_account_id is not None:
        payload["own_account_id"] = own_account_id
    return content_hash_hex(payload)


def derive_movement_day_key(raw: RawTransaction) -> str:
    """Return the coarse (effective date, amount) key for a raw row.

    Two rows that share this key but not the full
    :func:`derive_import_fingerprint` are *likely* — but not
    confidently — the same movement: same day, same amount, divergent
    narrative. The import path uses this to warn the operator about a
    probable cross-format duplicate rather than silently importing it.
    """
    effective_value_date = raw.value_date or raw.booked_date
    return f"{effective_value_date.isoformat()}:{canonical_decimal_string(raw.amount)}"


def existing_transaction_import_fingerprints(transaction: Transaction) -> frozenset[str]:
    """Return every canonical re-import fingerprint for a stored transaction.

    Imported rows carry their parse-boundary, direction-qualified fingerprint
    verbatim. Older or hand-entered rows may not have that stamp, so their
    current raw payload is projected once with the stored direction as a
    deterministic fallback. Preview diagnostics and the persisting import path
    must use this exact projection: a directionless fallback would incorrectly
    collapse otherwise distinct incoming and outgoing movements.
    """
    fingerprints = {
        derive_import_fingerprint(
            transaction.raw,
            direction=transaction.direction,
            own_account_id=transaction.own_account_id,
        )
    }
    if transaction.import_fingerprint is not None and transaction.import_fingerprint:
        fingerprints.add(transaction.import_fingerprint)
    return frozenset(fingerprints)
