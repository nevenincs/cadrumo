"""Typed error classes for the Impuesto sobre Sociedades compensación domain.

These guard-violation errors are raised by the pure base-imponible-negativa
carry-forward logic. Each inherits from both
:class:`~cadrumo.core.errors.CadrumoError` (so the failure reaches the typed
error registry with a stable code and structured context) and :exc:`ValueError`
(so scalar validation and coercion failures retain the standard Python error
category).
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class BinCarryForwardPolicyError(CadrumoError, ValueError):
    """Raised when a base-imponible-negativa stock violates carry-forward policy."""


class BinCohortShapeError(CadrumoError, ValueError):
    """Raised when a cohort's declared legs do not match its official shape.

    The Modelo 200 detalle cuadro gives every generation cohort three legs
    except the current-period one, which has no ``aplicado`` leg because LIS
    art. 26.1 only permits compensating losses ``procedentes de períodos
    anteriores``. Populating that leg is a legal impossibility, not an unusual
    value, so it is refused rather than coerced.
    """
