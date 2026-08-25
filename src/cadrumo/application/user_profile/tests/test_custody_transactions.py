"""Real-filesystem contracts for current-format local custody transactions."""

from __future__ import annotations

import os
from base64 import b64encode
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from typing import Any
from uuid import UUID, uuid4

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyCapsuleLabel,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyRecordError,
    ProfileCustodySentinelRecord,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
    inventory_staged_profile_custody_capsule,
    list_current_profile_custody_capsule_ids,
    load_committed_profile_custody_label_record,
    mint_profile_session,
    profile_custody_staging_path,
    profile_session_path,
    publish_profile_custody_capsule,
    publish_staged_profile_custody_capsule,
    rename_profile_custody_capsule_for_deletion,
    write_profile_custody_deletion_marker,
)
from ....adapters.persistence.storage.master_key import (
    BucketSession,
    bind_active_bucket_session,
    current_active_bucket_session,
)
from ....core import Period
from ....core.bucket_pointer import BucketPointer
from ....core.config import Settings
from ....domain.modelos import ModeloCode, ModeloRecord, derive_filing_record_id
from ... import user_profile as user_profiles
from ...evidence import LegalHoldCaseAuthority
from ...filing import FilingRetentionAuthority
from cadrumo.application.user_profile.custody_repository import profile_custody_transaction_lock
from cadrumo.application.user_profile.custody_service import _ProfileCustodyTransactionCapability as ProfileCustodyTransactionService
from cadrumo.application.user_profile.custody_transactions import ProfileCustodyHoldEvidence, ProfileCustodyTransactionConflictError, ProfileCustodyTransactionCorruptError, ProfileCustodyTransactionJournal, ProfileCustodyTransactionOperation, ProfileCustodyTransactionRefusalError, ProfileCustodyTransactionState
from ..profile_pointer import ActiveProfilePointerTransactionError, active_profile_pointer_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("327b296d-8377-4be0-b13a-ca4d8f692e1d")
_OTHER_PROFILE_ID = UUID("57c9594e-65de-470b-b768-4a4dd1323597")
_INSTANT = datetime(2026, 8, 13, 12, 34, 56, tzinfo=UTC)


def _observe_pointer(root: Path) -> BucketPointer:
    """Observe through the only public current-pointer transaction."""
    with active_profile_pointer_transaction(root) as transaction:
        return transaction.read()


def _select_pointer(root: Path, bucket_id: str) -> BucketPointer:
    """Select through the sole transition owner."""
    with active_profile_pointer_transaction(root) as transaction:
        return transaction.select(bucket_id)


def _clear_expected_pointer(root: Path, expected: BucketPointer) -> BucketPointer:
    """Model a crash boundary using the canonical compare-and-transition verb."""
    with active_profile_pointer_transaction(root) as transaction:
        return transaction.compare_and_restore(
            expected=expected,
            captured=BucketPointer.absent(transition_revision=0),
        )


def _committed_capsule(
    root: Path,
    *,
    profile_id: UUID = _PROFILE_ID,
    transaction_id: UUID | None = None,
) -> Path:
    envelope, sentinel, data_files = _create_capsule_input(profile_id=profile_id)
    return publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=transaction_id or uuid4(),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=sentinel,
        data_files={
            **data_files,
            "profile-label.v1.json": ProfileCustodyCapsuleLabel.create(
                profile_id=profile_id,
                label="crash label",
            ).canonical_json_bytes(),
        },
        settings=Settings(cadrumo_local_storage_root=root),
        published_at=_INSTANT,
    )


def _create_capsule_input(
    *,
    profile_id: UUID = _PROFILE_ID,
) -> tuple[ProfileCustodyEnvelope, ProfileCustodySentinelRecord, dict[str, bytes]]:
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=b64encode(b"e" * 16).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=b64encode(b"c" * 32).decode("ascii"),
            tag_b64=b64encode(b"t" * 16).decode("ascii"),
        ),
    )
    return (
        envelope,
        create_profile_custody_sentinel(envelope=envelope, dek=bytes(range(32))),
        {"state/payload.bin": b"encrypted-local-data"},
    )


def _authorise_clear_hold(service: ProfileCustodyTransactionService) -> None:
    """Record actual owner facts; deletion only consumes their projections."""
    LegalHoldCaseAuthority(root=service._root).record_open_case_snapshot(
        profile_id=_PROFILE_ID,
        open_case_ids=(),
        observed_at=_INSTANT,
    )
    FilingRetentionAuthority(root=service._root).record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(),
        observed_at=_INSTANT,
    )


