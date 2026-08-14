"""The sole application writer for committed profile-capsule lifecycle actions."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID, uuid4

from ...core import BucketPointer
from ...domain.user_profile import UserProfileRecord
from ._aggregate import CommittedProfileView
from ._capsule_record import PROFILE_RECORD_DATA_FILENAME, ProfileRecordSession
from ._custody_ports import (
    ProfileCustodyEnvelopePort,
    ProfileCustodyRecoveryEnvelopePort,
    ProfileCustodySentinelPort,
)
from ._custody_service import ProfileCustodyTransactionService
from ._custody_transactions import (
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyTransactionJournal,
    ProfileCustodyTransactionReceipt,
)
from ._profile_pointer_transaction import active_profile_pointer_transaction
from ._profile_repository import CommittedProfileRepository


class ProfileCapsuleLifecycle:
    """Create, restore, select and delete through the custody transaction owner.

    The service never builds capsule paths, scans buckets, writes manifests, or
    handles KDF/recovery state.  Its only presentation write is the label
    projection, which is made visible exclusively after custody commit
    validation.
    """

    def __init__(self, *, root: Path | None = None) -> None:
        self._profiles = CommittedProfileRepository(root=root)
        self._transactions = ProfileCustodyTransactionService(root=self._profiles.root)

    @property
    def root(self) -> Path:
        return self._profiles.root

    def create(
        self,
        *,
        label: str,
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        data_files: Mapping[str, bytes],
        initial_record: UserProfileRecord,
        record_session: ProfileRecordSession,
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None = None,
        profile_id: UUID | None = None,
    ) -> CommittedProfileView:
        identity = profile_id or uuid4()
        if password_envelope.profile_id != identity or sentinel.profile_id != identity:
            raise ValueError("profile lifecycle create material must bind the lifecycle UUID")
        if record_session.profile_id != identity:
            raise ValueError("profile lifecycle record session must bind the lifecycle UUID")
        if PROFILE_RECORD_DATA_FILENAME in data_files:
            raise ValueError("profile lifecycle refuses caller-supplied profile record bytes")
        staged_record = record_session.create_initial(initial_record)
        self._transactions.create_capsule(
            profile_id=identity,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files={**data_files, PROFILE_RECORD_DATA_FILENAME: staged_record},
            label=label,
            recovery_envelope=recovery_envelope,
            publication_kind="enroll",
        )
        return self._profiles.load(identity)

    def restore(
        self,
        *,
        label: str,
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        data_files: Mapping[str, bytes],
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None = None,
    ) -> CommittedProfileView:
        identity = password_envelope.profile_id
        if sentinel.profile_id != identity:
            raise ValueError("profile lifecycle restore material must bind one UUID")
        self._transactions.create_capsule(
            profile_id=identity,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files=data_files,
            label=label,
            recovery_envelope=recovery_envelope,
            publication_kind="restore",
        )
        return self._profiles.load(identity)

    def select(self, value: str) -> CommittedProfileView:
        aggregate = self._profiles.resolve(value)
        with active_profile_pointer_transaction(self.root) as pointer:
            pointer.write(BucketPointer(bucket_id=aggregate.profile_id, schema_version=1))
        return aggregate

    def prepare_delete(self, *, profile_id: UUID) -> ProfileCustodyTransactionJournal:
        self._profiles.load(profile_id)
        return self._transactions.prepare_delete(profile_id=profile_id)

    def confirm_delete(self, journal: ProfileCustodyTransactionJournal) -> ProfileCustodyDeleteConfirmation:
        return self._transactions.confirmation_for(journal)

    def delete(self, confirmation: ProfileCustodyDeleteConfirmation) -> ProfileCustodyTransactionReceipt:
        return self._transactions.execute_delete(confirmation)

    def recover_create(self, transaction_id: UUID) -> ProfileCustodyTransactionReceipt | None:
        return self._transactions.recover_create(transaction_id)


__all__ = ["ProfileCapsuleLifecycle"]
