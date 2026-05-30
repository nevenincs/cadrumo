"""Typed-id alias for attachment domain records.

`AttachmentId` pins the hex-64 sha-256 shape persisted by the
attachment catalogue. The alias lives in the attachment domain package
because the attachment domain owns both the catalogue-key shape and
the persisted-record contract; consumers in `application.evidence` and
`application.ledger` import the alias under its public name per
ADR Rule 4.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

AttachmentId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 content-addressed attachment identity."""

__all__ = ("AttachmentId",)