def _filed_record(*, filed_at: datetime) -> ModeloRecord:
    """Produce a real filed-modelo fact for the canonical filing owner."""
    work_unit_id = "a" * 64
    calculation_revision_id = "b" * 64
    filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=str(_PROFILE_ID),
        modelo=ModeloCode("303"),
        filing_year=filed_at.year,
        period=Period.from_year_and_code(filed_at.year, "2T"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )


def _persist_real_current_session_acceleration(root: Path) -> Path:
    """Create the current encrypted session record through its production writer."""
    mint_profile_session(
        storage_root=root,
        profile_id=_PROFILE_ID,
        custody_generation=1,
        dek_epoch=b64encode(b"e" * 16).decode("ascii"),
        dek=bytes(range(32)),
        now=_INSTANT,
        idle_minutes=15,
        absolute_minutes=240,
    )
    return profile_session_path(storage_root=root, profile_id=_PROFILE_ID)


def _publish_once_in_sibling(path_text: str, payload: bytes, result_queue: Any) -> None:
    """Run the real publish primitive in one spawned interpreter."""
    from ....adapters.persistence.storage.custody import (
        ProfileCustodyRecordError,
        ensure_profile_custody_local_directory,
        write_profile_custody_local_record,
    )

    path = Path(path_text)
    try:
        ensure_profile_custody_local_directory(path.parent)
        write_profile_custody_local_record(path, payload, publish_once=True)
    except ProfileCustodyRecordError:
        result_queue.put("collision")
    else:
        result_queue.put("published")


def _hold_transaction_lock_in_sibling(
    root_text: str,
    profile_id_text: str,
    release_event: Any,
    result_queue: Any,
) -> None:
    """Take the actual root-before-profile lock in a separate process.

    ``ready`` is published once the interpreter is up and the lock call is the
    only thing left to do. Without it a caller timing "did the sibling acquire?"
    is timing a Windows spawn plus a cadrumo import -- seconds of startup that
    swallow any window short enough to be a useful contention probe.
    """
    from ....tests.profile_persistence import composed_profile_persistence_ports
    from cadrumo.application.user_profile.custody_repository import profile_custody_transaction_lock

    with composed_profile_persistence_ports():
        result_queue.put("ready")
        with profile_custody_transaction_lock(Path(root_text), UUID(profile_id_text)):
            result_queue.put("locked")
            release_event.wait(30)


def _write_active_pointer_in_sibling(root_text: str, bucket_id_text: str, result_queue: Any) -> None:
    """Perform a production pointer write in an independent interpreter.

    ``ready`` is published once the interpreter is up and the pointer
    transaction is the only work left, so a caller timing "did the sibling get
    in?" measures the lock rather than the seconds a spawn spends importing.
    """
    from ....tests.profile_persistence import composed_profile_persistence_ports
    from ..profile_pointer import active_profile_pointer_transaction

    with composed_profile_persistence_ports():
        result_queue.put("ready")
        with active_profile_pointer_transaction(Path(root_text)) as pointer_transaction:
            pointer_transaction.select(bucket_id_text)
        result_queue.put("written")


def _crash_create_at_durable_boundary(root_text: str, transaction_id_text: str, boundary: str) -> None:
    """Persist one real create boundary in a child, then terminate without cleanup."""
    from ....tests.profile_persistence import composed_profile_persistence_ports

    composition = composed_profile_persistence_ports()
    composition.__enter__()
    root = Path(root_text)
    transaction_id = UUID(transaction_id_text)
    service = ProfileCustodyTransactionService(root=root)
    envelope, sentinel, data_files = _create_capsule_input()
    label_record = ProfileCustodyCapsuleLabel.create(profile_id=_PROFILE_ID, label="crash label")
    stage_name = profile_custody_staging_path(
        profile_id=_PROFILE_ID,
        transaction_id=transaction_id,
        root=root,
    ).name
    journal = ProfileCustodyTransactionJournal.create(
        transaction_id=transaction_id,
        operation=ProfileCustodyTransactionOperation.CREATE,
        profile_id=_PROFILE_ID,
        state=ProfileCustodyTransactionState.PREPARED,
        started_at=_INSTANT,
        updated_at=_INSTANT,
        pointer_before=_observe_pointer(root),
        proposed_generation=envelope.password_generation,
        label="crash label",
        label_revision=label_record.label_revision,
        label_content_digest=label_record.content_digest,
        label_self_digest=label_record.self_digest,
        staged_relative_path=stage_name,
    )
    service._repository.create_journal(journal)
    if boundary == "intent":
        os._exit(97)
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=transaction_id,
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=sentinel,
        data_files={
            **data_files,
            "profile-label.v1.json": label_record.canonical_json_bytes(),
        },
        root=root,
        published_at=_INSTANT,
        stage_only=True,
    )
    if boundary == "stage":
        os._exit(97)
    inventory = inventory_staged_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=transaction_id,
        root=root,
    )
    verified = journal.with_update(
        state=ProfileCustodyTransactionState.STAGE_VERIFIED,
        proposed_custody_digest=inventory.digest,
        updated_at=_INSTANT,
    )
    service._repository.save_journal(verified)
    if boundary == "verify":
        os._exit(97)
    publish_staged_profile_custody_capsule(profile_id=_PROFILE_ID, transaction_id=transaction_id, root=root)
    if boundary == "rename":
        os._exit(97)
    raise AssertionError(f"unknown crash boundary {boundary!r}")


