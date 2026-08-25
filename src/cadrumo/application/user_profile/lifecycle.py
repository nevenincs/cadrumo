"""The sole application writer for committed profile-capsule lifecycle actions."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from sqlite3 import DatabaseError
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError

from ...domain.user_profile.values import UserProfileRecord
from .aggregate import CommittedProfileView, ProfileRestoreAuthority
from .capsule_record import (
    ProfileRecordCommandEvent,
    ProfileRecordIntegrityError,
    ProfileRecordSession,
    ProfileRecordStore,
    stage_initial_profile_record_database,
    validate_staged_profile_record_database,
)
from .custody_hold_models import ProfileCustodyRetentionOverride
from .custody_ports import (
    ProfileCustodyEnvelopePort,
    ProfileCustodyRecoveryEnvelopePort,
    ProfileCustodySentinelPort,
    verify_profile_custody_dek_against_sentinel,
)
from .custody_repository import profile_custody_transaction_lock
from .custody_service import _ProfileCustodyTransactionCapability
from .custody_transactions import (
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyTransactionJournal,
    ProfileCustodyTransactionReceipt,
)
from .profile_pointer import active_profile_pointer_transaction
from .profile_repository import CommittedProfileRepository


class ProfileCapsuleLifecycle:
    """Create, restore, select and delete through the custody transaction owner.

    The service never builds capsule paths, scans buckets, writes manifests, or
    handles KDF/recovery state.  Its only presentation write is the label
    projection, which is made visible exclusively after custody commit
    validation.
    """

    def __init__(self, *, root: Path | None = None) -> None:
        """Initialize lifecycle actions rooted at the optional storage path."""
        self._profiles = CommittedProfileRepository(root=root)
        self._transactions = _ProfileCustodyTransactionCapability(root=self._profiles.root)

    @property
    def root(self) -> Path:
        """Return the committed profile storage root."""
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
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort,
        profile_id: UUID | None = None,
    ) -> CommittedProfileView:
        """Create and publish a new profile capsule."""
        identity = profile_id or uuid4()
        if recovery_envelope is None:
            raise ValueError("profile lifecycle create requires creation recovery material")
        if password_envelope.profile_id != identity or sentinel.profile_id != identity:
            raise ValueError("profile lifecycle create material must bind the lifecycle UUID")
        if record_session.profile_id != identity:
            raise ValueError("profile lifecycle record session must bind the lifecycle UUID")
        record_session.assert_initial_record(initial_record)
        self._transactions.create_capsule(
            profile_id=identity,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files=data_files,
            label=label,
            recovery_envelope=recovery_envelope,
            publication_kind="enroll",
            stage_initializer=lambda stage_path: stage_initial_profile_record_database(
                stage_path=stage_path,
                root=self.root,
                session=record_session,
                record=initial_record,
            ),
        )
        return self._profiles.load(identity)

    def restore(
        self,
        *,
        label: str,
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        data_files: Mapping[str, bytes],
        record_session: ProfileRecordSession,
        database_bytes: bytes,
        authority: ProfileRestoreAuthority,
    ) -> CommittedProfileView:
        """Publish one restored capsule under a named, proven restore authority.

        ``authority`` records which door proved the key: the profile's own
        password, or a portable recovery artifact. It is required and has no
        default, because the two are not interchangeable and a restore that
        does not say which one it used cannot be audited afterwards. Both
        doors prove the DEK before reaching here; neither mints, rotates, or
        replaces a key schedule, so a recovery-proved restore republishes the
        SAME password envelope and does not hand back password access.

        The material agreement below is checked at the primitive rather than
        trusted from the door, and the reason is asymmetric cost. Publishing
        a capsule whose password envelope unwraps a key the staged database
        was not encrypted under produces a profile that authenticates and
        then decrypts nothing -- and it does so silently, at the one moment
        the operator believes their records were rescued. Proving the
        session's key against the committed sentinel is cheap; the failure it
        prevents is unrecoverable.
        """
        identity = password_envelope.profile_id
        if sentinel.profile_id != identity:
            raise ValueError("profile lifecycle restore material must bind one UUID")
        if record_session.profile_id != identity:
            raise ValueError("profile lifecycle restore session must bind the capsule UUID")
        if record_session.envelope_digest != password_envelope.self_digest:
            raise ValueError("profile lifecycle restore session was not minted from this password envelope")
        if record_session.dek_epoch != password_envelope.dek_epoch:
            raise ValueError("profile lifecycle restore session DEK epoch differs from its password envelope")
        if data_files:
            raise ValueError("profile lifecycle restore refuses arbitrary capsule data files")
        if not database_bytes:
            raise ValueError("profile lifecycle restore requires its canonical profile database")
        verify_profile_custody_dek_against_sentinel(
            dek=record_session.encryption_key(),
            profile_id=identity,
            dek_epoch=password_envelope.dek_epoch,
            sentinel=sentinel,
        )
        self._transactions.create_capsule(
            profile_id=identity,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files=data_files,
            label=label,
            recovery_envelope=None,
            publication_kind="restore",
            stage_initializer=lambda stage_path: self._stage_and_validate_restore_database(
                stage_path=stage_path,
                record_session=record_session,
                database_bytes=database_bytes,
            ),
        )
        return self._profiles.load(identity)

    def _replace_record_for_profile_command(
        self,
        *,
        profile_id: UUID,
        record_session: ProfileRecordSession,
        replacement: UserProfileRecord,
        event: ProfileRecordCommandEvent,
        expected_revision: int,
        expected_content_digest: str,
    ) -> UserProfileRecord:
        """Private CAS collaboration for explicit ``ProfileRecordRepository`` commands."""
        if record_session.profile_id != profile_id:
            raise ValueError("profile lifecycle record session must bind the replacement UUID")
        with profile_custody_transaction_lock(self.root, profile_id):
            return ProfileRecordStore(session=record_session, root=self.root).replace(
                replacement=replacement,
                event=event,
                expected_revision=expected_revision,
                expected_content_digest=expected_content_digest,
            )

    def _stage_and_validate_restore_database(
        self,
        *,
        stage_path: Path,
        record_session: ProfileRecordSession,
        database_bytes: bytes,
    ) -> None:
        """Stage a supplied canonical DB and authenticate it before publication."""
        database = stage_path / "db" / "cadrumo.db"
        database.parent.mkdir(mode=0o700, exist_ok=False)
        database.write_bytes(database_bytes)
        (stage_path / "blobs").mkdir(mode=0o700, exist_ok=False)
        try:
            validate_staged_profile_record_database(
                stage_path=stage_path,
                root=self.root,
                session=record_session,
            )
        except (DatabaseError, OSError, SQLAlchemyError, ValueError) as exc:
            raise ProfileRecordIntegrityError(
                "profile lifecycle restore database fails authenticated current-record validation"
            ) from exc

    def select(self, value: str) -> CommittedProfileView:
        """Select an existing profile as active."""
        aggregate = self._profiles.resolve(value)
        with active_profile_pointer_transaction(self.root) as pointer:
            pointer.select(aggregate.profile_id)
        return aggregate

    def prepare_delete(
        self,
        *,
        profile_id: UUID,
        retention_override: ProfileCustodyRetentionOverride | None = None,
        requires_inactive_target: bool = False,
    ) -> ProfileCustodyTransactionJournal:
        """Prepare one local deletion, carrying any operator retention authorisation.

        The override is forwarded rather than interpreted here: the custody
        capability owns the hold decision, and a second opinion at this layer
        would be a place for the two to disagree.
        """
        self._profiles.load(profile_id)
        return self._transactions.prepare_delete(
            profile_id=profile_id,
            retention_override=retention_override,
            requires_inactive_target=requires_inactive_target,
        )

    def confirm_delete(self, journal: ProfileCustodyTransactionJournal) -> ProfileCustodyDeleteConfirmation:
        """Bind a deletion confirmation to a prepared journal."""
        return self._transactions.confirmation_for(journal)

    def delete(self, confirmation: ProfileCustodyDeleteConfirmation) -> ProfileCustodyTransactionReceipt:
        """Execute a confirmed profile deletion."""
        return self._transactions.execute_delete(confirmation)

    def recover_create(self, transaction_id: UUID) -> ProfileCustodyTransactionReceipt | None:
        """Recover a previously interrupted profile creation."""
        return self._transactions.recover_create(transaction_id)


__all__ = ["ProfileCapsuleLifecycle"]
