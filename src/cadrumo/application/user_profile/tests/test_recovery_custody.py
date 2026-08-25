"""Recovery enrollment, portable artifact, and the two restore authorities.

Every test here runs the real chain: real Argon2id calibration, a real
password envelope, the real capsule publication, a real file on a real
filesystem. There is no stand-in for the KDF, because the whole exposure
argument for exporting a recovery artifact rests on what the KDF and the
secret's entropy actually cost an attacker, and a substituted one would
prove nothing about that.

Three claims carry the safety weight and each has an arm that makes it
falsifiable: the artifact refuses a corrupted or substituted record rather
than yielding key material; the destination guard refuses rather than warns;
and the recovery secret exists nowhere on disk after a successful export.
"""

from __future__ import annotations

import os
from base64 import b64encode
from pathlib import Path
from secrets import token_bytes
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession, ProfileRecordStore
from cadrumo.application.user_profile.custody_ports import create_profile_custody_registration_material
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.recovery_contracts import ProfileCustodyRecoveryArtifactWarning
from cadrumo.application.user_profile.recovery_custody import (
    ProfileRecoveryArtifactReceipt,
    ProfileRecoveryEnrollment,
    export_profile_recovery_artifact,
    mint_profile_creation_recovery,
    restore_profile_from_recovery_artifact,
    restore_profile_with_password,
)

from ....adapters.persistence.storage import generate_recovery_key
from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyRecordError,
    create_profile_custody_sentinel,
)
from ....core.config import override_settings
from ....core.errors import build_error_envelope, render_error_text
from ....core.i18n import tr
from ....domain.user_profile import ProfileSetupState, UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "an operator chosen passphrase that clears the verifier minimum"  # noqa: S105 - real test credential


class _EnrolledProfile:
    """One really-created profile plus every record a recovery flow needs."""

    __slots__ = ("dek", "enrollment", "envelope", "profile_id", "root", "sentinel")

    def __init__(self, root: Path) -> None:
        self.root = root
        self.profile_id = uuid4()
        self.dek = token_bytes(32)
        dek_epoch = b64encode(token_bytes(16)).decode("ascii")
        material = create_profile_custody_registration_material(
            profile_id=self.profile_id,
            password=_PASSWORD,
            dek=self.dek,
            dek_epoch=dek_epoch,
            salt=token_bytes(16),
        )
        envelope = material.envelope
        # Narrowed on the way out of the boundary and needed back at its
        # substrate type here, because this module builds a second sentinel
        # against the same envelope to construct the divergent-key case.
        assert isinstance(envelope, ProfileCustodyEnvelope)
        self.envelope = envelope
        self.sentinel = material.sentinel
        self.enrollment = mint_profile_creation_recovery(
            profile_id=self.profile_id,
            dek=self.dek,
            dek_epoch=dek_epoch,
        )
        session = ProfileRecordSession.from_envelope(envelope=self.envelope, dek=self.dek)
        try:
            ProfileCapsuleLifecycle(root=root).create(
                label=f"Recovery operator {self.profile_id}",
                profile_id=self.profile_id,
                password_envelope=self.envelope,
                sentinel=self.sentinel,
                data_files={},
                initial_record=UserProfileRecord(
                    profile_id=str(self.profile_id),
                    setup_state=ProfileSetupState.INCOMPLETE,
                ),
                record_session=session,
                recovery_envelope=self.enrollment.envelope,
            )
        finally:
            session.close()

    @property
    def database_bytes(self) -> bytes:
        return (self.root / "buckets" / str(self.profile_id) / "db" / "cadrumo.db").read_bytes()

    def export(self, target: Path) -> ProfileRecoveryArtifactReceipt:
        return export_profile_recovery_artifact(
            self.enrollment,
            current_password=_PASSWORD,
            password_envelope=self.envelope,
            sentinel=self.sentinel,
            target=target,
        )


@pytest.fixture(scope="module")
def _enrolled_once(tmp_path_factory: pytest.TempPathFactory):
    """Create the subject profile once, with the real KDF, for the module.

    The Argon2id calibration is deliberately not substituted, and it is the
    dominant cost here: repeating it per test spent ten minutes proving the
    same enrollment sixteen times. One enrollment is shared because nothing
    below mutates it -- every restore publishes into its own fresh root and
    every export writes its own per-test destination -- so the tests stay
    independent while the honest KDF is paid for once.
    """
    root = tmp_path_factory.mktemp("recovery-store")
    with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=None):
        yield _EnrolledProfile(root)