def _create_labeled_capsule_in_sibling(
    root_text: str,
    profile_id_text: str,
    label: str,
    result_queue: Any,
    barrier: Any = None,
) -> None:
    """Attempt the actual complete create transaction in an independent process.

    The barrier is released once the envelope material exists and the
    transaction is the only work left. Without it the siblings reach the create
    whenever their own KDF setup happens to finish, so the race is loose and
    the collision is decided by scheduling luck rather than by the lock.
    """
    from ....tests.profile_capsule import mint_test_profile_recovery_envelope
    from ....tests.profile_persistence import composed_profile_persistence_ports

    root = Path(root_text)
    profile_id = UUID(profile_id_text)
    envelope, sentinel, data_files = _create_capsule_input(profile_id=profile_id)
    with composed_profile_persistence_ports():
        recovery_envelope = mint_test_profile_recovery_envelope(
            profile_id,
            dek=bytes(range(32)),
            dek_epoch=envelope.dek_epoch,
        )
        if barrier is not None:
            barrier.wait(60)
        try:
            ProfileCustodyTransactionService(root=root).create_capsule(
                profile_id=profile_id,
                password_envelope=envelope,
                sentinel=sentinel,
                data_files=data_files,
                recovery_envelope=recovery_envelope,
                label=label,
                now=_INSTANT,
            )
        except ProfileCustodyTransactionConflictError:
            result_queue.put("collision")
        else:
            result_queue.put("published")


def test_confirmed_local_delete_is_atomic_receipted_and_idempotent(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    _select_pointer(tmp_path, str(_PROFILE_ID))
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)

    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    confirmation = service.confirmation_for(journal)
    receipt = service.execute_delete(confirmation, now=_INSTANT)

    assert not capsule.exists()
    assert _observe_pointer(tmp_path).bucket_id is None
    assert receipt.transaction_id == journal.transaction_id
    assert receipt.pointer_cleared is True
    assert receipt.retained_external_state
    assert service.execute_delete(confirmation, now=_INSTANT) == receipt
    assert service._repository.load_journal(journal.transaction_id).state is ProfileCustodyTransactionState.COMPLETE
    assert service._repository.load_receipt(journal.transaction_id) == receipt


def test_inactive_only_delete_revalidates_policy_after_prepare_and_before_effects(tmp_path: Path) -> None:
    """A resumed single-target delete refuses a profile activated after prepare."""
    capsule = _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)

    journal = service.prepare_delete(
        profile_id=_PROFILE_ID,
        requires_inactive_target=True,
        now=_INSTANT,
    )
    assert journal.requires_inactive_target is True
    confirmation = service.confirmation_for(journal)

    # This is the durable crash/resume boundary: another canonical login may
    # publish the pointer after preparation and before a later executor resumes.
    active_pointer = _select_pointer(tmp_path, str(_PROFILE_ID))

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="active profile"):
        service.execute_delete(confirmation, now=_INSTANT + timedelta(seconds=1))

    assert capsule.is_dir()
    assert _observe_pointer(tmp_path) == active_pointer
    assert (
        service._repository.load_journal(journal.transaction_id).state is ProfileCustodyTransactionState.DELETE_PREPARED
    )


