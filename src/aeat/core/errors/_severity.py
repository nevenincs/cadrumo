"""Shared severity primitive for diagnostics, findings, and validation issues.

A single ``BaseSeverity`` enum carries the INFO < WARNING < ERROR
contract for every diagnostic, finding, and validation issue in the
project. Call sites import this type directly; semantic context lives
in the field name (``diagnostic_severity``, ``finding_severity``,
``validation_severity``), not in duplicate type names.

The string values are lowercase (``"info"``, ``"warning"``,
``"error"``) to match the on-disk JSON convention used by the
ledger-import diagnostic fixtures; the member names stay uppercase
to follow the standard enum-member convention.
"""

from __future__ import annotations

from enum import StrEnum


class BaseSeverity(StrEnum):
    """Shared severity primitive: INFO < WARNING < ERROR."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


__all__ = ["BaseSeverity"]
