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


def later_absent_when_none(value: object) -> bool:
    """Leave out, while it holds nothing, an optional field added after builds stopped writing ``null``.

    Some builds wrote :func:`absent_when_none` fields as ``null``, and the
    snapshots they saved are bound by digests of that form, so a reader also
    tries it. A field those builds never had appears in none of their
    snapshots, so it stays out of that form too; it takes this exclusion
    instead of :func:`absent_when_none`.
    """
    return value is None


def later_absent_when_empty(value: object) -> bool:
    """Leave out, while it is empty, a collection field added after builds stopped writing ``null``.

    The collection counterpart of :func:`later_absent_when_none`: a snapshot saved
    before the field existed is bound by digests of dumps without it, and an
    empty collection says nothing the field's absence did not.
    """
    return not value


__all__ = ["absent_when_none", "later_absent_when_empty", "later_absent_when_none"]