def test_delete_completes_when_preflight_and_execution_fall_at_different_instants(tmp_path: Path) -> None:
    """The reproduction: a real delete takes time between confirm and execute.

    Deliberately passes NO ``now`` to any hop, so each call reads the wall
    clock exactly as the public facade and the destructive reset do. That is
    the configuration every production deletion runs in, and it used to refuse:
    the hold assessment carries ``assessed_at`` and a digest computed over it,
    so re-assessing unchanged owner facts produced an unequal object and the
    whole-object comparison read "evidence changed" from the clock alone.

    The sleep is the point rather than incidental slowness -- without a
    measurable gap between preflight and execution the two assessments can
    share a timestamp and the bug hides.
    """
    import time

    capsule = _committed_capsule(tmp_path)
    _select_pointer(tmp_path, str(_PROFILE_ID))
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)

    journal = service.prepare_delete(profile_id=_PROFILE_ID)
    confirmation = service.confirmation_for(journal)
    time.sleep(1.1)
    receipt = service.execute_delete(confirmation)

    assert not capsule.exists()
    assert receipt.transaction_id == journal.transaction_id


def test_delete_still_refuses_when_a_hold_is_taken_between_preflight_and_execution(tmp_path: Path) -> None:
    """The property the guard exists for must survive the narrowing.

    A legal case opening AFTER the preflight authorised deletion is the
    time-of-check/time-of-use case. Narrowing the comparison from the whole
    assessment to the dispositions must not trade the false positive above for
    a false negative here, so this drives the real owner authority rather than
    editing the journal.
    """
    _committed_capsule(tmp_path)
    _select_pointer(tmp_path, str(_PROFILE_ID))
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)

    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    confirmation = service.confirmation_for(journal)

    LegalHoldCaseAuthority(root=tmp_path).record_open_case_snapshot(
        profile_id=_PROFILE_ID,
        open_case_ids=("legal-case-opened-after-preflight",),
        observed_at=_INSTANT + timedelta(seconds=1),
    )

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="changed after delete preflight"):
        service.execute_delete(confirmation, now=_INSTANT + timedelta(seconds=2))


def test_delete_refuses_hold_and_never_creates_a_journal(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    LegalHoldCaseAuthority(root=tmp_path).record_open_case_snapshot(
        profile_id=_PROFILE_ID,
        open_case_ids=("legal-case-locked",),
        observed_at=_INSTANT,
    )
    FilingRetentionAuthority(root=tmp_path).record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(),
        observed_at=_INSTANT,
    )

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="hold"):
        service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)

    assert capsule.is_dir()
    assert not (tmp_path / "profile-custody-transactions").exists()


def test_delete_refuses_when_canonical_hold_evidence_is_absent(tmp_path: Path) -> None:
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="hold owner facts are absent"):
        service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)


def test_delete_hold_preflight_derives_only_from_durable_owner_records(tmp_path: Path) -> None:
    """A deletion caller has no API for inventing a clear legal or filing result."""
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    legal_owner = LegalHoldCaseAuthority(root=tmp_path)
    filing_owner = FilingRetentionAuthority(root=tmp_path)
    legal_owner.record_open_case_snapshot(
        profile_id=_PROFILE_ID,
        open_case_ids=("legal-retention-order-2026-08-13",),
        observed_at=_INSTANT,
    )
    filing_owner.record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(),
        observed_at=_INSTANT,
    )

    assert not hasattr(user_profiles, "ProfileCustodyHoldOwnerRecord")
    assert not hasattr(user_profiles, "ProfileCustodyLegalHoldRecordRepository")
    assert not hasattr(user_profiles, "ProfileCustodyFilingHoldRecordRepository")
    assert not hasattr(ProfileCustodyHoldEvidence, "create")
    legal_projection = legal_owner.project(_PROFILE_ID, now=_INSTANT)
    assert legal_projection.blocks_local_deletion is True
    assert legal_projection.source_record_id == f"legal-case-snapshot-{_PROFILE_ID}"
    with pytest.raises(ProfileCustodyTransactionRefusalError, match="hold"):
        service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)


def test_delete_revalidates_owner_hold_records_before_destruction(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    FilingRetentionAuthority(root=tmp_path).record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(_filed_record(filed_at=datetime(2026, 8, 1, tzinfo=UTC)),),
        observed_at=_INSTANT + timedelta(seconds=1),
    )

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="hold"):
        service.execute_delete(service.confirmation_for(journal), now=_INSTANT + timedelta(seconds=2))
    assert capsule.is_dir()


def test_delete_refuses_pointer_or_inventory_drift_after_preflight(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    _select_pointer(tmp_path, str(_PROFILE_ID))
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)

    _select_pointer(tmp_path, str(_OTHER_PROFILE_ID))
    with pytest.raises(ProfileCustodyTransactionConflictError, match="pointer changed"):
        service.execute_delete(service.confirmation_for(journal), now=_INSTANT)
    assert capsule.is_dir()


