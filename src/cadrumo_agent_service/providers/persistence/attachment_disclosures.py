"""Remembered attachment grants and the release ledger, in the runtime's encrypted custody."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Final, override

from pydantic import BaseModel, ConfigDict, ValidationError

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.service_client import InstalledServiceClient

from ..application.attachment_releases import (
    DisclosureGrant,
    DisclosureRecord,
    DisclosureStore,
    ReleaseAction,
    StoredGrants,
)

ATTACHMENT_GRANTS_CAPABILITY: Final = "attachment-disclosure-grants"
ATTACHMENT_GRANTS_KEY: Final = "remembered"
ATTACHMENT_LEDGER_CAPABILITY: Final = "attachment-release-ledger"


class _GrantDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    grant_id: str
    action: ReleaseAction
    lane: str
    model: str
    sha256: str | None
    conversation_id: str | None
    display_name: str | None


class _GrantsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    grants: tuple[_GrantDocument, ...]


class SecureAttachmentDisclosureStore(DisclosureStore):
    """Use only the two descriptor capabilities; an answer outside the contract grants nothing."""

    def __init__(self, *, client: InstalledServiceClient) -> None:
        """Bind the store to one runtime-issued service lease."""
        self._client = client

    @override
    def read_grants(self) -> StoredGrants | None:
        """Return the remembered grants; an unreadable record is no grants anyone can rely on."""
        try:
            reply, material = self._client.record_read(ATTACHMENT_GRANTS_CAPABILITY, ATTACHMENT_GRANTS_KEY)
        except (RefusalError, FrontendRefusedError, OSError):
            return None
        try:
            if reply.state == "absent":
                return StoredGrants(grants=(), revision=ABSENT_SECURE_OBJECT_REVISION_ID)
            if reply.state != "present" or reply.revision is None:
                return None
            document = _GrantsDocument.model_validate_json(bytes(material))
        except ValidationError:
            return None
        finally:
            material[:] = b"\0" * len(material)
        return StoredGrants(
            grants=tuple(DisclosureGrant(**held.model_dump()) for held in document.grants),
            revision=reply.revision,
        )

    @override
    def write_grants(self, grants: tuple[DisclosureGrant, ...], *, expected_revision: str) -> bool:
        """Commit the whole list at the revision read."""
        body = {"version": 1, "grants": [asdict(grant) for grant in grants]}
        return self._write(ATTACHMENT_GRANTS_CAPABILITY, ATTACHMENT_GRANTS_KEY, body, expected_revision)

    @override
    def append_release(self, record: DisclosureRecord) -> bool:
        """Add one record under a key of its own; an existing key is refused, never replaced."""
        return self._write(
            ATTACHMENT_LEDGER_CAPABILITY,
            f"release-{record.record_id}",
            {"version": 1, **asdict(record)},
            ABSENT_SECURE_OBJECT_REVISION_ID,
        )

    def _write(self, capability: str, key: str, body: dict[str, object], expected_revision: str) -> bool:
        material = bytearray(json.dumps(body, separators=(",", ":")).encode("utf-8"))
        try:
            reply = self._client.record_write(capability, key, payload=material, expected_revision=expected_revision)
        except (RefusalError, FrontendRefusedError, OSError):
            return False
        finally:
            material[:] = b"\0" * len(material)
        return reply.state == "written"


__all__ = [
    "ATTACHMENT_GRANTS_CAPABILITY",
    "ATTACHMENT_GRANTS_KEY",
    "ATTACHMENT_LEDGER_CAPABILITY",
    "SecureAttachmentDisclosureStore",
]
