"""Typed ``--json`` payload schema for ``aeat config profile complete-setup``.

Referenced as a deferred public schema target by production-authored CommandSpec
so the JSON-contract gate enumerates the surface without import-time registration.

The payload reports the promotion, never the facts: what an operator needs from
this verb is whether the profile now carries the readiness CLAIM, and which
record revision carries it, so a later reader can tell a fresh promotion from an
idempotent no-op.
"""

from __future__ import annotations

from ....core.identity import ProfileId
from ....core.json_contract import OutputSchema


class ProfileCompleteSetupResult(OutputSchema):
    """JSON envelope for ``aeat config profile complete-setup``.

    ``setup_state`` is the state AFTER the call, so a success always reads
    ``complete``. ``already_complete`` marks the idempotent no-op: the record was
    already promoted, nothing was written, and ``record_revision`` is the
    revision the earlier promotion produced rather than a new one.

    ``missing_required_paths`` stays empty on success. It carries content only on
    the refusal path, where it names the profile paths that still have to be
    answered -- a bare "incomplete" would leave the operator with nowhere to go,
    and this verb's whole purpose is to be the door that says what is missing.
    """

    profile_id: ProfileId
    setup_state: str
    record_revision: int
    already_complete: bool = False
    missing_required_paths: list[str] = []
