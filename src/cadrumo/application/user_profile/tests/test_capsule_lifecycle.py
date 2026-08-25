"""Real filesystem contracts for the committed-capsule lifecycle surface."""

from __future__ import annotations

from base64 import b64encode
from functools import lru_cache
from hashlib import sha256
from multiprocessing import get_context
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyCapsuleLabel,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyRecordError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
    ProfileCustodySentinelRecord,
    ProfileCustodyWrappedDek,
    ProfileLabelHeadRepository,
    create_profile_custody_sentinel,
    load_committed_profile_custody_label_record,
    replace_committed_profile_custody_data_file,
)
from ....core import read_pointer
from ....domain.buckets import BucketEventType
from ....domain.user_profile import (
    ProfileNotFoundError,
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from ....tests.user_profile import complete_profile_facts
from .._capsule_record import ProfileRecordConflictError, ProfileRecordSession, ProfileRecordStore
from .._custody_ports import ProfileCustodyRecoveryEnvelopePort
from .._custody_repository import profile_custody_transaction_lock
from .._custody_transactions import ProfileCustodyTransactionConflictError
from .._lifecycle import ProfileCapsuleLifecycle
from .._profile_record_repository import ProfileRecordRepository, bound_profile_record_session
from .._profile_repository import CommittedProfileRepository
from .._recovery_custody import mint_profile_creation_recovery

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("327b296d-8377-4be0-b13a-ca4d8f692e1d")


def _current_capsule_input(
    *,
    profile_id: UUID = _PROFILE_ID,
) -> tuple[ProfileCustodyEnvelope, ProfileCustodySentinelRecord, dict[str, bytes], bytes]:
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
    dek = bytes(range(32))
    return (
        envelope,
        create_profile_custody_sentinel(envelope=envelope, dek=dek),
        {"state/payload.bin": b"x"},
        dek,
    )


@lru_cache
def _recovery_envelope(profile_id: UUID, dek_epoch: str) -> ProfileCustodyRecoveryEnvelopePort:
    """Mint one real recovery wrapper for lifecycle tests not about its secret."""
    enrollment = mint_profile_creation_recovery(
        profile_id=profile_id,
        dek=bytes(range(32)),
        dek_epoch=dek_epoch,
    )
    with enrollment.recovery_key:
        return enrollment.envelope


def _crash_between_label_record_and_head(root_text: str, profile_id_text: str) -> None:
    """Durably replace the label after its pending head witness, then terminate."""
    from ....tests.profile_persistence import composed_profile_persistence_ports

    root = Path(root_text)
    profile_id = UUID(profile_id_text)
    with composed_profile_persistence_ports(), profile_custody_transaction_lock(root, profile_id):
        current = load_committed_profile_custody_label_record(profile_id, root=root)
        heads = ProfileLabelHeadRepository(root=root)
        current_head = heads.recover_advance(profile_id=profile_id, current_label=current)
        replacement = ProfileCustodyCapsuleLabel.create(
            profile_id=profile_id,
            label="Recovered after crash",
            label_revision=current.label_revision + 1,
            previous_label_digest=current.content_digest,
        )
        heads.begin_advance(
            current_head=current_head,
            current_label=current,
            replacement_label=replacement,
        )
        replace_committed_profile_custody_data_file(
            profile_id,
            "profile-label.v1.json",
            replacement.canonical_json_bytes(),
            expected_sha256=f"sha256:{sha256(current.canonical_json_bytes()).hexdigest()}",
            root=root,
        )
    raise SystemExit(97)


def test_lifecycle_projects_only_its_committed_capsule_and_owns_selection(tmp_path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    service = ProfileCapsuleLifecycle(root=tmp_path)

    record_session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    created = service.create(
        label="Capsule operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        initial_record=UserProfileRecord(profile_id=str(_PROFILE_ID), setup_state=ProfileSetupState.INCOMPLETE),
        record_session=record_session,
    )

    assert created.profile_id == str(_PROFILE_ID)
    assert created.label == "Capsule operator"
    assert CommittedProfileRepository(root=tmp_path).list() == (created,)
    assert service.select("Capsule operator") == created
    pointer = read_pointer(tmp_path)
    assert pointer.bucket_id == str(_PROFILE_ID)
    assert (tmp_path / "buckets" / str(_PROFILE_ID) / "db" / "cadrumo.db").is_file()
    with bound_profile_record_session(record_session):
        assert ProfileRecordRepository.for_current_session(_PROFILE_ID, root=tmp_path).load(
            _PROFILE_ID
        ).profile_id == str(_PROFILE_ID)


def test_enrollment_publication_requires_a_recovery_envelope_argument(tmp_path) -> None:
    """The lifecycle signature has no password-only creation lane."""
    envelope, sentinel, data_files, dek = _current_capsule_input()
    record_session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    try:
        with pytest.raises(TypeError, match="recovery_envelope"):
            ProfileCapsuleLifecycle(root=tmp_path).create(
                label="Recovery invariant operator",
                profile_id=_PROFILE_ID,
                password_envelope=envelope,
                sentinel=sentinel,
                data_files=data_files,
                initial_record=UserProfileRecord(profile_id=str(_PROFILE_ID), setup_state=ProfileSetupState.INCOMPLETE),
                record_session=record_session,
            )
    finally:
        record_session.close()

    assert not (tmp_path / "buckets" / str(_PROFILE_ID)).exists()


def test_enrollment_publication_refuses_explicit_none_without_a_capsule(tmp_path) -> None:
    """Runtime callers cannot bypass the mandatory type with explicit None."""
    envelope, sentinel, data_files, dek = _current_capsule_input()
    record_session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    try:
        with pytest.raises(ValueError, match="requires creation recovery material"):
            ProfileCapsuleLifecycle(root=tmp_path).create(
                label="Explicit None recovery",
                profile_id=_PROFILE_ID,
                password_envelope=envelope,
                sentinel=sentinel,
                data_files=data_files,
                recovery_envelope=None,  # type: ignore[arg-type] - runtime bypass probe
                initial_record=UserProfileRecord(profile_id=str(_PROFILE_ID), setup_state=ProfileSetupState.INCOMPLETE),
                record_session=record_session,
            )
    finally:
        record_session.close()

    assert not (tmp_path / "buckets" / str(_PROFILE_ID)).exists()


def test_repository_refuses_retired_bucket_directories_without_treating_them_as_profiles(tmp_path) -> None:
    retired = tmp_path / "buckets" / str(_PROFILE_ID)
    retired.mkdir(parents=True)
    (retired / "manifest.toml").write_text("label = 'Retired'\n", encoding="utf-8")

    repository = CommittedProfileRepository(root=tmp_path)

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        repository.list()
    assert captured.value.refusal is ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED


def test_complete_setup_cas_replaces_only_the_current_authenticated_record(tmp_path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    record_session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    service = ProfileCapsuleLifecycle(root=tmp_path)
    service.create(
        label="CAS operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        # The subject carries a complete answer set because promotion now
        # judges the record against the contract COMPLETE claims. This test is
        # about the compare-and-swap, so its subject has to be a record that
        # promotion would legitimately accept; an empty one would fail here for
        # the promotion door's reason rather than this test's.
        initial_record=UserProfileRecord(
            profile_id=str(_PROFILE_ID),
            facts=complete_profile_facts(load_user_profile_schema()),
            setup_state=ProfileSetupState.INCOMPLETE,
        ),
        record_session=record_session,
    )

    with bound_profile_record_session(record_session):
        repository = ProfileRecordRepository.for_current_session(_PROFILE_ID, root=tmp_path)
        initial = repository.load(_PROFILE_ID)
        completed = repository.complete_setup(
            _PROFILE_ID,
            expected_revision=initial.record_revision,
            expected_content_digest=initial.content_digest,
        )
        reloaded = repository.load(_PROFILE_ID)
        assert completed.setup_state is ProfileSetupState.COMPLETE
        assert reloaded.setup_state is ProfileSetupState.COMPLETE
        assert reloaded.record_revision == initial.record_revision + 1
        assert reloaded.previous_record_digest == initial.content_digest
        persisted = ProfileRecordStore(session=record_session, root=tmp_path).load()
        assert persisted.previous_row_revision_id is not None
        with pytest.raises(ProfileRecordConflictError):
            repository.complete_setup(
                _PROFILE_ID,
                expected_revision=initial.record_revision,
                expected_content_digest=initial.content_digest,
            )


def test_fact_command_cas_publishes_the_record_and_authenticated_event_together(tmp_path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    record_session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    ProfileCapsuleLifecycle(root=tmp_path).create(
        label="Fact command operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        initial_record=UserProfileRecord(profile_id=str(_PROFILE_ID), setup_state=ProfileSetupState.INCOMPLETE),
        record_session=record_session,
    )

    with bound_profile_record_session(record_session):
        repository = ProfileRecordRepository.for_current_session(_PROFILE_ID, root=tmp_path)
        initial = repository.load(_PROFILE_ID)
        updated = repository.apply_fact_changes(
            _PROFILE_ID,
            facts=(*initial.facts, UserProfileFact(path="identity.tax_id", value="12345678Z")),
            expected_revision=initial.record_revision,
            expected_content_digest=initial.content_digest,
            event_type=BucketEventType.CENSO_APPLIED,
            event_payload={"adopted_count": "1", "divergence_count": "0"},
        )
        persisted = ProfileRecordStore(session=record_session, root=tmp_path).load()
        assert persisted.record == updated
        assert persisted.event_id
        history = ProfileRecordStore(session=record_session, root=tmp_path).history()
        assert [event.event_type for event in history] == [
            BucketEventType.PROFILE_BUCKET_CREATED,
            BucketEventType.CENSO_APPLIED,
        ]
        assert history[-1].event_id == persisted.event_id


def test_public_facade_exposes_no_transaction_service_or_generic_record_replace() -> None:
    """Only the lifecycle and explicit record commands expose write operations."""
    from ... import user_profile as public_user_profile

    assert not hasattr(public_user_profile, "ProfileCustodyTransactionService")
    assert not hasattr(ProfileCapsuleLifecycle, "replace_current_record")
    assert hasattr(ProfileRecordRepository, "complete_setup")
    assert hasattr(ProfileRecordRepository, "apply_fact_changes")


def test_label_provenance_is_uuid_bound_and_revisioned_at_create(tmp_path: Path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    lifecycle = ProfileCapsuleLifecycle(root=tmp_path)
    lifecycle.create(
        label="Original operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        initial_record=UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=str(_PROFILE_ID)),
        record_session=session,
    )
    initial = load_committed_profile_custody_label_record(_PROFILE_ID, root=tmp_path)
    assert initial.profile_id == _PROFILE_ID
    assert initial.label_revision == 1
    assert initial.previous_label_digest is None
    assert (
        initial.canonical_json_bytes()
        == (tmp_path / "buckets" / str(_PROFILE_ID) / "data" / "profile-label.v1.json").read_bytes()
    )


def test_label_provenance_refuses_a_same_uuid_canonical_substitution(tmp_path: Path) -> None:
    other_profile_id = UUID("57c9594e-65de-470b-b768-4a4dd1323597")
    label_records: list[tuple[UUID, ProfileCustodyCapsuleLabel]] = []
    for profile_id, label in ((_PROFILE_ID, "First operator"), (other_profile_id, "Second operator")):
        envelope, sentinel, data_files, dek = _current_capsule_input(profile_id=profile_id)
        session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
        ProfileCapsuleLifecycle(root=tmp_path).create(
            label=label,
            profile_id=profile_id,
            password_envelope=envelope,
            sentinel=sentinel,
            data_files=data_files,
            recovery_envelope=_recovery_envelope(profile_id, envelope.dek_epoch),
            initial_record=UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=str(profile_id)),
            record_session=session,
        )
        label_records.append((profile_id, load_committed_profile_custody_label_record(profile_id, root=tmp_path)))

    first_id, _ = label_records[0]
    second_id, _ = label_records[1]
    first_path = tmp_path / "buckets" / str(first_id) / "data" / "profile-label.v1.json"
    second_path = tmp_path / "buckets" / str(second_id) / "data" / "profile-label.v1.json"
    first_path.write_bytes(second_path.read_bytes())
    with pytest.raises(ProfileCustodyRecordError, match="UUID"):
        load_committed_profile_custody_label_record(first_id, root=tmp_path)


def test_locked_label_read_refuses_a_fresh_canonical_same_uuid_substitution(tmp_path: Path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    ProfileCapsuleLifecycle(root=tmp_path).create(
        label="Trusted operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        initial_record=UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=str(_PROFILE_ID)),
        record_session=session,
    )
    original = load_committed_profile_custody_label_record(_PROFILE_ID, root=tmp_path)
    label_path = tmp_path / "buckets" / str(_PROFILE_ID) / "data" / "profile-label.v1.json"
    label_path.write_bytes(
        ProfileCustodyCapsuleLabel.create(
            profile_id=_PROFILE_ID,
            label="Freshly canonical forgery",
            label_revision=original.label_revision + 1,
            previous_label_digest=original.content_digest,
        ).canonical_json_bytes()
    )
    with pytest.raises(ProfileCustodyTransactionConflictError, match="trusted head"):
        CommittedProfileRepository(root=tmp_path).load(_PROFILE_ID)


def test_real_crash_between_label_and_head_recovers_the_durable_advance(tmp_path: Path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    ProfileCapsuleLifecycle(root=tmp_path).create(
        label="Crash boundary operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        initial_record=UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=str(_PROFILE_ID)),
        record_session=session,
    )
    before = CommittedProfileRepository(root=tmp_path).load(_PROFILE_ID)
    child = get_context("spawn").Process(
        target=_crash_between_label_record_and_head,
        args=(str(tmp_path), str(_PROFILE_ID)),
    )
    child.start()
    child.join(30)
    assert child.exitcode == 97

    recovered = CommittedProfileRepository(root=tmp_path).load(_PROFILE_ID)
    recovered_head = ProfileLabelHeadRepository(root=tmp_path).load_current(_PROFILE_ID)
    assert recovered.label == "Recovered after crash"
    assert recovered.label_revision == before.label_revision + 1
    assert recovered.label_source_witness == recovered_head.self_digest
    assert recovered_head.source_witness == before.label_source_witness
    assert not (tmp_path / "profile-custody-label-heads" / f".{_PROFILE_ID}.pending.json").exists()


def test_committed_profile_view_keeps_facts_locked_until_the_current_session_authenticates(tmp_path: Path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    ProfileCapsuleLifecycle(root=tmp_path).create(
        label="Locked view operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        recovery_envelope=_recovery_envelope(_PROFILE_ID, envelope.dek_epoch),
        initial_record=UserProfileRecord(
            profile_id=str(_PROFILE_ID),
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            setup_state=ProfileSetupState.INCOMPLETE,
        ),
        record_session=session,
    )
    repository = CommittedProfileRepository(root=tmp_path)
    locked = repository.load(_PROFILE_ID)
    assert locked.fact_summary.availability == "UNAVAILABLE_LOCKED"
    assert locked.fact_summary.fact_count == 0
    assert locked.label_revision == 1
    assert locked.label_content_digest
    assert locked.label_self_digest
    assert locked.label_source_witness
    with pytest.raises(ProfileNotFoundError, match="authenticated session"):
        repository.load_unlocked(_PROFILE_ID)
    with bound_profile_record_session(session):
        unlocked = repository.load_unlocked(_PROFILE_ID)
    assert unlocked.fact_summary.availability == "AVAILABLE_UNLOCKED"
    assert unlocked.fact_summary.setup_state is ProfileSetupState.INCOMPLETE
    assert unlocked.fact_summary.fact_count == 1
    assert unlocked.fact_summary.record_revision == 1
    assert unlocked.fact_summary.content_digest
    assert unlocked.label_revision == locked.label_revision
    assert unlocked.label_content_digest == locked.label_content_digest
    assert unlocked.label_self_digest == locked.label_self_digest
    assert unlocked.label_source_witness == locked.label_source_witness
