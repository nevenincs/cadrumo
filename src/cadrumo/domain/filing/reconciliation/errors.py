"""Narrow exceptions for the cross-modelo reconciliation domain.

Justificante parse failures are surfaced via
:class:`domain.justificante.JustificanteParseError`; this module
defines reconciliation-specific failures only.
"""

from __future__ import annotations

from ....core.errors import CadrumoError


class ReconciliationError(CadrumoError):
    """Base error for reconciliation between periodic filings and annual summaries."""


class ReconciliationDeclaracionParseError(ReconciliationError):
    """Raised when a filed declaration export cannot be parsed for reconciliation."""


class ReconciliationDriftError(ReconciliationError):
    """Raised when reconciliation detects arithmetic or identity drift across declarations."""
