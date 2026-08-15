"""Real filesystem contracts for current profile-custody capsule publication."""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ......core import StorageCategory, scan_directory
from ......core.config import Settings
from .. import (
    ProfileCustodyCapsuleLabel,
    ProfileCustodyCommit,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyRecordError,
    ProfileCustodyRecoveryArtifact,
    ProfileCustodyRecoveryEnvelope,
    ProfileCustodyRecoveryGuidance,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
    ProfileCustodyWrappedDek,
    create_profile_custody_password_envelope,
    create_profile_custody_recovery_envelope,
    create_profile_custody_sentinel,
    detect_retired_profile_custody_member_paths,
    export_profile_custody_recovery_artifact,
    import_profile_custody_recovery_artifact,
    list_current_profile_custody_capsule_ids,
    load_committed_profile_password_material,
    parse_profile_custody_commit,
    parse_profile_custody_recovery_artifact,
    parse_profile_custody_recovery_envelope,
    profile_custody_path,
    publish_profile_custody_capsule,
    recognize_current_profile_capsule,
    unlock_imported_profile_custody_recovery_artifact,
    unlock_profile_custody,
    unlock_profile_custody_recovery,
    verify_profile_custody_sentinel,
)
from .._recovery import PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("327b296d-8377-4be0-b13a-ca4d8f692e1d")
_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")
_PASSPHRASE = "profile " + "password" + " 123"
_RECOVERY_SECRET = "profile " + "recovery" + " 123"


def _settings(tmp_path: Path) -> Settings:
    return Settings(cadrumo_local_storage_root=tmp_path)


def _kdf() -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
        output_bytes=32,
    )


def _wrapped_dek() -> ProfileCustodyWrappedDek:
    return ProfileCustodyWrappedDek(
        nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
        ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
        tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
    )


def _password_envelope(*, profile_id: UUID = _PROFILE_ID, dek_epoch: str = _EPOCH) -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=dek_epoch,
        kdf=_kdf(),
        wrapped_dek=_wrapped_dek(),
    )


def _recovery_envelope(*, profile_id: UUID = _PROFILE_ID, dek_epoch: str = _EPOCH) -> ProfileCustodyRecoveryEnvelope:
    return ProfileCustodyRecoveryEnvelope.create(
        profile_id=profile_id,
        recovery_generation=1,
        dek_epoch=dek_epoch,
        kdf=_kdf(),
        wrapped_dek=_wrapped_dek(),
    )


