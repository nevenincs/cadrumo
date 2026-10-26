"""Canonical ledger transaction identities and operator references."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..hex import Hex64Str

__all__ = ["TransactionId", "TransactionIdReference"]


type TransactionId = Hex64Str
"""Hex-64 content-addressed ledger-transaction identity."""

TransactionIdReference = Annotated[str, Field(min_length=1, max_length=64)]
"""Operator-entered full transaction id or prefix resolved by the ledger."""
