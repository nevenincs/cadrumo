"""The one rule for deriving a live capture's snapshot identity.

A capture's snapshot id is the digest of its canonical JSON, so two captures
carrying the same facts get the same id and a changed fact gets a new one. Two
capture modules each stated that rule for their own type; stated twice, a change
to what "canonical" means would have had to be made twice to keep ids stable.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core.hashing import sha256_hex

__all__ = ["derive_snapshot_id"]


def derive_snapshot_id(capture: BaseModel) -> str:
    """Return the snapshot identity of ``capture`` as the digest of its canonical JSON.

    Typed on the model base rather than on each capture, because the rule is
    about the serialisation and not about which capture is being serialised.
    """
    return sha256_hex(capture.model_dump_json())
