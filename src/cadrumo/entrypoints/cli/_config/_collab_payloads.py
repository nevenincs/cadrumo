"""Typed ``--json`` payload schemas for the ``aeat config collab recipient`` CLI.

Each class declared here is a strict :class:`~core.json_contract.OutputSchema`
subclass and is referenced as a deferred public schema target by
production-authored CommandSpec so
the JSON-contract test suite can enumerate every collab-recipient command surface this
module covers. Field sets mirror :class:`~application.modelo.RecipientFingerprintRecord`
projected to plain JSON; the private key never appears anywhere in this module (the
registry stores only recipients' PUBLIC keys -- see
:mod:`~entrypoints.cli._config._collab`).

See Also:
    :class:`~application.modelo.RecipientFingerprintRecord`
        Application record shape these output rows project.
    :class:`~core.json_contract.OutputSchema`
        Base class for typed CLI JSON result payloads.
    CommandSpec schema target
        Deferred public target that owns each command envelope schema.
    :mod:`~entrypoints.cli._config._collab`
        Command handlers that emit these payloads.
    :func:`~entrypoints.cli._common.emit_envelope`
        CLI envelope renderer used after the payloads are populated.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import model_validator

from ....application.modelo._review_package_recipient_registry import RecipientFingerprintRecord
from ....core.json_contract import OutputSchema


class RecipientFingerprintRowPayload(OutputSchema):
    """One registered recipient row in the ``config collab recipient list`` surface."""

    recipient_id: str
    label: str
    public_key_hex: str
    fingerprint_sha256: str
    added_at: datetime

    @model_validator(mode="after")
    def _validate_recipient_record(self) -> RecipientFingerprintRowPayload:
        """Derive the displayed fingerprint from the same trusted key contract."""
        record = RecipientFingerprintRecord(
            recipient_id=self.recipient_id,
            label=self.label,
            public_key_hex=self.public_key_hex,
            added_at=self.added_at,
        )
        if self.fingerprint_sha256 != record.fingerprint_sha256:
            raise ValueError("fingerprint_sha256 must be derived from public_key_hex")
        return self


class ConfigCollabRecipientAddResult(RecipientFingerprintRowPayload):
    """JSON envelope for ``aeat config collab recipient add``."""


class ConfigCollabRecipientListResult(OutputSchema):
    """JSON envelope for ``aeat config collab recipient list``."""

    recipients: list[RecipientFingerprintRowPayload]
    count: int


class ConfigCollabRecipientRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config collab recipient remove``."""

    recipient_id: str
    remaining: int


__all__ = [
    "ConfigCollabRecipientAddResult",
    "ConfigCollabRecipientListResult",
    "ConfigCollabRecipientRemoveResult",
    "RecipientFingerprintRowPayload",
]
