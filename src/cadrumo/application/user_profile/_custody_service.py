"""Application service for current-format profile custody transactions."""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from ...adapters.persistence.storage import custody
from ...core import BucketPointer
from ...core.paths import effective_storage_root
from ._custody_hold import ProfileCustodyHoldAuthority
from ._custody_pointer import ProfileCustodyPointerSnapshot
from ._custody_ports import (
    ProfileCustodyEnvelopePort,
    ProfileCustodyRecoveryEnvelopePort,
    ProfileCustodySentinelPort,
)
from ._custody_repository import (
    ProfileCustodyTransactionRepository,
    compare_and_swap_profile_pointer,
    profile_custody_transaction_lock,
)
from ._custody_transactions import (
    CUSTODY_RECEIPT_SCHEMA_VERSION,
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyInventoryWitness,
    ProfileCustodyOwnerReceipt,
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionCorruptError,
    ProfileCustodyTransactionJournal,
    ProfileCustodyTransactionOperation,
    ProfileCustodyTransactionReceipt,
    ProfileCustodyTransactionRefusalError,
    ProfileCustodyTransactionState,
)
from ._login_session import (
    remove_profile_session_acceleration_for_custody_delete,
    revoke_live_profile_secret_for_custody_delete,
)


class ProfileCustodyDisplacedSessionRetirementError(ProfileCustodyTransactionConflictError):
    """The create transaction could not void the session of the profile it displaces.

    Distinct from the generic transaction conflict for one reason that is
    operator-facing rather than structural: creation refuses on this and on a
    label or UUID collision alike, and the collision message -- the profile
    already exists -- is a false account of this one.  The operator's own
    credentials and label are fine; a prior profile's session artefact could not
    be removed, so the creation door needs a refusal that says that.

    It subclasses the conflict deliberately.  Every existing handler treats a
    create conflict as a refusal that leaves the pointer where it was, and that
    is exactly the disposition wanted here; narrowing the message must not
    narrow which handlers catch it.

    Its registry entry is declared retryable, which is a considered value rather
    than an oversight to correct: the underlying removal fails when something
    else holds the receipt open -- another reader, a backup agent, a scanner --
    which clears on its own, so a second attempt is the right advice to give.
    """


