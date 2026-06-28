"""Typed id alias for :class:`Invoice` records.

:data:`InvoiceId` pins the hex-64 sha-256 shape
:func:`derive_invoice_id` mints for every persisted :class:`Invoice`.
The alias lives in the invoice domain package because the invoice domain
owns both the minting algorithm and the persisted-record shape; consumers
in :mod:`aeat.application.ledger` and the CLI payload surface import the
alias under its public name per ADR Rule 4.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

InvoiceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 content-addressed invoice identity. Minted via :func:`derive_invoice_id`."""

__all__ = ("InvoiceId",)
