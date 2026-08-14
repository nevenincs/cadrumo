"""Domain-facing ports for profile lifecycle collaborators."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ProfileCustodyLabelAuthorityProtocol(Protocol):
    """Atomic label-provenance mutation required by profile lifecycle."""

    def rename_label(
        self,
        *,
        profile_id: UUID,
        label: str,
        expected_label_revision: int,
        expected_content_digest: str,
    ) -> None:
        """Publish a UUID-bound label after an exact compare-and-swap witness."""
        ...


__all__ = ["ProfileCustodyLabelAuthorityProtocol"]
