"""Typed id aliases for :class:`EvidenceBundle` records.

:data:`BundleId` and :data:`EvidenceId` pin the hex-64 sha-256 shape
minted by the evidence bundle pipeline. The aliases live in the
evidence application package because the bundle and per-record evidence
ids are minted in the application layer (no single domain owner).
"""

from __future__ import annotations

from ...core import Hex64Str

BundleId = Hex64Str
"""Hex-64 content-addressed evidence-bundle identity."""

EvidenceId = Hex64Str
"""Hex-64 content-addressed per-record evidence identity."""

__all__ = ("BundleId", "EvidenceId")
