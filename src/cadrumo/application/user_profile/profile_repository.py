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
    ProfileCustodyCapsuleLabel,
    ProfileCustodyPasswordMaterial,
    ProfileCustodyRecordError,
    ProfileLabelHead,
    ProfileLabelHeadRepository,
    list_current_profile_custody_capsule_ids,
    load_committed_profile_custody_label_record,
    load_committed_profile_password_material,
    recognize_current_profile_capsule,
)
from ...core.identity import ProfileId, ProfileLabel
from ...core.paths import effective_storage_root
from ...domain.user_profile.errors import ProfileNotFoundError
from .aggregate import CommittedProfileView, UnlockedProfileFactSummary
from .custody_repository import ProfileCustodyTransactionRepository, profile_custody_transaction_lock
from .custody_transactions import (
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionJournal,
    ProfileCustodyTransactionOperation,
)


def _require_initial_label_witness(
    profile_id: UUID,
    journal: ProfileCustodyTransactionJournal,
) -> None:
    checks = (
        (journal.operation is ProfileCustodyTransactionOperation.CREATE, "operation is not create"),
        (journal.profile_id == profile_id, "profile identity differs"),
        (journal.label_revision == 1, "label revision is not initial"),
        (journal.label_content_digest is not None, "label content digest is absent"),
        (journal.label_self_digest is not None, "label self digest is absent"),
    )
    for valid, reason in checks:
        if not valid:
            raise ProfileCustodyTransactionConflictError(
                f"committed capsule has no canonical initial label witness ({reason})"
            )


def _require_initial_label_match(
    label_record: ProfileCustodyCapsuleLabel,
    journal: ProfileCustodyTransactionJournal,
) -> None:
    if label_record.label_revision != 1:
        return
    if any(
        (
            label_record.content_digest != journal.label_content_digest,
            label_record.self_digest != journal.label_self_digest,
            label_record.label != journal.label,
        )
    ):
        raise ProfileCustodyTransactionConflictError("initial label differs from its create transaction witness")


def _verify_label_head(
    *,
    root: Path,
    label_record: ProfileCustodyCapsuleLabel,
    source_witness: str,
) -> ProfileLabelHead:
    try:
        return ProfileLabelHeadRepository(root=root).verify_or_recover_initial(
            label=label_record,
            source_witness=source_witness,
        )
    except ProfileCustodyRecordError as exc:
        raise ProfileCustodyTransactionConflictError(str(exc)) from exc


def _load_current_custody_state(
    *,
    root: Path,
    profile_id: UUID,
) -> tuple[ProfileCustodyPasswordMaterial, ProfileCustodyCapsuleLabel, ProfileLabelHead]:
    with profile_custody_transaction_lock(root, profile_id):
        material = load_committed_profile_password_material(profile_id, root=root)
        label_record = load_committed_profile_custody_label_record(profile_id, root=root)
        journal = ProfileCustodyTransactionRepository(root=root).load_journal(material.commit.transaction_id)
        _require_initial_label_witness(profile_id, journal)
        _require_initial_label_match(label_record, journal)
        head = _verify_label_head(root=root, label_record=label_record, source_witness=journal.self_digest)
    return material, label_record, head


def _published_at(material: ProfileCustodyPasswordMaterial) -> datetime:
    return datetime.fromisoformat(material.commit.published_at.replace("Z", "+00:00")).astimezone(UTC)


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

    def load_unlocked(self, profile_id: str | UUID) -> CommittedProfileView:
        """Project fact state and provenance only through the current authenticated session."""
        aggregate = self.load(profile_id)
        from .profile_record_repository import ProfileRecordRepository

        record = ProfileRecordRepository.for_current_session(aggregate.profile_id, root=self._root).load(
            aggregate.profile_id
        )
        return aggregate.model_copy(
            update={
                "fact_summary": UnlockedProfileFactSummary(
                    setup_state=record.setup_state,
                    fact_count=len(record.facts),
                    record_revision=record.record_revision,
                    content_digest=record.content_digest,
                )
            }
        )

    def _aggregate_for(self, profile_id: UUID, *, label_override: str | None = None) -> CommittedProfileView:
        if recognize_current_profile_capsule(profile_id, root=self._root) is None:
            raise ProfileNotFoundError("profile has no validated committed custody capsule")
        material, label_record, head = _load_current_custody_state(root=self._root, profile_id=profile_id)
        if label_override is not None and label_override != label_record.label:
            raise ProfileNotFoundError("profile label override differs from its authenticated provenance")
        return CommittedProfileView(
            profile_id=str(profile_id),
            label=label_record.label,
            committed_at=_published_at(material),
            publication_kind=material.commit.publication_kind,
            password_generation=material.envelope.password_generation,
            label_revision=head.label_revision,
            label_content_digest=head.label_content_digest,
            label_self_digest=head.label_self_digest,
            label_source_witness=head.self_digest,
        )


__all__ = ["CommittedProfileRepository", "ProfileSummary"]
