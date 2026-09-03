"""Tracked material proving the custody absence scan reaches a sibling package.

This module exists only to be READ by the shared-master absence gate in the
application layer's own test package.  That gate's scope proof needs evidence
that its scan root recurses into sibling packages, and the evidence has to be
something that survives the cutover succeeding: anchoring it to the census of
live violations makes the proof collapse at exactly the moment the campaign
reaches its goal, and creates a standing reason to keep one violation alive.  A
tracked fixture does not expire.

It carries one reach of each shape the gate distinguishes -- a module path into
the shared-master package naming no retired symbol, and a retired provider name
reached as an attribute on the storage namespace, naming no module path -- so a
scan that reaches this file also demonstrates both nets firing on real tracked
source.  The provider reach is an attribute rather than an import on purpose:
the name no longer exists, so an import of it would be a false claim about the
tree and a genuine dangling edge for the import-edge integrity gate to report.

Nothing imports this module and nothing calls what it defines.  The reaches are
placed where they cannot execute, so the file is inert if it is ever imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....adapters.persistence.storage.master_key.bucket_session import BucketSession


def _never_called() -> object:
    """A retired provider name reached in the one form that stays true.

    The name is gone from the tree, so importing it states something false
    about the codebase: the statement could never execute, and the import-edge
    integrity gate reads it -- correctly -- as a consumer left pointing at
    nothing after a deletion landed without its sweep.  This file is not a
    consumer; nothing imports it and nothing calls this.  It is evidence.

    An attribute reach on the storage namespace says exactly what is meant, is
    one of the shapes the custody detector distinguishes in its own right, and
    remains an accurate reach after the symbol's removal rather than a broken
    one.  Both gates then read this file as what it is.
    """
    from ....adapters.persistence import storage

    return storage.get_master_key_provider  # ty: ignore[unresolved-attribute]  # reason: reaching a removed name IS the evidence this file exists to carry


def _annotated(session: BucketSession | None) -> object:
    return session