def test_delete_refuses_inventory_drift_after_preflight(tmp_path: Path) -> None:
    """A distinct preflight proves inventory drift without reviving a stale coordinate."""
    root = tmp_path / "inventory-drift"
    root.mkdir()
    capsule = _committed_capsule(root)
    _select_pointer(root, str(_PROFILE_ID))
    service = ProfileCustodyTransactionService(root=root)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)

    (capsule / "data" / "state" / "payload.bin").write_bytes(b"changed encrypted local data")
    with pytest.raises(ProfileCustodyTransactionConflictError, match=r"marker|inventory"):
        service.execute_delete(service.confirmation_for(journal), now=_INSTANT)
    assert capsule.is_dir()


def test_inventory_and_delete_refuse_a_real_link_inside_the_capsule(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    linked = capsule / "data" / "state" / "redirect.bin"
    os.symlink(outside, linked)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)

    with pytest.raises(ProfileCustodyRecordError, match=r"link|reparse"):
        service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)

    assert outside.read_bytes() == b"outside"
    assert capsule.is_dir()


def test_crash_recovery_removes_only_its_transaction_tombstone(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    assert journal.inventory is not None
    write_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=journal.transaction_id,
        inventory_digest=journal.inventory.digest,
        root=tmp_path,
    )
    tombstone = rename_profile_custody_capsule_for_deletion(
        profile_id=_PROFILE_ID,
        transaction_id=journal.transaction_id,
        root=tmp_path,
    )
    service._repository.save_journal(
        journal.with_update(
            state=ProfileCustodyTransactionState.POINTER_CLEARED,
            updated_at=_INSTANT,
        )
    )

    receipt = service.execute_delete(service.confirmation_for(journal), now=_INSTANT)

    assert receipt.transaction_id == journal.transaction_id
    assert not tombstone.exists()
    assert not capsule.exists()


def test_delete_recovers_a_pointer_clear_before_its_journal_state_is_saved(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    _select_pointer(tmp_path, str(_PROFILE_ID))
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)

    _clear_expected_pointer(tmp_path, journal.pointer_before)
    receipt = service.execute_delete(service.confirmation_for(journal), now=_INSTANT)

    assert receipt.pointer_cleared is True
    assert not capsule.exists()


def test_delete_refuses_a_preplanted_or_ambiguous_tombstone(tmp_path: Path) -> None:
    capsule = _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    tombstone = tmp_path / "buckets" / f".{_PROFILE_ID}.deleting-{journal.transaction_id}"
    tombstone.mkdir()
    untouched = tombstone / "unrelated.bin"
    untouched.write_bytes(b"unrelated")
    service._repository.save_journal(
        journal.with_update(state=ProfileCustodyTransactionState.POINTER_CLEARED, updated_at=_INSTANT)
    )

    with pytest.raises(ProfileCustodyRecordError, match="ambiguous"):
        service.execute_delete(service.confirmation_for(journal), now=_INSTANT)

    assert capsule.is_dir()
    assert untouched.read_bytes() == b"unrelated"


def test_delete_refuses_confirmation_for_a_different_preflight_target(tmp_path: Path) -> None:
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    confirmation = service.confirmation_for(journal).model_copy(update={"challenge": "f" * 64})

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="not bound"):
        service.execute_delete(confirmation, now=_INSTANT)


def test_journal_rejects_noncanonical_durable_bytes(tmp_path: Path) -> None:
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    service._repository.journal_path(journal.transaction_id).write_bytes(b'{"state":"delete_prepared"}')

    with pytest.raises(ProfileCustodyTransactionCorruptError, match="invalid"):
        service._repository.load_journal(journal.transaction_id)


def test_repository_refuses_real_link_roots_and_leaves(tmp_path: Path) -> None:
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside")
    leaf = service._repository.journal_path(journal.transaction_id)
    leaf.unlink()
    os.symlink(outside, leaf)

    with pytest.raises(ProfileCustodyTransactionCorruptError, match="opened"):
        service._repository.load_journal(journal.transaction_id)

    assert outside.read_bytes() == b"outside"


def test_pointer_capture_and_cas_refuse_a_real_pointer_link(tmp_path: Path) -> None:
    outside = tmp_path / "outside-pointer"
    outside.write_text(
        BucketPointer.selected(bucket_id=str(_PROFILE_ID), transition_revision=1).to_toml(), encoding="utf-8"
    )
    os.symlink(outside, tmp_path / "active-profile")

    with pytest.raises(OSError, match=r"link|reparse|symbolic"):
        _observe_pointer(tmp_path)

    assert outside.read_text(encoding="utf-8") == BucketPointer.selected(
        bucket_id=str(_PROFILE_ID), transition_revision=1
    ).to_toml()


