"""Errors for the tax-record retention-floor domain.

:class:`RetentionFloorError` is the refusal a destructive erase raises when
one or more filed tax records are still inside their legal retention window
(Ley 58/2003 art. 66/70; see
:data:`~core.external_constants.TAX_RECORD_RETENTION_FLOOR_YEARS`).
"""

from __future__ import annotations

from ...core.errors import CadrumoError


class RetentionError(CadrumoError):
    """Base error for the tax-record retention domain."""


class RetentionFloorError(RetentionError):
    """Raised when erasing a record still within its legal retention floor.

    The Administration's right to review a filed self-assessment prescribes
    four years after the voluntary filing deadline (LGT art. 66/67), and the
    supporting documentation must be conserved for that window (art. 70.2).
    Erasing such a record before the floor elapses destroys evidence the law
    requires kept, so the erase is refused unless the operator supplies an
    explicit legal-retention override.
    """
