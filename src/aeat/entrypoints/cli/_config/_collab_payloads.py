"""Typed ``--json`` payload schemas for the ``aeat config collab recipient`` CLI.

Each class declared here is a strict :class:`~entrypoints.cli._schemas.OutputSchema`
subclass and is decorated with :func:`~entrypoints.cli._schemas.register_schema` so
the JSON-contract test suite can enumerate every collab-recipient command surface this
module covers. Field sets mirror :class:`~application.modelo.RecipientFingerprintRecord`
projected to plain JSON; the private key never appears anywhere in this module (the
registry stores only recipients' PUBLIC keys -- see
:mod:`~entrypoints.cli._config._collab`).
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


class RecipientFingerprintRowPayload(OutputSchema):
    """One registered recipient row in the ``config collab recipient list`` surface."""

    recipient_id: str
    label: str
    public_key_hex: str
    fingerprint_sha256: str
    added_at: str


@register_schema("config.collab.recipient.add")
class ConfigCollabRecipientAddResult(OutputSchema):
    """JSON envelope for ``aeat config collab recipient add``."""

    recipient_id: str
    label: str
    public_key_hex: str
    fingerprint_sha256: str
    added_at: str


@register_schema("config.collab.recipient.list")
class ConfigCollabRecipientListResult(OutputSchema):
    """JSON envelope for ``aeat config collab recipient list``."""

    recipients: list[RecipientFingerprintRowPayload]
    count: int


@register_schema("config.collab.recipient.remove")
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