def test_journal_writer_refuses_an_existing_leaf_and_never_overwrites_it(tmp_path: Path) -> None:
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    transaction_id = uuid4()
    service._repository._ensure_root(service._repository._journal_root, "custody transaction journal")
    target = service._repository.journal_path(transaction_id)
    target.write_bytes(b"preexisting")

    with pytest.raises(ProfileCustodyTransactionCorruptError, match="exclusively"):
        service.prepare_delete(profile_id=_PROFILE_ID, transaction_id=transaction_id, now=_INSTANT)

    assert target.read_bytes() == b"preexisting"


@pytest.mark.os_keychain
def test_delete_owner_receipts_are_durable_and_idempotent(tmp_path: Path) -> None:
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    session_path = _persist_real_current_session_acceleration(tmp_path)
    assert session_path.is_file()
    live_session = BucketSession.open(
        bucket_id=str(_PROFILE_ID),
        kek=b"k" * 32,
        dek=bytes(range(32)),
        idle_minutes=15,
        absolute_minutes=240,
        opened_at=_INSTANT,
        storage_root=tmp_path,
    )
    bind_active_bucket_session(live_session)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)
    receipt = service.execute_delete(service.confirmation_for(journal), now=_INSTANT)

    assert receipt.transaction_id == journal.transaction_id
    process_receipt = service._repository.load_owner_receipt(journal.transaction_id, "process-secret-revocation")
    acceleration_receipt = service._repository.load_owner_receipt(journal.transaction_id, "local-session-acceleration")
    assert process_receipt is not None and process_receipt.effect == "revoked"
    assert acceleration_receipt is not None and acceleration_receipt.effect == "removed"
    assert service.execute_delete(service.confirmation_for(journal), now=_INSTANT) == receipt
    assert not session_path.exists()
    assert live_session.sealed is True
    assert current_active_bucket_session() is None


@pytest.mark.os_keychain
def test_create_orchestration_journals_stages_verifies_and_publishes_pointer_last(tmp_path: Path) -> None:
    service = ProfileCustodyTransactionService(root=tmp_path)
    transaction_id = uuid4()
    envelope, sentinel, data_files = _create_capsule_input()
    assert _observe_pointer(tmp_path).bucket_id is None

    receipt = service.create_capsule(
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        label="Custody operator",
        publication_kind="restore",
        transaction_id=transaction_id,
        now=_INSTANT,
    )

    assert receipt.pointer_published is True
    assert receipt.pointer_cleared is False
    assert _observe_pointer(tmp_path).bucket_id == str(_PROFILE_ID)
    journal = service._repository.load_journal(transaction_id)
    assert journal.state is ProfileCustodyTransactionState.COMPLETE
    assert journal.proposed_generation == envelope.password_generation
    assert journal.proposed_custody_digest == receipt.inventory.digest
    assert journal.label == "Custody operator"
    assert load_committed_profile_custody_label_record(_PROFILE_ID, root=tmp_path).label == "Custody operator"
    assert not hasattr(service, "prepare_create")


def test_create_orchestration_refuses_custody_material_for_another_profile(tmp_path: Path) -> None:
    service = ProfileCustodyTransactionService(root=tmp_path)
    envelope, sentinel, data_files = _create_capsule_input(profile_id=_OTHER_PROFILE_ID)

    with pytest.raises(ProfileCustodyTransactionRefusalError, match="target profile"):
        service.create_capsule(
            profile_id=_PROFILE_ID,
            password_envelope=envelope,
            sentinel=sentinel,
            data_files=data_files,
            label="Other profile",
            now=_INSTANT,
        )


@pytest.mark.parametrize("boundary", ("intent", "stage", "verify", "rename"))
def test_create_recovery_after_real_subprocess_crash_at_each_durable_boundary(
    tmp_path: Path,
    boundary: str,
) -> None:
    """Recovery owns intent, stage, verified, and renamed bytes after process death."""
    transaction_id = uuid4()
    context = get_context("spawn")
    child = context.Process(
        target=_crash_create_at_durable_boundary,
        args=(str(tmp_path), str(transaction_id), boundary),
    )
    child.start()
    child.join(30)
    assert child.exitcode == 97

    receipt = ProfileCustodyTransactionService(root=tmp_path).recover_create(transaction_id, now=_INSTANT)
    journal = ProfileCustodyTransactionService(root=tmp_path)._repository.load_journal(transaction_id)
    if boundary == "intent":
        assert receipt is None
        assert journal.state is ProfileCustodyTransactionState.ROLLED_BACK
        assert _observe_pointer(tmp_path).bucket_id is None
        return
    assert receipt is not None
    assert receipt.pointer_published is True
    assert journal.state is ProfileCustodyTransactionState.COMPLETE
    assert _observe_pointer(tmp_path).bucket_id == str(_PROFILE_ID)
    assert load_committed_profile_custody_label_record(_PROFILE_ID, root=tmp_path).label == "crash label"