def test_supervised_password_recovery_and_artifact_paths_prove_the_same_dek(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    recovery = create_profile_custody_recovery_envelope(
        profile_id=_PROFILE_ID,
        recovery_secret=_RECOVERY_SECRET,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    artifact_path = tmp_path / "recovery-export.json"
    receipt = export_profile_custody_recovery_artifact(
        recovery,
        current_password=_PASSPHRASE,
        password_envelope=envelope,
        sentinel=sentinel,
        target=artifact_path,
        settings=settings,
    )
    artifact = receipt.artifact

    assert parse_profile_custody_recovery_envelope(recovery.canonical_json_bytes()) == recovery
    assert receipt.warnings
    assert parse_profile_custody_recovery_artifact(artifact_path.read_bytes()) == artifact
    assert (
        import_profile_custody_recovery_artifact(
            artifact_path,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
        )
        == artifact
    )
    assert unlock_profile_custody(envelope, _PASSPHRASE, sentinel=sentinel, settings=settings).dek == _DEK
    assert (
        unlock_profile_custody_recovery(
            recovery,
            _RECOVERY_SECRET,
            sentinel=sentinel,
            settings=settings,
        ).dek
        == _DEK
    )
    assert (
        unlock_imported_profile_custody_recovery_artifact(
            artifact,
            _RECOVERY_SECRET,
            sentinel=sentinel,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
            settings=settings,
        ).dek
        == _DEK
    )
    with pytest.raises(ProfileCustodyRecordError, match="created exclusively"):
        export_profile_custody_recovery_artifact(
            recovery,
            current_password=_PASSPHRASE,
            password_envelope=envelope,
            sentinel=sentinel,
            target=artifact_path,
            settings=settings,
        )
    with pytest.raises(ProfileCustodyRecordError, match="UUID or DEK epoch"):
        import_profile_custody_recovery_artifact(
            artifact_path,
            expected_profile_id=uuid4(),
            expected_dek_epoch=_EPOCH,
        )


def test_recovery_artifact_refuses_unknown_noncanonical_and_foreign_members() -> None:
    artifact = ProfileCustodyRecoveryArtifact.from_recovery_envelope(_recovery_envelope())
    canonical = artifact.canonical_json_bytes()
    unknown = canonical.replace(b"{", b'{"unexpected":true,', 1)
    reordered = json.dumps(dict(reversed(tuple(json.loads(canonical).items()))), separators=(",", ":")).encode("utf-8")

    for value in (unknown, reordered):
        with pytest.raises(ProfileCustodyRecordError):
            parse_profile_custody_recovery_artifact(value)


def test_recovery_artifact_import_refuses_real_parent_and_leaf_reparse_nonregular_and_oversize_paths(
    tmp_path: Path,
) -> None:
    artifact = ProfileCustodyRecoveryArtifact.from_recovery_envelope(_recovery_envelope())
    source_parent = tmp_path / "source"
    source_parent.mkdir()
    source = source_parent / "recovery.json"
    source.write_bytes(artifact.canonical_json_bytes())

    assert (
        import_profile_custody_recovery_artifact(
            source,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
        )
        == artifact
    )

    linked_parent = tmp_path / "linked-parent"
    os.symlink(source_parent, linked_parent, target_is_directory=True)
    with pytest.raises(ProfileCustodyRecordError, match=r"safe existing directory|unavailable|reparse"):
        import_profile_custody_recovery_artifact(
            linked_parent / source.name,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
        )

    linked_leaf = source_parent / "linked-leaf.json"
    os.symlink(source, linked_leaf)
    with pytest.raises(ProfileCustodyRecordError, match=r"unavailable|non-reparse"):
        import_profile_custody_recovery_artifact(
            linked_leaf,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
        )

    nonregular = source_parent / "directory.json"
    nonregular.mkdir()
    with pytest.raises(ProfileCustodyRecordError, match=r"unavailable|regular|non-reparse"):
        import_profile_custody_recovery_artifact(
            nonregular,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
        )

    oversize = source_parent / "oversize.json"
    oversize.write_bytes(b"x" * (PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES + 1))
    with pytest.raises(ProfileCustodyRecordError, match="bounded regular"):
        import_profile_custody_recovery_artifact(
            oversize,
            expected_profile_id=_PROFILE_ID,
            expected_dek_epoch=_EPOCH,
        )


def test_committed_capsule_is_published_once_with_immutable_marker_and_password_only_read_set(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    recovery = create_profile_custody_recovery_envelope(
        profile_id=_PROFILE_ID,
        recovery_secret=_RECOVERY_SECRET,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    published_at = datetime(2026, 8, 13, 12, 34, 56, 123456, tzinfo=UTC)

    capsule = publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=UUID("4f28d1c4-e466-4a08-a25a-ea5925146f36"),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=sentinel,
        recovery_envelope=recovery,
        data_files={"state/current.bin": b"current encrypted payload"},
        settings=settings,
        published_at=published_at,
    )

    marker = parse_profile_custody_commit((capsule / "profile.commit.v1.json").read_bytes())
    assert marker.profile_id == _PROFILE_ID
    assert marker.published_at == "2026-08-13T12:34:56.123456Z"
    assert recognize_current_profile_capsule(_PROFILE_ID, settings=settings) == capsule
    recovery_path = capsule / "custody" / "recovery.v1.json"
    recovery_path.unlink()
    recovery_path.mkdir()
    recovery_accesses: list[str] = []

    def observe_open(event: str, arguments: tuple[object, ...]) -> None:
        if event == "open" and arguments and isinstance(arguments[0], str) and Path(arguments[0]) == recovery_path:
            recovery_accesses.append("audit-open")

    def observe_filesystem_calls(frame: object, event: str, argument: object) -> None:
        if event != "c_call" or getattr(argument, "__name__", "") not in {"stat", "lstat", "open", "read"}:
            return
        local_values = getattr(frame, "f_locals", {}).values()
        if any(isinstance(value, Path) and value == recovery_path for value in local_values):
            recovery_accesses.append(getattr(argument, "__name__", "unknown"))

    # This observes the process's actual open audit stream, independently of
    # the custody receipt.  The profile hook also observes C-level stat/open/
    # read calls made by real filesystem code with a recovery path local.
    # The recovery path is deliberately a directory, so an accidental ordinary
    # file open is also a hard real-FS error.
    sys.addaudithook(observe_open)
    previous_profile = sys.getprofile()
    sys.setprofile(observe_filesystem_calls)
    try:
        password_material = load_committed_profile_password_material(_PROFILE_ID, settings=settings)
        assert (
            unlock_profile_custody(
                password_material.envelope,
                _PASSPHRASE,
                sentinel=password_material.sentinel,
                settings=settings,
            ).dek
            == _DEK
        )
    finally:
        sys.setprofile(previous_profile)
    assert password_material.envelope == envelope
    assert password_material.sentinel == sentinel
    assert recovery_path not in {operation.path for operation in password_material.access_trace}
    assert {operation.operation for operation in password_material.access_trace} == {"stat", "open", "read"}
    assert recovery_accesses == []
    assert (capsule / "data" / "state" / "current.bin").read_bytes() == b"current encrypted payload"
    verify_profile_custody_sentinel(
        dek=_DEK,
        profile_id=_PROFILE_ID,
        dek_epoch=_EPOCH,
        sentinel=password_material.sentinel,
    )


def test_uncommitted_or_identity_mixed_capsules_are_not_usable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    candidate = profile_custody_path(_PROFILE_ID, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings).parent
    candidate.mkdir(parents=True)

    assert recognize_current_profile_capsule(_PROFILE_ID, settings=settings) is None
    with pytest.raises(ProfileCustodyRecordError, match="not committed"):
        load_committed_profile_password_material(_PROFILE_ID, settings=settings)


def test_discovery_refuses_a_retired_manifest_by_stat_only_without_opening_its_bytes(tmp_path: Path) -> None:
    """Retired custody is a typed refusal; its untrusted contents are never read."""
    settings = _settings(tmp_path)
    retired = tmp_path / "buckets" / str(_PROFILE_ID) / "manifest.toml"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(b"retired manifest bytes must never be parsed")
    opened_retired_paths: list[object] = []

    def record_open(event: str, arguments: tuple[object, ...]) -> None:
        if event != "open" or not arguments:
            return
        candidate = arguments[0]
        if isinstance(candidate, (str, bytes, os.PathLike)) and os.fspath(candidate) == os.fspath(retired):
            opened_retired_paths.append(os.fspath(candidate))

    sys.addaudithook(record_open)
    assert detect_retired_profile_custody_member_paths(
        tmp_path / "buckets",
        keystore_root=tmp_path / "keystore",
    ) == ("manifest.toml",)
    with pytest.raises(ProfileCustodyRefusedError) as captured:
        list_current_profile_custody_capsule_ids(settings=settings)

    assert captured.value.refusal is ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED
    assert captured.value.recovery_guidance == (
        ProfileCustodyRecoveryGuidance.DESTRUCTIVE_RESET,
        ProfileCustodyRecoveryGuidance.REENROLL_PROFILE,
    )
    assert captured.value.context == {
        "refusal": "LEGACY_CUSTODY_DETECTED",
        "recovery_guidance": ("DESTRUCTIVE_RESET", "REENROLL_PROFILE"),
        "capsules_root": str(tmp_path / "buckets"),
        "keystore_root": str(tmp_path / "keystore"),
        "retired_member_paths": ("manifest.toml",),
        "capsules_root_retired_matches": ("*/manifest.toml",),
    }
    assert opened_retired_paths == []


def test_discovery_refuses_a_retired_keystore_member_by_stat_only_without_opening_its_bytes(tmp_path: Path) -> None:
    """A retired shared-master wrapped DEK is recognised outside the buckets tree.

    The keystore is a sibling of ``buckets/``, so this store's buckets tree is
    entirely current-format and carries no retired member at all.  Only the
    keystore holds retired key material, which is the case a buckets-only
    detector reported as a clean, profile-less store.
    """
    settings = _settings(tmp_path)
    retired = tmp_path / "keystore" / str(_PROFILE_ID) / "bucket.dek.json"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(b"retired wrapped DEK bytes must never be parsed")
    opened_retired_paths: list[object] = []

    def record_open(event: str, arguments: tuple[object, ...]) -> None:
        if event != "open" or not arguments:
            return
        candidate = arguments[0]
        if isinstance(candidate, (str, bytes, os.PathLike)) and os.fspath(candidate) == os.fspath(retired):
            opened_retired_paths.append(os.fspath(candidate))

    sys.addaudithook(record_open)
    assert detect_retired_profile_custody_member_paths(
        tmp_path / "buckets",
        keystore_root=tmp_path / "keystore",
    ) == ("bucket.dek.json",)
    with pytest.raises(ProfileCustodyRefusedError) as captured:
        list_current_profile_custody_capsule_ids(settings=settings)

    assert captured.value.refusal is ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED
    assert captured.value.recovery_guidance == (
        ProfileCustodyRecoveryGuidance.DESTRUCTIVE_RESET,
        ProfileCustodyRecoveryGuidance.REENROLL_PROFILE,
    )
    assert captured.value.context == {
        "refusal": "LEGACY_CUSTODY_DETECTED",
        "recovery_guidance": ("DESTRUCTIVE_RESET", "REENROLL_PROFILE"),
        "capsules_root": str(tmp_path / "buckets"),
        "keystore_root": str(tmp_path / "keystore"),
        "retired_member_paths": ("bucket.dek.json",),
        "keystore_root_retired_matches": ("*/bucket.dek.json",),
    }
    # The buckets root is still named -- it is part of the prescribed reset --
    # but it contributes no match, so the operator is not sent looking for a
    # retired member in a tree that has none.
    assert "capsules_root_retired_matches" not in captured.value.context
    assert opened_retired_paths == []


def test_a_store_retired_in_both_roots_pairs_each_match_with_the_root_it_was_found_under(
    tmp_path: Path,
) -> None:
    """Two retired members must not collapse into an unpaired list of names.

    A flat union answers "which member" but not "where", and the flat union
    answers "where" only by accident when exactly one member is detected. The
    operator's route from the refusal to its cause is the pairing, and it costs
    no read: which name matched below which root is what the scan already
    observed.
    """
    settings = _settings(tmp_path)
    retired_manifest = tmp_path / "buckets" / str(_PROFILE_ID) / "manifest.toml"
    retired_manifest.parent.mkdir(parents=True)
    retired_manifest.write_bytes(b"retired manifest bytes must never be parsed")
    retired_dek = tmp_path / "keystore" / str(_PROFILE_ID) / "bucket.dek.json"
    retired_dek.parent.mkdir(parents=True)
    retired_dek.write_bytes(b"retired wrapped DEK bytes must never be parsed")

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        list_current_profile_custody_capsule_ids(settings=settings)

    assert captured.value.context == {
        "refusal": "LEGACY_CUSTODY_DETECTED",
        "recovery_guidance": ("DESTRUCTIVE_RESET", "REENROLL_PROFILE"),
        "capsules_root": str(tmp_path / "buckets"),
        "keystore_root": str(tmp_path / "keystore"),
        "retired_member_paths": ("bucket.dek.json", "manifest.toml"),
        "capsules_root_retired_matches": ("*/manifest.toml",),
        "keystore_root_retired_matches": ("*/bucket.dek.json",),
    }


def test_the_refusal_never_names_the_candidate_directory_it_found_a_retired_member_in(
    tmp_path: Path,
) -> None:
    """The search pattern must stay a wildcard, never a resolved identity.

    Disclosing the candidate name would assert that the directory IS a retired
    profile -- an identity inferred from retired custody. The pattern is the
    whole of what the operator gets, and it must remain unresolved.
    """
    settings = _settings(tmp_path)
    retired_manifest = tmp_path / "buckets" / str(_PROFILE_ID) / "manifest.toml"
    retired_manifest.parent.mkdir(parents=True)
    retired_manifest.write_bytes(b"retired manifest bytes must never be parsed")

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        list_current_profile_custody_capsule_ids(settings=settings)

    context = captured.value.context
    assert context is not None
    rendered = " ".join(str(value) for key, value in context.items() if key not in {"capsules_root", "keystore_root"})
    assert str(_PROFILE_ID) not in rendered
    assert context["capsules_root_retired_matches"] == ("*/manifest.toml",)


def test_a_current_store_with_live_keystore_sidecars_is_not_refused(tmp_path: Path) -> None:
    """The other half of the detector: it must refuse a retired store and nothing else.

    A detector that refuses every store is as broken as one that refuses none,
    so this exercises a published capsule whose keystore carries the LIVE
    sidecars (the persisted session record and the login-throttle cache) and
    asserts discovery still returns that capsule.
    """
    settings = _settings(tmp_path)
    envelope = _password_envelope()
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=uuid4(),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={"state/current.bin": b"current encrypted payload"},
        settings=settings,
    )
    live_keystore = tmp_path / "keystore" / str(_PROFILE_ID)
    live_keystore.mkdir(parents=True, exist_ok=True)
    (live_keystore / "session.v2.json").write_bytes(b"{}")
    (live_keystore / "login-throttle.json").write_bytes(b"{}")

    assert (
        detect_retired_profile_custody_member_paths(
            tmp_path / "buckets",
            keystore_root=tmp_path / "keystore",
        )
        == ()
    )
    assert list_current_profile_custody_capsule_ids(settings=settings) == (_PROFILE_ID,)


def test_discovery_refuses_an_invalid_current_marker_instead_of_skipping_it(tmp_path: Path) -> None:
    """A UUID candidate with a marker is current-format integrity state, never absence."""
    settings = _settings(tmp_path)
    marker = tmp_path / "buckets" / str(_PROFILE_ID) / "profile.commit.v1.json"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"not a current profile commit")

    with pytest.raises(ProfileCustodyRecordError):
        list_current_profile_custody_capsule_ids(settings=settings)


def test_committed_capsule_enumeration_refuses_linked_candidate_and_unsafe_root_ancestry(tmp_path: Path) -> None:
    """Discovery is anchored at the custody root and never follows a UUID-named link."""
    settings = _settings(tmp_path)
    envelope = _password_envelope()
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    published = publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=uuid4(),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=sentinel,
        data_files={
            "profile-label.v1.json": ProfileCustodyCapsuleLabel.create(
                profile_id=_PROFILE_ID,
                label="Anchored operator",
            ).canonical_json_bytes()
        },
        settings=settings,
    )
    other_profile = uuid4()
    outside = tmp_path / "outside-capsule"
    outside.mkdir()
    os.symlink(outside, published.parent / str(other_profile), target_is_directory=True)

    assert list_current_profile_custody_capsule_ids(settings=settings) == (_PROFILE_ID,)

    moved_capsules = tmp_path / "real-capsules"
    published.parent.rename(moved_capsules)
    os.symlink(moved_capsules, tmp_path / "buckets", target_is_directory=True)
    with pytest.raises(ProfileCustodyRecordError, match=r"link|unsafe|root|reparse"):
        list_current_profile_custody_capsule_ids(settings=settings)
    assert not (outside / "profile.commit.v1.json").exists()