class _ProfileCustodyTransactionCapability:
    """Internal physical-custody capability owned by ``ProfileCapsuleLifecycle``.

    No application caller may use this capability directly.  The lifecycle is
    the only collaboration boundary entitled to prepare, publish, recover, or
    remove a current capsule; keeping the transaction mechanics here prevents
    a second public writer from materialising beside that boundary.
    """

    def __init__(self, *, root: Path | None = None, adapters: Any | None = None) -> None:
        self._root = effective_storage_root(root)
        self._adapters: Any = adapters if adapters is not None else custody
        self._repository = ProfileCustodyTransactionRepository(root=self._root)
        self._holds = ProfileCustodyHoldAuthority(root=self._root)

    def prepare_delete(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID | None = None,
        now: datetime | None = None,
    ) -> ProfileCustodyTransactionJournal:
        """Record all local preflight evidence before any destructive action.

        The hold assessment, exact inventory, pointer snapshot, and confirmation
        challenge are written into one journal before the deletion marker exists.
        A later executor therefore either has the complete authorization record
        or cannot begin the destructive sequence.
        """
        transaction = transaction_id or uuid4()
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        with profile_custody_transaction_lock(self._root, profile_id):
            hold_assessment = self._holds.assess(profile_id, now=instant)
            if not hold_assessment.permits_local_deletion:
                raise ProfileCustodyTransactionRefusalError("a legal or filing hold blocks local profile deletion")
            inventory = self._adapters.inventory_committed_profile_custody_capsule(profile_id, root=self._root)
            journal = ProfileCustodyTransactionJournal.create(
                transaction_id=transaction,
                operation=ProfileCustodyTransactionOperation.DELETE,
                profile_id=profile_id,
                state=ProfileCustodyTransactionState.DELETE_PREPARED,
                started_at=instant,
                updated_at=instant,
                pointer_before=ProfileCustodyPointerSnapshot.capture(self._root),
                expected_custody_digest=inventory.digest,
                inventory=ProfileCustodyInventoryWitness.from_inventory(inventory),
                hold_assessment=hold_assessment,
                confirmation_challenge=secrets.token_hex(32),
            )
            self._repository.create_journal(journal)
            return journal

    def create_capsule(
        self,
        *,
        profile_id: UUID,
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        data_files: Mapping[str, bytes],
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None = None,
        label: str,
        publication_kind: Literal["enroll", "restore"] = "enroll",
        stage_initializer: Callable[[Path], None] | None = None,
        transaction_id: UUID | None = None,
        now: datetime | None = None,
    ) -> ProfileCustodyTransactionReceipt:
        """Journal, stage, verify, publish, then point at one new custody capsule.

        The stage is inventory-bound before publication, and the pointer changes
        only after the committed capsule is visible.  Every intermediate state
        is durable so recovery can resume at the last verified boundary.
        """
        if password_envelope.profile_id != profile_id or sentinel.profile_id != profile_id:
            raise ProfileCustodyTransactionRefusalError("create custody material does not bind its target profile")
        try:
            label_record = self._adapters.ProfileCustodyCapsuleLabel.create(
                profile_id=profile_id,
                label=label,
            )
            canonical_label = label_record.label
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyTransactionRefusalError("profile capsule label is invalid") from exc
        transaction = transaction_id or uuid4()
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        staged_relative_path = self._adapters.profile_custody_staging_path(
            profile_id=profile_id,
            transaction_id=transaction,
            root=self._root,
        ).name
        with profile_custody_transaction_lock(self._root, profile_id):
            self._refuse_duplicate_label_under_root_lock(profile_id=profile_id, label=canonical_label)
            journal = ProfileCustodyTransactionJournal.create(
                transaction_id=transaction,
                operation=ProfileCustodyTransactionOperation.CREATE,
                profile_id=profile_id,
                state=ProfileCustodyTransactionState.PREPARED,
                started_at=instant,
                updated_at=instant,
                pointer_before=ProfileCustodyPointerSnapshot.capture(self._root),
                proposed_generation=password_envelope.password_generation,
                label=canonical_label,
                label_revision=label_record.label_revision,
                label_content_digest=label_record.content_digest,
                label_self_digest=label_record.self_digest,
                staged_relative_path=staged_relative_path,
            )
            self._repository.create_journal(journal)
            self._adapters.publish_profile_custody_capsule(
                profile_id=profile_id,
                transaction_id=transaction,
                publication_kind=publication_kind,
                password_envelope=cast(Any, password_envelope),
                sentinel=cast(Any, sentinel),
                data_files={
                    **data_files,
                    self._adapters.PROFILE_CUSTODY_LABEL_FILENAME: label_record.canonical_json_bytes(),
                },
                recovery_envelope=cast(Any, recovery_envelope),
                root=self._root,
                published_at=instant,
                stage_only=True,
                stage_initializer=stage_initializer,
            )
            inventory = ProfileCustodyInventoryWitness.from_inventory(
                self._adapters.inventory_staged_profile_custody_capsule(
                    profile_id=profile_id, transaction_id=transaction, root=self._root
                )
            )
            verified = journal.with_update(
                state=ProfileCustodyTransactionState.STAGE_VERIFIED,
                proposed_custody_digest=inventory.digest,
                updated_at=instant,
            )
            self._repository.save_journal(verified)
            pointed = self._publish_verified_create(verified, instant)
            return self._finish_create_recovery(pointed, instant)

    def _refuse_duplicate_label_under_root_lock(
        self,
        *,
        profile_id: UUID,
        label: str,
        transaction_id: UUID | None = None,
        allow_existing_profile: bool = False,
    ) -> None:
        """Reject a label collision while the custody-root lock is held.

        The same scan serves initial creation and recovery publication.  In the
        recovery form, a matching profile is accepted only when its durable
        commit names this transaction; an unrelated commit is a conflict.
        """
        for existing_profile_id in self._adapters.list_current_profile_custody_capsule_ids(root=self._root):
            if existing_profile_id == profile_id:
                if allow_existing_profile:
                    continue
                if transaction_id is None:
                    raise ProfileCustodyTransactionConflictError(
                        "profile UUID already names a committed custody capsule"
                    )
                material = self._adapters.load_committed_profile_password_material(existing_profile_id, root=self._root)
                if material.commit.transaction_id != transaction_id:
                    raise ProfileCustodyTransactionConflictError(
                        "profile UUID is now committed by another custody transaction"
                    )
                continue
            try:
                existing_label = self._adapters.load_committed_profile_custody_label_record(
                    existing_profile_id, root=self._root
                )
            except Exception as exc:
                raise ProfileCustodyTransactionCorruptError(
                    "committed profile capsule has no valid label projection"
                ) from exc
            if existing_label.label.casefold() == label.casefold():
                raise ProfileCustodyTransactionConflictError("profile label is already bound to a committed capsule")

    def _refuse_duplicate_label_publication_under_root_lock(
        self,
        journal: ProfileCustodyTransactionJournal,
    ) -> None:
        assert journal.label is not None
        self._refuse_duplicate_label_under_root_lock(
            profile_id=journal.profile_id,
            label=journal.label,
            transaction_id=journal.transaction_id,
        )

    def _verify_staged_create_label(self, journal: ProfileCustodyTransactionJournal) -> None:
        """Bind journal intent to the exact label covered by the stage inventory."""
        assert journal.label is not None
        staged_label = self._adapters.load_staged_profile_custody_label_record(
            journal.profile_id,
            journal.transaction_id,
            root=self._root,
        )
        if staged_label.label != journal.label:
            raise ProfileCustodyTransactionConflictError("verified create stage label differs from its journal")

    def recover_create(
        self,
        transaction_id: UUID,
        *,
        now: datetime | None = None,
    ) -> ProfileCustodyTransactionReceipt | None:
        """Recover a create journal without replacing an independently changed pointer.

        Recovery reloads the journal while holding the profile lock, then checks
        the captured pointer witness again immediately before publication.  A
        receipt makes the operation idempotent without replaying adapter effects.
        """
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        journal = self._repository.load_journal(transaction_id)
        if journal.operation is not ProfileCustodyTransactionOperation.CREATE:
            raise ProfileCustodyTransactionRefusalError("journal does not name a custody create transaction")
        with profile_custody_transaction_lock(self._root, journal.profile_id):
            journal = self._repository.load_journal(transaction_id)
            receipt = self._repository.load_receipt(transaction_id)
            if receipt is not None:
                self._mark_create_complete(journal, instant)
                return receipt
            journal = self._recover_prepared_create(journal, instant)
            if journal is None:
                return None
            if journal.state is ProfileCustodyTransactionState.ROLLED_BACK:
                return None
            return self._finish_create_recovery(journal, instant)

    def _mark_create_complete(self, journal: ProfileCustodyTransactionJournal, instant: datetime) -> None:
        if journal.state is not ProfileCustodyTransactionState.COMPLETE:
            self._repository.save_journal(
                journal.with_update(state=ProfileCustodyTransactionState.COMPLETE, updated_at=instant)
            )

    def _recover_prepared_create(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal | None:
        """Resolve the durable create state into publishable or rolled-back work.

        Verified stages go directly through publication; a prepared stage must
        be inventoried and label-checked again.  Unknown states remain visible
        to the caller instead of being silently interpreted as success.
        """
        if journal.state in {
            ProfileCustodyTransactionState.STAGE_VERIFIED,
            ProfileCustodyTransactionState.CAPSULE_PUBLISHED,
        }:
            return self._publish_verified_create(journal, instant)
        if journal.state is not ProfileCustodyTransactionState.PREPARED:
            return journal
        return self._recover_prepared_create_stage(journal, instant)

    def _recover_prepared_create_stage(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal | None:
        """Reconcile a prepared stage against the pointer and final capsule.

        Both stage and final presence is corruption, while neither is a safe
        rollback only when the pointer still equals the original witness.  A
        surviving stage is promoted to ``STAGE_VERIFIED`` before publication.
        """
        current = ProfileCustodyPointerSnapshot.capture(self._root)
        stage = self._create_stage_path(journal)
        final = self._adapters.recognize_current_profile_capsule(journal.profile_id, root=self._root)
        if os.path.lexists(stage) and final is not None:
            raise ProfileCustodyTransactionConflictError("create recovery found both its stage and final capsule")
        if final is None and not os.path.lexists(stage):
            if current != journal.pointer_before:
                raise ProfileCustodyTransactionConflictError(
                    "create recovery will not overwrite an independently changed pointer"
                )
            rolled_back = journal.with_update(state=ProfileCustodyTransactionState.ROLLED_BACK, updated_at=instant)
            self._repository.save_journal(rolled_back)
            return None
        if final is not None:
            raise ProfileCustodyTransactionConflictError("create final capsule lacks its verified journal state")
        try:
            inventory = ProfileCustodyInventoryWitness.from_inventory(
                self._adapters.inventory_staged_profile_custody_capsule(
                    profile_id=journal.profile_id, transaction_id=journal.transaction_id, root=self._root
                )
            )
        except Exception as exc:
            raise ProfileCustodyTransactionConflictError("create stage cannot be verified for recovery") from exc
        self._verify_staged_create_label(journal)
        verified = journal.with_update(
            state=ProfileCustodyTransactionState.STAGE_VERIFIED,
            proposed_custody_digest=inventory.digest,
            updated_at=instant,
        )
        self._repository.save_journal(verified)
        return self._publish_verified_create(verified, instant)

    def _publish_verified_create(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal:
        """Publish a verified stage and compare-and-swap the active pointer.

        A final capsule may already exist after a crash, but it must carry this
        transaction's commit and exact inventory.  The pointer is never replaced
        when another operation has changed it since the journal was prepared.

        Selecting the new capsule DISPLACES whichever profile the pointer named
        before, so the displaced profile's durable session material is retired
        here, strictly before the swap.  Ordering it ahead of the swap is what
        makes the property crash-proof without a second durable state: a process
        death can leave the retirement done and the pointer unmoved, which costs
        the operator one passphrase, but it can never leave the pointer moved and
        the receipt live, which costs a passphrase-free bucket key.
        """
        assert journal.proposed_custody_digest is not None
        self._refuse_duplicate_label_publication_under_root_lock(journal)
        stage = self._create_stage_path(journal)
        final = self._adapters.recognize_current_profile_capsule(journal.profile_id, root=self._root)
        if os.path.lexists(stage) and final is None:
            inventory = ProfileCustodyInventoryWitness.from_inventory(
                self._adapters.inventory_staged_profile_custody_capsule(
                    profile_id=journal.profile_id, transaction_id=journal.transaction_id, root=self._root
                )
            )
            if inventory.digest != journal.proposed_custody_digest:
                raise ProfileCustodyTransactionConflictError("verified create stage differs from its journal")
            self._verify_staged_create_label(journal)
            self._adapters.publish_staged_profile_custody_capsule(
                profile_id=journal.profile_id, transaction_id=journal.transaction_id, root=self._root
            )
            published = journal.with_update(state=ProfileCustodyTransactionState.CAPSULE_PUBLISHED, updated_at=instant)
            self._repository.save_journal(published)
            journal = published
        elif final is not None:
            inventory = self._current_create_inventory(journal)
            if inventory is None:
                raise ProfileCustodyTransactionConflictError("verified create final capsule is absent")
            journal = journal.with_update(state=ProfileCustodyTransactionState.CAPSULE_PUBLISHED, updated_at=instant)
            self._repository.save_journal(journal)
        else:
            raise ProfileCustodyTransactionConflictError("verified create stage disappeared before publication")
        current = ProfileCustodyPointerSnapshot.capture(self._root)
        replacement = BucketPointer(bucket_id=str(journal.profile_id), schema_version=1).to_toml().encode("utf-8")
        if current == journal.pointer_before:
            self._retire_displaced_profile_session(journal)
            compare_and_swap_profile_pointer(
                root=self._root,
                expected=journal.pointer_before,
                replacement=replacement,
            )
        elif current.captured_bytes() != replacement:
            raise ProfileCustodyTransactionConflictError(
                "create recovery will not overwrite an independently changed pointer"
            )
        else:
            self._retire_displaced_profile_session(journal)
        published = journal.with_update(
            state=ProfileCustodyTransactionState.POINTER_PUBLISHED,
            updated_at=instant,
        )
        self._repository.save_journal(published)
        return published

    def _retire_displaced_profile_session(self, journal: ProfileCustodyTransactionJournal) -> None:
        """Void the durable session of the profile this create is about to displace.

        Creation selects its new capsule, and until this ran nothing retired the
        profile it selected AWAY from.  That profile kept a resumable
        acceleration receipt, so its bucket key stayed recoverable with no
        passphrase for the whole window until some later login happened to
        observe the boundary -- and permanently for a registration no login ever
        follows.

        The identity comes from ``pointer_before``: the durable pointer value
        this transaction captured under the custody lock and journalled before
        it staged anything.  Neither of the two identities a fresh process can
        otherwise reach is honest here.  A live in-process session is absent in
        the ordinary operator flow, where every invocation is a new process, and
        the handover journal is written from that same live value, so both are
        blank in exactly the case that leaks.  The pointer's PREVIOUS value is
        durable, is recorded before the swap that invalidates it, and is
        therefore readable on every replay.

        Routed through the one revocation primitive the delete transaction
        already uses, so a second implementation of "this profile's stored
        session is void" cannot exist to disagree with the first.  That
        primitive verifies the artefact is gone and raises when it is not; the
        refusal is deliberately converted rather than swallowed, so a retirement
        that did not complete refuses the registration with the pointer still on
        the displaced profile.

        A pointer naming something that is not a profile UUID owns no session
        record -- session artefacts are UUID-keyed -- so there is nothing to
        retire and nothing to leak.  It is passed over rather than refused,
        because registering a fresh profile is the operator's route out of a
        corrupt pointer and must not be blocked by it.
        """
        displaced = self._selected_profile_before(journal.pointer_before)
        if displaced is None or displaced == str(journal.profile_id):
            return
        try:
            UUID(displaced)
        except ValueError:
            return
        try:
            remove_profile_session_acceleration_for_custody_delete(
                storage_root=self._root,
                bucket_id=displaced,
            )
        except Exception as exc:
            raise ProfileCustodyDisplacedSessionRetirementError(
                "displaced profile session acceleration could not be retired before pointer publication"
            ) from exc

    @staticmethod
    def _selected_profile_before(snapshot: ProfileCustodyPointerSnapshot) -> str | None:
        """Return the profile the captured pointer named, or ``None`` when unselected."""
        captured = snapshot.captured_bytes()
        if captured is None:
            return None
        try:
            pointer = BucketPointer.from_toml(captured.decode("utf-8"))
        except (UnicodeDecodeError, ValidationError, ValueError) as exc:
            raise ProfileCustodyTransactionConflictError("captured active profile pointer is not canonical") from exc
        return pointer.bucket_id

    def _finish_create_recovery(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionReceipt:
        """Write the create receipt only after the pointer is durably published.

        The receipt records the final inventory and is itself idempotent through
        the repository.  The journal reaches ``COMPLETE`` last, so recovery can
        distinguish publication from receipt persistence.
        """
        if journal.state is not ProfileCustodyTransactionState.POINTER_PUBLISHED:
            raise ProfileCustodyTransactionConflictError("create journal has an unexplained recovery state")
        inventory = self._current_create_inventory(journal)
        if inventory is None:
            raise ProfileCustodyTransactionConflictError("published create capsule disappeared before receipt")
        receipt = ProfileCustodyTransactionReceipt.create(
            transaction_id=journal.transaction_id,
            profile_id=journal.profile_id,
            operation=ProfileCustodyTransactionOperation.CREATE,
            completed_at=instant,
            inventory=inventory,
            pointer_cleared=False,
            pointer_published=True,
        )
        receipt = self._repository.write_receipt(receipt)
        self._repository.save_journal(
            journal.with_update(state=ProfileCustodyTransactionState.COMPLETE, updated_at=instant)
        )
        return receipt

    def confirmation_for(self, journal: ProfileCustodyTransactionJournal) -> ProfileCustodyDeleteConfirmation:
        """Return the exact target-bound confirmation object an operator must echo."""
        if journal.operation is not ProfileCustodyTransactionOperation.DELETE or journal.inventory is None:
            raise ProfileCustodyTransactionRefusalError("only a prepared delete journal can be confirmed")
        assert journal.confirmation_challenge is not None
        return ProfileCustodyDeleteConfirmation(
            transaction_id=journal.transaction_id,
            profile_id=journal.profile_id,
            inventory_digest=journal.inventory.digest,
            challenge=journal.confirmation_challenge,
        )

    def execute_delete(
        self,
        confirmation: ProfileCustodyDeleteConfirmation,
        *,
        now: datetime | None = None,
    ) -> ProfileCustodyTransactionReceipt:
        """Execute or resume one fully confirmed local deletion; never touch external state.

        The confirmation is checked before and inside the profile lock.  Each
        owner step persists its receipt and next journal state, allowing a crash
        to resume without repeating a completed local effect.
        """
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        journal = self._repository.load_journal(confirmation.transaction_id)
        if journal.operation is not ProfileCustodyTransactionOperation.DELETE:
            raise ProfileCustodyTransactionRefusalError("confirmation does not name a local delete transaction")
        self._validate_confirmation(journal, confirmation)
        with profile_custody_transaction_lock(self._root, journal.profile_id):
            journal = self._repository.load_journal(journal.transaction_id)
            self._validate_confirmation(journal, confirmation)
            receipt = self._repository.load_receipt(journal.transaction_id)
            if receipt is not None:
                if journal.state is not ProfileCustodyTransactionState.COMPLETE:
                    self._repository.save_journal(
                        journal.with_update(state=ProfileCustodyTransactionState.COMPLETE, updated_at=instant)
                    )
                return receipt
            return self._resume_delete(journal, instant)

    def _resume_delete(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionReceipt:
        """Advance the ordered local-delete owners from the prepared journal.

        Hold evidence is re-read before any effect.  The state sequence is
        intentionally linear: secrets, session acceleration, pointer, tombstone
        rename, local removal, and final receipt.
        """
        self._validate_current_delete_hold(journal, instant)
        assert journal.inventory is not None
        inventory_digest = journal.inventory.digest
        journal = self._mark_delete_prepared(journal, instant)
        journal = self._advance_delete_state(
            journal,
            instant,
            expected=ProfileCustodyTransactionState.DELETE_MARKED,
            next_state=ProfileCustodyTransactionState.PROCESS_SECRETS_REVOKED,
            action=self._revoke_process_secrets,
        )
        journal = self._advance_delete_state(
            journal,
            instant,
            expected=ProfileCustodyTransactionState.PROCESS_SECRETS_REVOKED,
            next_state=ProfileCustodyTransactionState.SESSION_ACCELERATION_DELETED,
            action=self._delete_local_session_acceleration,
        )
        journal = self._clear_delete_pointer(journal, instant)
        journal = self._rename_delete_capsule(journal, inventory_digest, instant)
        journal = self._remove_delete_capsule(journal, inventory_digest, instant)
        return self._complete_delete(journal, instant)

    def _validate_current_delete_hold(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> None:
        """Require the original hold assessment to remain current at execution.

        A changed legal or filing owner DISPOSITION invalidates the old
        confirmation, even when the old assessment had permitted deletion. This
        closes the time-of-check/time-of-use gap between preflight and
        execution.

        Compared on the dispositions rather than on the whole assessment, and
        the distinction is the difference between a guard and a wall. An
        assessment carries ``assessed_at`` and an ``evidence_digest`` computed
        over it, so re-assessing unchanged owner facts one second later yields
        an unequal object. Whole-object equality therefore refused EVERY
        deletion whose preflight and execution fell at different instants --
        which is every real one, because the operator echoes a confirmation
        between them. The criterion the paragraph above states is owner facts;
        the observation instant is when we looked, not what we found.

        What still invalidates a confirmation: either owner flipping between
        cleared and held, in either direction, and any state in which the
        current assessment does not permit deletion. The dangerous transition
        -- cleared at preflight, held at execution -- is refused by both the
        disposition comparison and the permission check independently.

        What no longer invalidates it: a re-observation of unchanged
        dispositions. One residual gap is worth naming rather than leaving for
        someone to discover: a change of SOURCE RECORD under an unchanged
        disposition -- one legal case closing as another opens, both held --
        is not detected here, because the assessment carries only the
        dispositions and a time-varying digest, not the source-record
        identities. Closing that needs the per-owner ``source_record_digest``
        carried in the journal, which is a persisted-shape change and is not
        made here. It is not a safety hole at present: an unchanged ``held``
        still refuses, and an unchanged ``cleared`` is a state deletion is
        legitimately permitted in.
        """
        if journal.hold_assessment is None or not journal.hold_assessment.permits_local_deletion:
            raise ProfileCustodyTransactionRefusalError("a legal or filing hold blocks local profile deletion")
        current_hold = self._holds.assess(journal.profile_id, now=instant)
        recorded = journal.hold_assessment
        dispositions_changed = (
            current_hold.profile_id != recorded.profile_id
            or current_hold.legal_hold != recorded.legal_hold
            or current_hold.filing_hold != recorded.filing_hold
        )
        if dispositions_changed or not current_hold.permits_local_deletion:
            raise ProfileCustodyTransactionRefusalError(
                "canonical legal or filing hold evidence changed after delete preflight"
            )

    def _mark_delete_prepared(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal:
        """Re-inventory the committed capsule before writing its deletion marker.

        The marker binds the exact non-secret inventory captured at preflight;
        any change is a conflict rather than an invitation to delete new data.
        """
        if journal.state is not ProfileCustodyTransactionState.DELETE_PREPARED:
            return journal
        assert journal.inventory is not None
        inventory = ProfileCustodyInventoryWitness.from_inventory(
            self._adapters.inventory_committed_profile_custody_capsule(journal.profile_id, root=self._root)
        )
        if inventory != journal.inventory:
            raise ProfileCustodyTransactionConflictError("profile capsule inventory changed after delete preflight")
        self._adapters.write_profile_custody_deletion_marker(
            profile_id=journal.profile_id,
            transaction_id=journal.transaction_id,
            inventory_digest=journal.inventory.digest,
            root=self._root,
        )
        marked = journal.with_update(state=ProfileCustodyTransactionState.DELETE_MARKED, updated_at=instant)
        self._repository.save_journal(marked)
        return marked

    def _advance_delete_state(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
        *,
        expected: ProfileCustodyTransactionState,
        next_state: ProfileCustodyTransactionState,
        action: Callable[[ProfileCustodyTransactionJournal, datetime], None],
    ) -> ProfileCustodyTransactionJournal:
        """Clear the pointer only after the two owner effects are durable.

        Compare-and-swap accepts the already-cleared target produced by a prior
        attempt, but refuses any unrelated pointer value.
        """
        """Run one idempotent owner step and persist its next journal state."""
        if journal.state is not expected:
            return journal
        self._verify_source_delete_marker(journal)
        action(journal, instant)
        advanced = journal.with_update(state=next_state, updated_at=instant)
        self._repository.save_journal(advanced)
        return advanced

    def _clear_delete_pointer(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal:
        """Rename the committed capsule to its transaction-owned tombstone.

        An existing tombstone is verified instead of recreated, preserving
        idempotence after a crash between rename and journal persistence.
        """
        if journal.state is not ProfileCustodyTransactionState.SESSION_ACCELERATION_DELETED:
            return journal
        self._verify_source_delete_marker(journal)
        replacement = self._pointer_replacement(journal.pointer_before, journal.profile_id)
        current = ProfileCustodyPointerSnapshot.capture(self._root)
        if current == journal.pointer_before:
            compare_and_swap_profile_pointer(root=self._root, expected=journal.pointer_before, replacement=replacement)
        elif current.captured_bytes() != replacement:
            raise ProfileCustodyTransactionConflictError("active profile pointer changed after delete preflight")
        cleared = journal.with_update(state=ProfileCustodyTransactionState.POINTER_CLEARED, updated_at=instant)
        self._repository.save_journal(cleared)
        return cleared

    def _rename_delete_capsule(
        self,
        journal: ProfileCustodyTransactionJournal,
        inventory_digest: str,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal:
        """Verify and remove the tombstone, then persist ``LOCAL_REMOVED``."""
        if journal.state is not ProfileCustodyTransactionState.POINTER_CLEARED:
            return journal
        tombstone = self._adapters.profile_custody_deletion_path(
            profile_id=journal.profile_id,
            transaction_id=journal.transaction_id,
            root=self._root,
        )
        if os.path.lexists(tombstone):
            self._adapters.verify_profile_custody_deletion_tombstone(
                profile_id=journal.profile_id,
                transaction_id=journal.transaction_id,
                inventory_digest=inventory_digest,
                root=self._root,
            )
        else:
            self._verify_source_delete_marker(journal)
            tombstone = self._adapters.rename_profile_custody_capsule_for_deletion(
                profile_id=journal.profile_id,
                transaction_id=journal.transaction_id,
                root=self._root,
            )
        renamed = journal.with_update(
            state=ProfileCustodyTransactionState.CAPSULE_RENAMED,
            updated_at=instant,
            tombstone_relative_path=tombstone.name,
        )
        self._repository.save_journal(renamed)
        return renamed

    def _remove_delete_capsule(
        self,
        journal: ProfileCustodyTransactionJournal,
        inventory_digest: str,
        instant: datetime,
    ) -> ProfileCustodyTransactionJournal:
        if journal.state is not ProfileCustodyTransactionState.CAPSULE_RENAMED:
            return journal
        self._adapters.verify_profile_custody_deletion_tombstone(
            profile_id=journal.profile_id,
            transaction_id=journal.transaction_id,
            inventory_digest=inventory_digest,
            root=self._root,
        )
        self._adapters.remove_profile_custody_deletion_tombstone(
            profile_id=journal.profile_id,
            transaction_id=journal.transaction_id,
            root=self._root,
        )
        removed = journal.with_update(state=ProfileCustodyTransactionState.LOCAL_REMOVED, updated_at=instant)
        self._repository.save_journal(removed)
        return removed

    def _complete_delete(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
    ) -> ProfileCustodyTransactionReceipt:
        """Write the final receipt and mark the local deletion complete."""
        if journal.state is not ProfileCustodyTransactionState.LOCAL_REMOVED:
            raise ProfileCustodyTransactionConflictError("delete journal has an unexplained recovery state")
        assert journal.inventory is not None
        receipt = ProfileCustodyTransactionReceipt.create(
            transaction_id=journal.transaction_id,
            profile_id=journal.profile_id,
            completed_at=instant,
            inventory=journal.inventory,
            pointer_cleared=self._pointer_replacement(journal.pointer_before, journal.profile_id) is None,
        )
        receipt = self._repository.write_receipt(receipt)
        self._repository.save_journal(
            journal.with_update(state=ProfileCustodyTransactionState.COMPLETE, updated_at=instant)
        )
        return receipt

    def _current_create_inventory(
        self,
        journal: ProfileCustodyTransactionJournal,
    ) -> ProfileCustodyInventoryWitness | None:
        """Return the current committed inventory when it still belongs here.

        Stage and final capsule presence cannot coexist.  A final capsule must
        match the journal's transaction, generation, label, and custody digest.
        """
        stage = self._create_stage_path(journal)
        committed = self._adapters.recognize_current_profile_capsule(journal.profile_id, root=self._root)
        if os.path.lexists(stage) and committed is not None:
            raise ProfileCustodyTransactionConflictError("create recovery found both its stage and final capsule")
        if committed is None:
            return None
        self._validate_current_create_material(journal)
        inventory = ProfileCustodyInventoryWitness.from_inventory(
            self._adapters.inventory_committed_profile_custody_capsule(journal.profile_id, root=self._root)
        )
        if inventory.digest != journal.proposed_custody_digest:
            raise ProfileCustodyTransactionConflictError("published create custody digest differs from its journal")
        return inventory

    def _validate_current_create_material(self, journal: ProfileCustodyTransactionJournal) -> None:
        """Check the commit, password generation, and label against the journal."""
        material = self._adapters.load_committed_profile_password_material(journal.profile_id, root=self._root)
        if material.commit.transaction_id != journal.transaction_id:
            raise ProfileCustodyTransactionConflictError("final capsule was not published by this create transaction")
        if material.envelope.password_generation != journal.proposed_generation:
            raise ProfileCustodyTransactionConflictError(
                "final capsule password generation differs from create journal"
            )
        assert journal.label is not None
        if (
            self._adapters.load_committed_profile_custody_label_record(journal.profile_id, root=self._root).label
            != journal.label
        ):
            raise ProfileCustodyTransactionConflictError("published create label differs from its journal")

    def _create_stage_path(self, journal: ProfileCustodyTransactionJournal) -> Path:
        assert journal.staged_relative_path is not None
        expected = cast(
            Path,
            self._adapters.profile_custody_staging_path(
                profile_id=journal.profile_id, transaction_id=journal.transaction_id, root=self._root
            ),
        )
        if journal.staged_relative_path != expected.name:
            raise ProfileCustodyTransactionConflictError(
                "create journal stage is not the transaction-owned custody stage"
            )
        return expected

    def _verify_source_delete_marker(self, journal: ProfileCustodyTransactionJournal) -> None:
        """Authenticate the prepared deletion marker before each destructive step."""
        assert journal.inventory is not None
        try:
            self._adapters.verify_profile_custody_deletion_marker(
                profile_id=journal.profile_id,
                transaction_id=journal.transaction_id,
                inventory_digest=journal.inventory.digest,
                root=self._root,
            )
        except Exception as exc:
            raise ProfileCustodyTransactionConflictError(
                "prepared local deletion marker no longer matches source custody"
            ) from exc

    def _record_owner_effect(
        self,
        journal: ProfileCustodyTransactionJournal,
        instant: datetime,
        *,
        owner: Literal["process-secret-revocation", "local-session-acceleration"],
        error_message: str,
        produce: Callable[[], Any],
    ) -> None:
        """Persist one idempotent owner effect after its real adapter succeeds."""
        if self._repository.load_owner_receipt(journal.transaction_id, owner) is not None:
            return
        try:
            effect = produce()
        except Exception as exc:
            raise ProfileCustodyTransactionConflictError(error_message) from exc
        self._repository.write_owner_receipt(
            ProfileCustodyOwnerReceipt.create(
                schema_version=CUSTODY_RECEIPT_SCHEMA_VERSION,
                transaction_id=journal.transaction_id,
                profile_id=journal.profile_id,
                owner=owner,
                effect=effect.value,
                completed_at=instant,
            )
        )

    def _revoke_process_secrets(self, journal: ProfileCustodyTransactionJournal, instant: datetime) -> None:
        self._record_owner_effect(
            journal,
            instant,
            owner="process-secret-revocation",
            error_message="current process-secret owner could not be revoked",
            produce=lambda: revoke_live_profile_secret_for_custody_delete(bucket_id=str(journal.profile_id)),
        )

    def _delete_local_session_acceleration(self, journal: ProfileCustodyTransactionJournal, instant: datetime) -> None:
        self._record_owner_effect(
            journal,
            instant,
            owner="local-session-acceleration",
            error_message="current local-session acceleration owner could not be removed",
            produce=lambda: remove_profile_session_acceleration_for_custody_delete(
                storage_root=self._root,
                bucket_id=str(journal.profile_id),
            ),
        )

    @classmethod
    def _pointer_replacement(cls, snapshot: ProfileCustodyPointerSnapshot, profile_id: UUID) -> bytes | None:
        """Return the pointer bytes after removing this profile, if needed."""
        selected = cls._selected_profile_before(snapshot)
        if selected is None:
            return None
        return None if selected == str(profile_id) else snapshot.captured_bytes()

    @staticmethod
    def _validate_confirmation(
        journal: ProfileCustodyTransactionJournal,
        confirmation: ProfileCustodyDeleteConfirmation,
    ) -> None:
        """Require confirmation identity, inventory, and challenge to match exactly."""
        if journal.inventory is None or journal.confirmation_challenge is None:
            raise ProfileCustodyTransactionCorruptError("delete journal lacks confirmation evidence")
        if (
            confirmation.transaction_id != journal.transaction_id
            or confirmation.profile_id != journal.profile_id
            or confirmation.inventory_digest != journal.inventory.digest
            or confirmation.challenge != journal.confirmation_challenge
        ):
            raise ProfileCustodyTransactionRefusalError("delete confirmation is not bound to the prepared local target")


__all__ = ["ProfileCustodyDisplacedSessionRetirementError", "_ProfileCustodyTransactionCapability"]