def test_create_recovery_refuses_a_label_claimed_while_its_real_stage_waited(tmp_path: Path) -> None:
    """A delayed recovery cannot make a staged duplicate label visible."""
    transaction_id = uuid4()
    context = get_context("spawn")
    child = context.Process(
        target=_crash_create_at_durable_boundary,
        args=(str(tmp_path), str(transaction_id), "stage"),
    )
    child.start()
    child.join(30)
    assert child.exitcode == 97

    envelope, sentinel, data_files = _create_capsule_input(profile_id=_OTHER_PROFILE_ID)
    ProfileCustodyTransactionService(root=tmp_path).create_capsule(
        profile_id=_OTHER_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        label="CRASH LABEL",
        publication_kind="restore",
        now=_INSTANT,
    )

    with pytest.raises(ProfileCustodyTransactionConflictError, match="label"):
        ProfileCustodyTransactionService(root=tmp_path).recover_create(transaction_id, now=_INSTANT)

    assert list_current_profile_custody_capsule_ids(root=tmp_path) == (_OTHER_PROFILE_ID,)
    assert profile_custody_staging_path(
        profile_id=_PROFILE_ID,
        transaction_id=transaction_id,
        root=tmp_path,
    ).is_dir()


def test_create_recovery_refuses_a_journal_label_not_bound_to_its_real_stage(tmp_path: Path) -> None:
    """Journal bytes cannot relabel a previously durable stage during recovery."""
    transaction_id = uuid4()
    context = get_context("spawn")
    child = context.Process(
        target=_crash_create_at_durable_boundary,
        args=(str(tmp_path), str(transaction_id), "stage"),
    )
    child.start()
    child.join(30)
    assert child.exitcode == 97

    service = ProfileCustodyTransactionService(root=tmp_path)
    journal = service._repository.load_journal(transaction_id)
    service._repository.save_journal(journal.with_update(label="another operator", updated_at=_INSTANT))

    with pytest.raises(ProfileCustodyTransactionConflictError, match="label"):
        service.recover_create(transaction_id, now=_INSTANT)

    assert list_current_profile_custody_capsule_ids(root=tmp_path) == ()
    assert profile_custody_staging_path(
        profile_id=_PROFILE_ID,
        transaction_id=transaction_id,
        root=tmp_path,
    ).is_dir()


def test_create_root_lock_serializes_duplicate_labels_across_real_processes(tmp_path: Path) -> None:
    """Two independently scheduled creates expose at most one matching label."""
    context = get_context("spawn")
    result_queue = context.Queue()
    barrier = context.Barrier(2)
    first = context.Process(
        target=_create_labeled_capsule_in_sibling,
        args=(str(tmp_path), str(_PROFILE_ID), "Same label", result_queue, barrier),
    )
    second = context.Process(
        target=_create_labeled_capsule_in_sibling,
        args=(str(tmp_path), str(_OTHER_PROFILE_ID), "same LABEL", result_queue, barrier),
    )
    first.start()
    second.start()
    first.join(30)
    second.join(30)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert sorted((result_queue.get(timeout=5), result_queue.get(timeout=5))) == ["collision", "published"]
    visible = list_current_profile_custody_capsule_ids(root=tmp_path)
    assert len(visible) == 1
    assert load_committed_profile_custody_label_record(visible[0], root=tmp_path).label.casefold() == "same label"


def test_publish_once_has_one_sibling_process_winner_and_never_overwrites(tmp_path: Path) -> None:
    """The Windows CREATE_NEW path is exercised by two independent interpreters."""
    parent = tmp_path / "local-records"
    target = parent / "once.json"
    context = get_context("spawn")
    result_queue = context.Queue()
    first = context.Process(target=_publish_once_in_sibling, args=(str(target), b"first", result_queue))
    second = context.Process(target=_publish_once_in_sibling, args=(str(target), b"second", result_queue))
    first.start()
    second.start()
    first.join(20)
    second.join(20)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert sorted((result_queue.get(timeout=5), result_queue.get(timeout=5))) == ["collision", "published"]
    assert target.read_bytes() in {b"first", b"second"}


