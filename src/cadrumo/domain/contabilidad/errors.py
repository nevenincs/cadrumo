"""Typed error classes for the contabilidad domain.

These guard-violation errors are raised by the pure trial-balance records. Each
inherits from both :class:`~cadrumo.core.errors.CadrumoError` (so the failure
reaches the typed error registry with a stable code and structured context) and
:exc:`ValueError` (so scalar validation and coercion failures retain the
standard Python error category).
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class SaldoCuentaBalanceError(CadrumoError, ValueError):
    """Raised when an account's balances and movements are inconsistent."""


class SumasYSaldosPreCloseError(CadrumoError, ValueError):
    """Raised when a trial balance was taken after the asiento de cierre.

    The Modelo 200 estados contables are transcribed from a pre-close trial
    balance. One taken after the close carries the period result on cuenta 129,
    and deriving the estados contables from it would double-count that result.
    """


class AjusteExtracontableShapeError(CadrumoError, ValueError):
    """Raised when a correction's fields contradict its permanente/temporaria class.

    A permanent correction has no pending balance — the AEAT Manual is explicit
    that the column cannot be filled — so carrying one is refused rather than
    coerced to zero.
    """
