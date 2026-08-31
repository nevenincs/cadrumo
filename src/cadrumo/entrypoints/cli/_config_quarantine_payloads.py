"""Private JSON payload rows for config repair quarantine."""

from __future__ import annotations

from ...core.json_contract import OutputSchema


class QuarantineNamespacePayload(OutputSchema):
    """One secure-object namespace row in a repair quarantine report.

    Projects the per-namespace counts carried by `SecureObjectIntegrityReport`
    and its secure-object integrity rows without exposing object keys,
    ciphertext, plaintext payload bytes, taxpayer identifiers, or bucket IDs.
    """

    namespace: str
    readable: int
    unreadable: int