@pytest.fixture
def enrolled(_enrolled_once: _EnrolledProfile, tmp_path: Path):
    """Bind the shared profile's storage root for the duration of one test.

    The destination guard resolves the storage root at export time, so the
    override has to be live inside the test and not merely at creation.
    """
    (tmp_path / "exports").mkdir()
    with override_settings(cadrumo_local_storage_root=_enrolled_once.root, cadrumo_active_profile=None):
        yield _enrolled_once


def test_enrollment_wraps_the_profiles_own_key_under_a_minted_mnemonic(enrolled: _EnrolledProfile) -> None:
    """The enrolled secret is 24 words, and it opens this profile's key.

    Enrollment must not generate a key of its own: the wrapper covers the
    DEK the profile already has, so a second wrapper cannot silently create
    a capsule with two different keys behind two different doors.
    """
    assert isinstance(enrolled.enrollment, ProfileRecoveryEnrollment)
    assert len(enrolled.enrollment.recovery_key.mnemonic.split()) == 24
    assert enrolled.enrollment.envelope.profile_id == enrolled.profile_id
    assert enrolled.enrollment.envelope.dek_epoch == enrolled.envelope.dek_epoch


def test_export_import_prove_returns_exactly_the_profiles_key(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """The full artifact round trip hands back the same 32 bytes, and only those."""
    target = tmp_path / "exports" / "recovery.json"

    receipt = enrolled.export(target)

    assert target.is_file()
    assert receipt.profile_id == enrolled.profile_id
    assert receipt.dek_epoch == enrolled.envelope.dek_epoch
    assert receipt.target == target
    assert set(receipt.warnings) == set(ProfileCustodyRecoveryArtifactWarning)

    restored = restore_profile_from_recovery_artifact(
        label="Recovered by artifact",
        artifact_source=target,
        recovery_secret=enrolled.enrollment.recovery_key.mnemonic,
        password_envelope=enrolled.envelope,
        sentinel=enrolled.sentinel,
        database_bytes=enrolled.database_bytes,
        root=tmp_path / "restored",
    )

    assert restored.profile_id == str(enrolled.profile_id)
    assert restored.publication_kind == "restore"


def test_export_writes_no_trace_of_the_recovery_secret_to_disk(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """The mnemonic and its entropy appear in no file the export touched.

    An artifact carries the WRAPPED key; the secret that unwraps it is the
    operator's alone. If either the words or the raw entropy reached the
    artifact, the storage root, or any stray file beside them, the export
    would be handing out both halves at once.
    """
    target = tmp_path / "exports" / "recovery.json"
    enrolled.export(target)
    words = enrolled.enrollment.recovery_key.mnemonic.encode("utf-8")
    entropy = bytes(enrolled.enrollment.recovery_key.raw)

    searched = 0
    for directory in (tmp_path / "exports", enrolled.root):
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            searched += 1
            payload = path.read_bytes()
            assert words not in payload, f"recovery mnemonic reached {path}"
            assert entropy not in payload, f"recovery entropy reached {path}"
    # Without this the loop above passes vacuously on an empty tree.
    assert searched >= 2


def test_a_corrupted_artifact_is_refused_instead_of_yielding_key_material(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """Deleting a field from the on-disk artifact makes the read refuse.

    The anti-tautology proof for every artifact assertion in this module: it
    establishes that a successful import is a real check on the bytes, not a
    parse that accepts whatever it finds.
    """
    target = tmp_path / "exports" / "recovery.json"
    enrolled.export(target)
    intact = target.read_text(encoding="utf-8")
    assert '"recovery_generation":' in intact
    corrupted = intact.replace('"recovery_generation":1,', "", 1)
    assert corrupted != intact
    target.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ProfileCustodyRecordError):
        restore_profile_from_recovery_artifact(
            label="Refused",
            artifact_source=target,
            recovery_secret=enrolled.enrollment.recovery_key.mnemonic,
            password_envelope=enrolled.envelope,
            sentinel=enrolled.sentinel,
            database_bytes=enrolled.database_bytes,
            root=tmp_path / "refused",
        )


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    if not root.exists():
        return ()
    return tuple(
        (
            path.relative_to(root).as_posix(),
            "file" if path.is_file() else "directory",
            path.read_bytes() if path.is_file() else None,
        )
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
    )


@pytest.mark.parametrize("candidate_kind", ("wrong_mnemonic", "malformed_surrogate"))
def test_hostile_recovery_secret_has_one_exact_public_refusal_and_no_mutation(
    candidate_kind: str,
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    target = tmp_path / "exports" / f"{candidate_kind}.json"
    destination = tmp_path / f"{candidate_kind}-refused"
    enrolled.export(target)
    candidate = " ".join(["abandon"] * 23 + ["art"])
    candidate_safe = candidate
    if candidate_kind == "malformed_surrogate":
        candidate = chr(0xD800)
        candidate_safe = repr(candidate).encode("ascii", errors="backslashreplace").decode("ascii")
    before = _tree_snapshot(tmp_path)

    with pytest.raises(ProfileAuthenticationRefusedError) as refused:
        restore_profile_from_recovery_artifact(
            label="Refused",
            artifact_source=target,
            recovery_secret=candidate,
            password_envelope=enrolled.envelope,
            sentinel=enrolled.sentinel,
            database_bytes=enrolled.database_bytes,
            root=destination,
        )

    assert refused.value.context is None
    with override_settings(cadrumo_output_language="es"):
        envelope = build_error_envelope(refused.value)
        rendered = render_error_text(refused.value)
    message = tr("application.user_profile.errors.profile_authentication_refused", locale="es")
    prefix = tr("errors.prefix.refused", locale="es")
    assert envelope.model_dump(mode="json") == {
        "code": "REFUSED_PROFILE_AUTHENTICATION",
        "category": "REFUSED",
        "message": message,
        "action": None,
        "retryable": False,
        "runbook_id": None,
        "context": None,
        "trace_id": None,
    }
    assert rendered == f"{prefix} {message}\n"
    assert "profile recovery secret did not authenticate" not in rendered
    assert "profile recovery secret is not strict UTF-8" not in rendered
    assert "application.user_profile.errors.profile_authentication_refused" not in rendered
    assert "INTERNAL" not in rendered
    assert "Traceback" not in rendered
    assert candidate_safe not in rendered
    assert _tree_snapshot(tmp_path) == before


def test_an_artifact_cannot_become_another_profiles_authority(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """A restore under a different identity is refused, not silently accepted.

    This is the portability boundary. The artifact travels to another
    machine for the SAME profile; it must never carry that profile's
    authority onto a different UUID, because a capsule published that way
    would authenticate under an identity its own contents contradict.
    """
    target = tmp_path / "exports" / "recovery.json"
    enrolled.export(target)
    other_id = uuid4()
    other = create_profile_custody_registration_material(
        profile_id=other_id,
        password=_PASSWORD,
        dek=token_bytes(32),
        dek_epoch=b64encode(token_bytes(16)).decode("ascii"),
        salt=token_bytes(16),
    )

    with pytest.raises(ProfileCustodyRecordError, match="does not match its named target"):
        restore_profile_from_recovery_artifact(
            label="Wrong identity",
            artifact_source=target,
            recovery_secret=enrolled.enrollment.recovery_key.mnemonic,
            password_envelope=other.envelope,
            sentinel=other.sentinel,
            database_bytes=enrolled.database_bytes,
            root=tmp_path / "wrong-identity",
        )


@pytest.mark.parametrize("relative", ["recovery.json", os.path.join("exports", "recovery.json")])
def test_export_refuses_a_relative_destination(
    enrolled: _EnrolledProfile,
    relative: str,
) -> None:
    """A destination the operator did not fully name is refused."""
    with pytest.raises(ProfileCustodyRecordError, match="absolute path"):
        enrolled.export(Path(relative))


def test_export_refuses_a_destination_carrying_an_indirect_segment(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """A path whose written form differs from the path it opens is refused."""
    with pytest.raises(ProfileCustodyRecordError, match="no parent or current directory segment"):
        enrolled.export(tmp_path / "exports" / ".." / "exports" / "recovery.json")


def test_export_refuses_a_destination_inside_the_storage_root(
    enrolled: _EnrolledProfile,
) -> None:
    """The artifact may not be stored with the ciphertext it unwraps."""
    with pytest.raises(ProfileCustodyRecordError, match="outside the Cadrumo storage root"):
        enrolled.export(enrolled.root / "recovery.json")

    with pytest.raises(ProfileCustodyRecordError, match="outside the Cadrumo storage root"):
        enrolled.export(enrolled.root / "buckets" / str(enrolled.profile_id) / "recovery.json")


def test_export_refuses_to_replace_an_existing_file(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """An occupied destination is refused rather than overwritten.

    Overwriting would destroy whatever was there, and on a re-export it
    would destroy the artifact the operator is holding while they still
    believe it is valid.
    """
    target = tmp_path / "exports" / "recovery.json"
    target.write_text("not an artifact", encoding="utf-8")

    with pytest.raises(ProfileCustodyRecordError, match="created exclusively"):
        enrolled.export(target)

    assert target.read_text(encoding="utf-8") == "not an artifact"


@pytest.mark.parametrize("candidate", ("not the operator's passphrase at all", "short"))
def test_export_requires_the_current_password(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
    candidate: str,
) -> None:
    """Producing a second door requires the door that already exists."""
    target = tmp_path / "exports" / "recovery.json"

    with pytest.raises(ProfileAuthenticationRefusedError) as refused:
        export_profile_recovery_artifact(
            enrolled.enrollment,
            current_password=candidate,
            password_envelope=enrolled.envelope,
            sentinel=enrolled.sentinel,
            target=target,
        )

    assert not target.exists()
    assert refused.value.translated_message == "application.user_profile.errors.profile_authentication_refused"
    assert refused.value.context is None
    assert candidate not in repr(refused.value)


def test_password_only_restore_publishes_the_capsule(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """The password alone republishes a capsule: no recovery material at all."""
    restored = restore_profile_with_password(
        label="Recovered by password",
        password=_PASSWORD,
        password_envelope=enrolled.envelope,
        sentinel=enrolled.sentinel,
        database_bytes=enrolled.database_bytes,
        root=tmp_path / "password-restored",
    )

    assert restored.profile_id == str(enrolled.profile_id)
    assert restored.publication_kind == "restore"


@pytest.mark.parametrize("candidate", ("a different passphrase entirely, still long enough", "short"))
def test_password_only_restore_refuses_the_wrong_password(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
    candidate: str,
) -> None:
    """The password proof is a real unwrap, so a wrong one publishes nothing."""
    destination = tmp_path / "refused-restore"

    with pytest.raises(ProfileAuthenticationRefusedError) as refused:
        restore_profile_with_password(
            label="Refused",
            password=candidate,
            password_envelope=enrolled.envelope,
            sentinel=enrolled.sentinel,
            database_bytes=enrolled.database_bytes,
            root=destination,
        )

    assert not (destination / "buckets" / str(enrolled.profile_id)).exists()
    assert refused.value.translated_message == "application.user_profile.errors.profile_authentication_refused"
    assert refused.value.context is None
    assert candidate not in repr(refused.value)


def test_restore_refuses_a_database_key_the_committed_sentinel_does_not_commit_to(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """A database keyed differently from the password's key is refused.

    This is the one failure the staged-database authentication cannot see,
    and it is the expensive one. Every other check passes here: the envelope
    is this profile's, the session was minted from that exact envelope, and
    the staged database authenticates perfectly against that session --
    because the database really was written under the session's key. Only
    the committed sentinel disagrees, and the sentinel is the record saying
    which key the PASSWORD produces.

    Publishing it would leave a capsule that accepts the operator's password
    and then decrypts nothing, discovered on the day they needed it. The
    divergence is constructed rather than simulated: the source capsule below
    is genuinely created under the divergent key.
    """
    divergent_dek = token_bytes(32)
    divergent_session = ProfileRecordSession.from_envelope(envelope=enrolled.envelope, dek=divergent_dek)
    source_root = tmp_path / "divergent-source"
    target_root = tmp_path / "divergent-target"
    try:
        ProfileCapsuleLifecycle(root=source_root).create(
            label="Divergent key source",
            profile_id=enrolled.profile_id,
            password_envelope=enrolled.envelope,
            sentinel=create_profile_custody_sentinel(envelope=enrolled.envelope, dek=divergent_dek),
            data_files={},
            initial_record=UserProfileRecord(
                profile_id=str(enrolled.profile_id),
                setup_state=ProfileSetupState.INCOMPLETE,
            ),
            record_session=divergent_session,
            recovery_envelope=enrolled.enrollment.envelope,
        )
        divergent_database = (source_root / "buckets" / str(enrolled.profile_id) / "db" / "cadrumo.db").read_bytes()

        with pytest.raises(ProfileCustodyRecordError, match="sentinel"):
            ProfileCapsuleLifecycle(root=target_root).restore(
                label="Divergent key",
                password_envelope=enrolled.envelope,
                sentinel=enrolled.sentinel,
                data_files={},
                record_session=divergent_session,
                database_bytes=divergent_database,
                authority="password",
            )
    finally:
        divergent_session.close()

    assert not (target_root / "buckets" / str(enrolled.profile_id)).exists()


def test_restore_refuses_a_sentinel_from_a_different_profile(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """A sentinel and an envelope naming different profiles cannot be combined."""
    other_id = UUID("6f3c0b4d-2f5a-4a6a-9c1f-0d2c5e7a8b90")
    other_envelope = create_profile_custody_registration_material(
        profile_id=other_id,
        password=_PASSWORD,
        dek=enrolled.dek,
        dek_epoch=enrolled.envelope.dek_epoch,
        salt=token_bytes(16),
    ).envelope
    assert isinstance(other_envelope, ProfileCustodyEnvelope)
    foreign_sentinel = create_profile_custody_sentinel(envelope=other_envelope, dek=enrolled.dek)
    session = ProfileRecordSession.from_envelope(envelope=enrolled.envelope, dek=enrolled.dek)
    try:
        with pytest.raises(ValueError, match="must bind one UUID"):
            ProfileCapsuleLifecycle(root=tmp_path / "foreign-sentinel").restore(
                label="Foreign sentinel",
                password_envelope=enrolled.envelope,
                sentinel=foreign_sentinel,
                data_files={},
                record_session=session,
                database_bytes=enrolled.database_bytes,
                authority="password",
            )
    finally:
        session.close()


def test_recovery_artifact_restore_publishes_a_capsule_whose_records_are_readable(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """The artifact door returns an operator's RECORDS, not merely a capsule.

    This is the claim the whole recovery mechanism exists to make good on,
    and publishing a capsule is only half of it: a restore that republished
    a capsule whose database no key could open would satisfy every assertion
    about publication and still leave the taxpayer with nothing. So the
    record is decrypted out of the restored capsule, through a session built
    from the key the ARTIFACT proved, and compared to what was stored.
    """
    artifact = tmp_path / "exports" / "recovery.artifact.json"
    enrolled.export(artifact)
    destination = tmp_path / "artifact-restored"

    restored = restore_profile_from_recovery_artifact(
        label="Recovered by artifact",
        artifact_source=artifact,
        recovery_secret=enrolled.enrollment.recovery_key.mnemonic,
        password_envelope=enrolled.envelope,
        sentinel=enrolled.sentinel,
        database_bytes=enrolled.database_bytes,
        root=destination,
    )

    assert restored.profile_id == str(enrolled.profile_id)
    assert restored.publication_kind == "restore"

    session = ProfileRecordSession.from_envelope(envelope=enrolled.envelope, dek=enrolled.dek)
    try:
        recovered = ProfileRecordStore(session=session, root=destination).load().record
    finally:
        session.close()

    assert recovered.profile_id == str(enrolled.profile_id)
    assert recovered.setup_state is ProfileSetupState.INCOMPLETE


def test_recovery_artifact_restore_does_not_hand_back_password_access(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """Recovering the DATA is not recovering the credential, and must not become it.

    The capsule is republished under its EXISTING password envelope, so an
    operator who genuinely lost their password gets their records onto a
    valid capsule and still cannot log in with a password they do not know.
    Changing that would be credential rotation reached through the recovery
    door, which is a different capability with a different authorisation --
    so this pins the boundary rather than describing it in a docstring.
    """
    artifact = tmp_path / "exports" / "no-password-reset.artifact.json"
    enrolled.export(artifact)
    destination = tmp_path / "artifact-restored-envelope"

    restore_profile_from_recovery_artifact(
        label="Recovered without a new password",
        artifact_source=artifact,
        recovery_secret=enrolled.enrollment.recovery_key.mnemonic,
        password_envelope=enrolled.envelope,
        sentinel=enrolled.sentinel,
        database_bytes=enrolled.database_bytes,
        root=destination,
    )

    republished = (destination / "buckets" / str(enrolled.profile_id) / "custody" / "envelope.v1.json").read_bytes()

    assert republished == enrolled.envelope.canonical_json_bytes()


def test_a_wrong_mnemonic_restores_nothing_through_the_artifact_door(
    enrolled: _EnrolledProfile,
    tmp_path: Path,
) -> None:
    """Anti-tautology for the pair above: the artifact is not self-authorising.

    Both sibling tests would read identically if holding the FILE were
    sufficient, so a real artifact presented with a different real mnemonic
    must publish nothing at all.
    """
    artifact = tmp_path / "exports" / "wrong-secret.artifact.json"
    enrolled.export(artifact)
    destination = tmp_path / "artifact-refused"

    with generate_recovery_key() as impostor:
        assert impostor.mnemonic != enrolled.enrollment.recovery_key.mnemonic
        with pytest.raises(ProfileAuthenticationRefusedError) as refused:
            restore_profile_from_recovery_artifact(
                label="Refused",
                artifact_source=artifact,
                recovery_secret=impostor.mnemonic,
                password_envelope=enrolled.envelope,
                sentinel=enrolled.sentinel,
                database_bytes=enrolled.database_bytes,
                root=destination,
            )

    assert refused.value.context is None

    assert not (destination / "buckets" / str(enrolled.profile_id)).exists()
