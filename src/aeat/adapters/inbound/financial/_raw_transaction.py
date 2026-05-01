"""Inbound re-export of the raw transaction record types.

This module re-exports the canonical raw-transaction record types defined in
:mod:`aeat.domain.transactions._raw_transaction` so that providers in
:mod:`aeat.adapters.inbound.financial.providers` can import them through the
financial-adapter namespace without coupling directly to the domain layout.

See Also:
    :class:`aeat.domain.transactions._raw_transaction.RawTransaction`
"""

from ....domain.transactions._raw_transaction import RawProvenance, RawTransaction, SourceFormat

__all__ = ["RawProvenance", "RawTransaction", "SourceFormat"]
