"""Why a profile custody capsule was published.

One vocabulary, previously written out at ten annotation sites across seven modules in
two layers: the custody capsule records and their writers, the profile aggregate and
summary views, and the custody service and ports between them. They agreed only
because nobody had changed one of them.

The custody adapters and the profile application code both reach ``core``, so the
definition lives here rather than in either of them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

__all__ = ["ProfilePublicationKind", "ProfilePublicationKindValue"]


class ProfilePublicationKind(StrEnum):
    """Which act published this generation of a profile's custody capsule."""

    ENROLL = "enroll"
    """First publication, establishing custody for a profile that had none.

    An enrolment is the only publication that may mint a recovery envelope, because
    it is the only one where no earlier envelope exists to republish.
    """

    RESTORE = "restore"
    """Republication of custody for a profile that already had it.

    A restore says the capsule was re-established, and deliberately not what
    authorised it -- that is a separate axis, and the two must not be merged.
    """


ProfilePublicationKindValue = Literal[
    ProfilePublicationKind.ENROLL,
    ProfilePublicationKind.RESTORE,
]
"""The same vocabulary for a strict model field or a boundary parameter.

A bare enum under strict validation refuses the plain token a serialised capsule
record carries, so those fields take this literal over the members above rather than
restating the pair.
"""