def test_transaction_lock_serializes_siblings_and_releases_after_process_death(tmp_path: Path) -> None:
    """Root-before-profile locking is kernel-owned, cross-process, and non-stale."""
    _committed_capsule(tmp_path)
    context = get_context("spawn")
    first_release = context.Event()
    second_release = context.Event()
    result_queue = context.Queue()
    first = context.Process(
        target=_hold_transaction_lock_in_sibling,
        args=(str(tmp_path), str(_PROFILE_ID), first_release, result_queue),
    )
    second = context.Process(
        target=_hold_transaction_lock_in_sibling,
        args=(str(tmp_path), str(_OTHER_PROFILE_ID), second_release, result_queue),
    )
    first.start()
    try:
        assert result_queue.get(timeout=20) == "ready"
        assert result_queue.get(timeout=20) == "locked"

        # The exclusion window opens only after the sibling reports itself
        # ready, so it measures the LOCK rather than the seconds a spawned
        # interpreter spends importing before it can even attempt one. Timed
        # from `second.start()` this assertion was satisfied by startup latency
        # and passed with the root lock removed entirely.
        second.start()
        assert result_queue.get(timeout=20) == "ready"
        with pytest.raises(Empty):
            result_queue.get(timeout=2.0)

        first.terminate()
        first.join(10)
        assert first.exitcode is not None and first.exitcode != 0
        assert result_queue.get(timeout=20) == "locked"
        second_release.set()
        second.join(10)
        assert second.exitcode == 0
    finally:
        if first.is_alive():
            first.kill()
            first.join(10)
        if second.is_alive():
            second.kill()
            second.join(10)


def test_pointer_transition_and_active_pointer_writer_share_one_root_lock(tmp_path: Path) -> None:
    """A sibling cannot slip between a transaction observation and transition."""
    _committed_capsule(tmp_path)
    original = _select_pointer(tmp_path, str(_PROFILE_ID))
    context = get_context("spawn")
    result_queue = context.Queue()
    writer = context.Process(
        target=_write_active_pointer_in_sibling,
        args=(str(tmp_path), str(_OTHER_PROFILE_ID), result_queue),
    )

    try:
        with profile_custody_transaction_lock(tmp_path, _PROFILE_ID):
            captured = _observe_pointer(tmp_path)
            writer.start()

            # Opened only after the sibling reports ready: timed from start()
            # this window closed before a spawned interpreter could finish
            # importing, so it passed with the root lock removed entirely and
            # proved nothing about exclusion.
            assert result_queue.get(timeout=20) == "ready"
            with pytest.raises(Empty):
                result_queue.get(timeout=2.0)
            assert captured == original
            _clear_expected_pointer(tmp_path, captured)

        assert result_queue.get(timeout=20) == "written"
        writer.join(10)
        assert writer.exitcode == 0
        replacement = _observe_pointer(tmp_path)
        assert replacement.bucket_id == str(_OTHER_PROFILE_ID)
        with (
            active_profile_pointer_transaction(tmp_path) as transaction,
            pytest.raises(ActiveProfilePointerTransactionError),
        ):
            transaction.compare_and_restore(
                expected=captured,
                captured=BucketPointer.absent(transition_revision=0),
            )
        assert _observe_pointer(tmp_path) == replacement
    finally:
        if writer.is_alive():
            writer.kill()
            writer.join(10)


def test_transaction_lock_refuses_a_real_reparse_capsule_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, tmp_path / "buckets", target_is_directory=True)

    with (
        pytest.raises(ProfileCustodyTransactionCorruptError, match="lock root"),
        profile_custody_transaction_lock(tmp_path, _PROFILE_ID),
    ):
        pytest.fail("a reparse capsule root must never be locked")

    assert not (outside / f".profile-custody-{_PROFILE_ID}.lock").exists()


@pytest.mark.os_keychain
def test_owner_receipts_resume_after_owner_effect_precedes_journal_state(tmp_path: Path) -> None:
    """A real owner effect survives a crash before its enclosing state update."""
    _committed_capsule(tmp_path)
    service = ProfileCustodyTransactionService(root=tmp_path)
    _authorise_clear_hold(service)
    session_path = _persist_real_current_session_acceleration(tmp_path)
    journal = service.prepare_delete(profile_id=_PROFILE_ID, now=_INSTANT)

    service._revoke_process_secrets(journal, _INSTANT)
    process_receipt = service._repository.load_owner_receipt(journal.transaction_id, "process-secret-revocation")
    assert process_receipt is not None and process_receipt.effect == "verified_absent"

    receipt = service.execute_delete(service.confirmation_for(journal), now=_INSTANT)

    assert receipt.transaction_id == journal.transaction_id
    assert not session_path.exists()