def test_crash_boundary_never_recognizes_a_marker_written_only_in_sibling_staging(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    transaction_id = uuid4()
    staged = profile_custody_path(
        _PROFILE_ID, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings
    ).parent.parent / (f".{_PROFILE_ID}.staging-{transaction_id}")
    staged.mkdir(parents=True)
    (staged / "profile.commit.v1.json").write_bytes(
        ProfileCustodyCommit.create(
            profile_id=_PROFILE_ID,
            transaction_id=transaction_id,
            publication_kind="enroll",
        ).canonical_json_bytes()
    )

    # This is the durable state if a process terminates after marker fsync but
    # before the only publication rename.  Recognition has no staging scan.
    assert recognize_current_profile_capsule(_PROFILE_ID, settings=settings) is None
    with pytest.raises(ProfileCustodyRecordError, match="not committed"):
        load_committed_profile_password_material(_PROFILE_ID, settings=settings)


def test_publication_refuses_epoch_mismatch_traversal_and_leaves_no_staging_capsule(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    envelope = _password_envelope()
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    mismatched_recovery = _recovery_envelope(dek_epoch=base64.b64encode(b"x" * 16).decode("ascii"))

    with pytest.raises(ProfileCustodyRecordError, match="optional recovery identity"):
        publish_profile_custody_capsule(
            profile_id=_PROFILE_ID,
            transaction_id=uuid4(),
            publication_kind="enroll",
            password_envelope=envelope,
            sentinel=sentinel,
            recovery_envelope=mismatched_recovery,
            data_files={},
            settings=settings,
        )
    with pytest.raises(ProfileCustodyRecordError, match="escapes its staging root"):
        publish_profile_custody_capsule(
            profile_id=_PROFILE_ID,
            transaction_id=uuid4(),
            publication_kind="enroll",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={"../outside": b"must never be written"},
            settings=settings,
        )

    capsules_root = profile_custody_path(
        _PROFILE_ID, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings
    ).parent.parent
    assert not scan_directory(capsules_root, pattern=f".{_PROFILE_ID}.staging-*")
    assert not os.path.lexists(capsules_root / str(_PROFILE_ID))


def test_publication_and_export_refuse_real_directory_reparse_points(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    recovery = create_profile_custody_recovery_envelope(
        profile_id=_PROFILE_ID,
        recovery_secret=_RECOVERY_SECRET,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    capsules_root = profile_custody_path(
        _PROFILE_ID, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings
    ).parent.parent
    capsules_root.parent.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, capsules_root, target_is_directory=True)

    with pytest.raises(ProfileCustodyRecordError, match="root must not be a link"):
        publish_profile_custody_capsule(
            profile_id=_PROFILE_ID,
            transaction_id=uuid4(),
            publication_kind="enroll",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={},
            settings=settings,
        )

    export_parent = tmp_path / "export-parent"
    os.symlink(outside, export_parent, target_is_directory=True)
    with pytest.raises(ProfileCustodyRecordError, match="target parent"):
        export_profile_custody_recovery_artifact(
            recovery,
            current_password=_PASSPHRASE,
            password_envelope=envelope,
            sentinel=sentinel,
            target=export_parent / "recovery.json",
            settings=settings,
        )


def test_publication_collision_refuses_replacement_and_safely_removes_own_stage(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    destination = profile_custody_path(_PROFILE_ID, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings).parent
    destination.mkdir(parents=True)
    transaction_id = uuid4()

    with pytest.raises(ProfileCustodyRecordError, match="destination already exists"):
        publish_profile_custody_capsule(
            profile_id=_PROFILE_ID,
            transaction_id=transaction_id,
            publication_kind="enroll",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={},
            settings=settings,
        )

    assert destination.is_dir()
    assert not os.path.lexists(
        profile_custody_path(
            _PROFILE_ID, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings
        ).parent.parent.joinpath(f".{_PROFILE_ID}.staging-{transaction_id}")
    )
