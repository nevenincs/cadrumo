"""Errors for the tax-record retention-floor domain.

:class:`RetentionFloorError` is the refusal RESERVED for a destructive erase
that would destroy filed tax records still inside their legal retention window
(Ley 58/2003 art. 66/70; see
:data:`~domain.retention.TAX_RECORD_RETENTION_FLOOR_YEARS`).

No code raises it today, and that is a true statement about the tree rather
than an omission. The bucket erase it once guarded was withdrawn together with
the guard when the custody capsule became the sole profile authority: a
manifest-level surface cannot decrypt the profile record, so it cannot assess
retention, and :meth:`~application.bucket_maintenance.BucketMaintenanceService.assess_deletion`
now refuses every existing target outright rather than erasing one unassessed.
The class is kept because that refusal names the assessment as the missing
capability and a future destructive command is expected to bind it.

Read the tense above literally. This module previously described the erase and
its operator override in the present tense while neither was reachable, which
reads as a guard that has gone missing rather than one whose subject was
retired -- an expensive thing for the next reader to discover.
"""

from __future__ import annotations

from ...core.errors import CadrumoError


class RetentionError(CadrumoError):
    """Base error for the tax-record retention domain."""


class RetentionFloorError(RetentionError):
    """The refusal reserved for erasing a record inside its legal retention floor.

    The Administration's right to review a filed self-assessment prescribes
    four years after the voluntary filing deadline (LGT art. 66/67), and the
    supporting documentation must be conserved for that window (art. 70.2).
    Erasing such a record before the floor elapses destroys evidence the law
    requires kept, which is why a destructive erase must consult the floor and
    refuse -- or record an explicit operator override -- before proceeding.

    Not currently raised: see the module docstring for why the erase this
    guards is withdrawn rather than unguarded.
    """
