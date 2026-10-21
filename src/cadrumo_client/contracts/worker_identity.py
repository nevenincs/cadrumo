"""Neutral identity metadata for one privately contained background worker."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.hex import Hex64Str
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class ProfileWorkerIdentity(BaseModel):
    """Nonsecret routing metadata; native ownership and custody proof remain required."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    worker_id: UUID
    runtime_boot_id: UUID
    binding: ProfileAccessBinding

    @property
    def operation_owner_id(self) -> Hex64Str:
        """Name this worker's operation owner, never its lease token.

        The identity is only nonsecret routing metadata. Its boot coordinate
        binds it to one server process and does not grant authority.
        """
        return content_hash_hex(
            {
                "schema_version": 1,
                "authority": "cadrumo.runtime.worker.operation-owner",
                "worker": self.model_dump(mode="json"),
            }
        )
