"""Committed-capsule profile projection repository.

This repository owns only mutable presentation labels.  UUID discovery and all
custody facts are delegated to the current-format capsule adapter; a label
record without a valid committed capsule is intentionally invisible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...adapters.persistence.storage.custody import (
    list_current_profile_custody_capsule_ids,
    load_committed_profile_custody_label,
    load_committed_profile_password_material,
)
from ...core.identity import ProfileId, ProfileLabel
from ...core.paths import effective_storage_root
from ...domain.user_profile import ProfileNotFoundError
from ._aggregate import CommittedProfileView


class ProfileSummary(BaseModel):
    """Listing projection with no key, KDF, manifest, or recovery material."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    profile_id: ProfileId
    label: ProfileLabel


class CommittedProfileRepository:
    """Resolve labels and UUIDs only for validated committed capsules."""

    def __init__(self, *, root: Path | None = None) -> None:
        self._root = effective_storage_root(root)

    @property
    def root(self) -> Path:
        return self._root

    def load(self, profile_id: str | UUID) -> CommittedProfileView:
        try:
            identity = UUID(str(profile_id))
        except ValueError as exc:
            raise ProfileNotFoundError("profile identity is not a canonical UUID") from exc
        return self._aggregate_for(identity)

    def resolve(self, value: str) -> CommittedProfileView:
        """Resolve an exact UUID or exact label without scanning retired buckets."""
        try:
            return self.load(value)
        except ProfileNotFoundError:
            pass
        matches = [aggregate for aggregate in self.list() if aggregate.label == value]
        if len(matches) != 1:
            raise ProfileNotFoundError("profile label does not resolve to one committed capsule")
        return matches[0]

    def list(self) -> tuple[CommittedProfileView, ...]:
        """Project only current capsules recognized by the custody adapter."""
        result: list[CommittedProfileView] = []
        for profile_id in list_current_profile_custody_capsule_ids(root=self._root):
            try:
                result.append(self._aggregate_for(profile_id))
            except ProfileNotFoundError:
                continue
        return tuple(sorted(result, key=lambda item: item.profile_id))

    def summaries(self) -> tuple[ProfileSummary, ...]:
        return tuple(ProfileSummary(profile_id=item.profile_id, label=item.label) for item in self.list())

    def _aggregate_for(self, profile_id: UUID, *, label_override: str | None = None) -> CommittedProfileView:
        try:
            material = load_committed_profile_password_material(profile_id, root=self._root)
        except Exception as exc:
            raise ProfileNotFoundError("profile has no validated committed custody capsule") from exc
        label = (
            label_override
            if label_override is not None
            else load_committed_profile_custody_label(profile_id, root=self._root)
        )
        published_at = datetime.fromisoformat(material.commit.published_at.replace("Z", "+00:00")).astimezone(UTC)
        return CommittedProfileView(
            profile_id=str(profile_id),
            label=label,
            committed_at=published_at,
            publication_kind=material.commit.publication_kind,
            password_generation=material.envelope.password_generation,
        )


__all__ = ["CommittedProfileRepository", "ProfileNotFoundError", "ProfileSummary"]
