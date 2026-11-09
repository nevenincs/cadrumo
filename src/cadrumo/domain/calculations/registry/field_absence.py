"""The one exclusion an optional registry field added after snapshots were saved takes.

A calculation revision saves its registry snapshot and binds it by digests of
that snapshot's dumps. A field added to a registry model later reads as ``None``
from every snapshot saved before it existed; dumped as ``null`` it would change
both digests and make every earlier revision unreadable. Such a field is left out
of each dump while it holds nothing, in the default dump and in the complete one
that otherwise keeps every declared field, so an earlier snapshot dumps exactly
as it was saved and a later one says only what it declares.
"""

from __future__ import annotations


def absent_when_none(value: object) -> bool:
    """Leave an optional registry field out of a dump while it holds nothing."""
    return value is None


__all__ = ["absent_when_none"]
