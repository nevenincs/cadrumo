"""Errors for the tax-record retention-floor domain.

:class:`RetentionFloorError` is the refusal RESERVED for a destructive erase
that would destroy filed tax records still inside their legal retention window
(Ley 58/2003 art. 66/70; see
:data:`~domain.retention.TAX_RECORD_RETENTION_FLOOR_YEARS`).

It IS raised: the configuration reset refuses at the point it would destroy a
bucket, when the target's recorded retention still blocks erasure and no
operator override was approved.

That refusal is a backstop rather than the first line. The reset normally
pauses earlier, before a blocked target reaches deletion, so no supported flow
arrives at this error. It is checked at the destructive point anyway, because a
guard living only in an earlier phase is one refactor away from being skipped
and the loss it would permit is unrecoverable.

The dormancy this module used to describe is over, and the reason it gave is
worth recording because it stopped being true without anyone noticing. It said
a manifest-level surface cannot decrypt the profile record and therefore cannot
assess retention, keeping the class only because "that refusal names the
assessment as the missing capability". The capability now exists, and the
precise claim matters because the loose version of it was wrong:
:meth:`~application.filing.FilingRetentionAuthority.assess` computes the
retained count, the floor and the safe-erase date from a plaintext filing
snapshot, so ASSESSING needs no session. Producing that snapshot still does --
it summarises the bucket's encrypted filing catalogue -- so the deferral was
right about the write side and wrong only about the read side. The snapshot
does not abolish the session requirement, it relocates it to the moment a
filing is recorded, which is the one moment a session is held by construction.

A deferral is a claim about the moment it was written, and this one outlived
its constraint long enough to be read as current more than once.
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

    Raised by the configuration reset immediately before it destroys a bucket;
    see the module docstring for why that placement is a backstop rather than
    the only check.
    """
