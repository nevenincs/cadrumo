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
imported from the storage facade naming no module path -- so a scan that reaches
this file also demonstrates both nets firing on real tracked source.

Nothing imports this module and nothing calls what it defines.  The reaches are
placed where they cannot execute, so the file is inert if it is ever imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....adapters.persistence.storage.master_key.bucket_session import BucketSession


def _never_called() -> object:
    from ....adapters.persistence.storage import get_master_key_provider

    return get_master_key_provider


def _annotated(session: BucketSession | None) -> object:
    return session
