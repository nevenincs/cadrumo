"""Inert namespace for cross-modelo reconciliation errors.

This package owns the narrow exception vocabulary used when periodic filings,
annual summaries, or imported declaración evidence cannot be reconciled. The
``errors`` defines :class:`ReconciliationError`, the family
base, :class:`ReconciliationDeclaracionParseError` wraps filed-declaration parse
failures at the reconciliation boundary, and :class:`ReconciliationDriftError`
signals arithmetic or identity drift across declarations.

Declaración parsing, justificante parsing, registry relation folding, and
application-level clean-state checks remain outside this package. Callers should
raise these errors only after those owner surfaces have supplied their typed
evidence.

The package initializer exports no symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
