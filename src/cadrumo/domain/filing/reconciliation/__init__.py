"""Cross-modelo reconciliation error facade for :mod:`domain.filing`.

This package owns the narrow exception vocabulary used when periodic filings,
annual summaries, or imported declaración evidence cannot be reconciled. The
public surface is deliberately small: :class:`ReconciliationError` is the family
base, :class:`ReconciliationDeclaracionParseError` wraps filed-declaration parse
failures at the reconciliation boundary, and :class:`ReconciliationDriftError`
signals arithmetic or identity drift across declarations.

Declaración parsing, justificante parsing, registry relation folding, and
application-level clean-state checks remain outside this package. Callers should
raise these errors only after those owner surfaces have supplied their typed
evidence.
"""

from .errors import (
    ReconciliationDeclaracionParseError,
    ReconciliationDriftError,
    ReconciliationError,
)

__all__ = [
    "ReconciliationDeclaracionParseError",
    "ReconciliationDriftError",
    "ReconciliationError",
]
