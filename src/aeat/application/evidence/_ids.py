"""Typed id aliases for :class:`EvidenceBundle` records.

:data:`BundleId` and :data:`EvidenceId` pin the hex-64 sha-256 shape
minted by the evidence bundle pipeline. The aliases live in the
evidence application package because the bundle and per-record evidence
ids are minted in the application layer (no single domain owner) per ADR
Rule 6 application-layer placement.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

BundleId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 content-addressed evidence-bundle identity."""

EvidenceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 content-addressed per-record evidence identity."""

__all__ = ("BundleId", "EvidenceId")
