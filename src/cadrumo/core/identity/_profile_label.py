"""Operator-facing profile label shared by the manifest and the pointer.

A profile carries two identities: the immutable :data:`BucketId` UUID the
storage layer addresses it by, and the label the operator chose and is the
only one they ever see. The label crosses the same boundary twice -- it is
persisted on the bucket manifest and projected onto the profile-bucket
pointer that operator surfaces enumerate -- so both sides must agree on what
a valid label is.

They did not. The pointer required a trimmed 1..160 label while the manifest
accepted an unconstrained string, so a manifest written with an empty or
overlong label persisted happily and then raised an uncaught validation error
at enumeration time, with the scan-issue surface reporting nothing. Declaring
the constraint once and consuming it on both sides makes the manifest refuse
the value at the write boundary, and turns an already-malformed manifest on
disk into a reported scan issue rather than a crash.

See Also:
    :data:`~core.identity.BucketId`
        The immutable machine identity this label accompanies.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ProfileLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
"""Operator-chosen display name for one profile bucket."""

__all__ = ("ProfileLabel",)
