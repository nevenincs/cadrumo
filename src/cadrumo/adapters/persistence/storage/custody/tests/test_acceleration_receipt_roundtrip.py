"""Current per-profile persisted-session acceleration behaviour.

The cases use the real Windows keychain, actual atomic sidecars, and the
production AES-GCM receipt API.  They deliberately have no test-only writer:
only a successful production mint may create a resumable receipt.
"""

from __future__ import annotations

import base64
import os
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import keyring
import pytest

from ......core.errors.hierarchy import CoreValidationError
from ......core.profile_session import ProfileSessionRefusalReason
from ...custody.filesystem import (
    compare_and_replace_profile_custody_local_record,
    ensure_profile_custody_local_directory,
    profile_custody_root_lock,
)
from ...errors import DecryptionError, EncryptionError, KeyringUnavailableError, StorageValidationError
from ..acceleration_receipt import (
    PROFILE_SESSION_KEYCHAIN_SERVICE,
    PROFILE_SESSION_RECORD_MAX_BYTES,
    AccelerationReceiptRevocationError,
    _pending_retirement_bytes,
    _profile_session_lock_path,
    _profile_session_retirement_path,
    _receipt_bytes,
    _write_acceleration_receipt,
    advance_persisted_profile_session_idle_deadline,
    delete_profile_session,
    mint_profile_session,
    profile_session_path,
    resume_profile_session,
)
from ..acceleration_receipt_crypto import (
    PROFILE_SESSION_SCHEMA_VERSION,
    PersistedProfileSession,
    unwrap_profile_session_dek,
    wrap_profile_session_dek,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
_IDLE_MINUTES = 15
_ABSOLUTE_MINUTES = 240
_EPOCH = "test-dek-epoch-1"


def _profile_id() -> UUID:
    """Return an isolated immutable capsule identity."""
    return uuid4()


def _account(profile_id: UUID, session_id: UUID) -> str:
    """State the external keychain contract independently of production code."""
    return f"{profile_id}:{session_id}"


def _wrap(*, session_key: bytes, dek: bytes, profile_id: UUID) -> PersistedProfileSession:
    """Create a production AEAD receipt with deterministic metadata."""
    return wrap_profile_session_dek(
        session_key=session_key,
        dek=dek,
        profile_id=profile_id,
        session_id=uuid4(),
        custody_generation=1,
        dek_epoch=_EPOCH,
        issued_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=_IDLE_MINUTES),
        absolute_deadline=_NOW + timedelta(minutes=_ABSOLUTE_MINUTES),
    )


class TestSessionReceiptAad:
    """Every current provenance/deadline field is cryptographically bound."""

    def test_roundtrip_recovers_the_dek(self) -> None:
        session_key = secrets.token_bytes(32)
        dek = secrets.token_bytes(32)
        record = _wrap(session_key=session_key, dek=dek, profile_id=_profile_id())

        assert unwrap_profile_session_dek(session_key=session_key, record=record) == dek

    @pytest.mark.parametrize(
        "mutation",
        [
            {"schema_version": PROFILE_SESSION_SCHEMA_VERSION + 1},
            {"profile_id": uuid4()},
            {"session_id": uuid4()},
            {"custody_generation": 2},
            {"dek_epoch": "other-epoch"},
            {"issued_at": _NOW - timedelta(seconds=1)},
            {"idle_deadline": _NOW + timedelta(minutes=60)},
            {"absolute_deadline": _NOW + timedelta(minutes=300)},
        ],
        ids=(
            "schema-version",
            "profile-id",
            "session-id",
            "custody-generation",
            "dek-epoch",
            "issued-at",
            "idle-deadline",
            "absolute-deadline",
        ),
    )
    def test_metadata_substitution_fails_tag(self, mutation: dict[str, object]) -> None:
        session_key = secrets.token_bytes(32)
        record = _wrap(session_key=session_key, dek=secrets.token_bytes(32), profile_id=_profile_id())

        with pytest.raises(DecryptionError):
            unwrap_profile_session_dek(session_key=session_key, record=record.model_copy(update=mutation))

    def test_wrong_lengths_and_naive_issue_time_refuse(self) -> None:
        profile_id = _profile_id()
        with pytest.raises(EncryptionError):
            _wrap(session_key=b"short", dek=secrets.token_bytes(32), profile_id=profile_id)
        with pytest.raises(EncryptionError):
            _wrap(session_key=secrets.token_bytes(32), dek=b"short", profile_id=profile_id)
        with pytest.raises(CoreValidationError):
            wrap_profile_session_dek(
                session_key=secrets.token_bytes(32),
                dek=secrets.token_bytes(32),
                profile_id=profile_id,
                session_id=uuid4(),
                custody_generation=1,
                dek_epoch=_EPOCH,
                issued_at=datetime(2026, 8, 14, 12, 0, 0),
                idle_deadline=_NOW + timedelta(minutes=15),
                absolute_deadline=_NOW + timedelta(minutes=240),
            )


class TestKeyringBoundary:
    """Observe the actual host capability without replacing its backend."""

    def test_mint_either_persists_a_complete_receipt_or_leaves_no_artifact(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
        try:
            record = mint_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=1,
                dek_epoch=_EPOCH,
                dek=secrets.token_bytes(32),
                now=_NOW,
                idle_minutes=_IDLE_MINUTES,
                absolute_minutes=_ABSOLUTE_MINUTES,
            )
        except KeyringUnavailableError:
            # The live Windows credential boundary refused the key before a
            # disk-only receipt could be published.  The next login remains
            # process-scoped, never a fallback to another key authority.
            assert not path.exists()
        else:
            try:
                assert path.exists()
                assert (
                    keyring.get_password(
                        PROFILE_SESSION_KEYCHAIN_SERVICE,
                        _account(profile_id, record.session_id),
                    )
                    is not None
                )
            finally:
                delete_profile_session(storage_root=tmp_path, profile_id=profile_id)


class TestAnchoredReceiptBoundary:
    """Hostile receipt leaves reach only the custody local-record owner."""

    @staticmethod
    def _path(tmp_path: Path, profile_id: UUID) -> Path:
        path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
        ensure_profile_custody_local_directory(path.parent.parent)
        ensure_profile_custody_local_directory(path.parent)
        return path

    def test_absent_receipt_refusal_does_not_materialise_a_session_lock(self, tmp_path: Path) -> None:
        """A logged-out probe must not leave a durable lock artifact behind.

        Root-secret refusals first ask whether a resumable session exists.  If
        that answer is the ordinary absence case, the probe must not create a
        session-owned lock before the secret source is even validated.
        """
        profile_id = _profile_id()
        path = self._path(tmp_path, profile_id)
        lock_path = _profile_session_lock_path(path)
        # The active-profile transaction has already provisioned this root
        # leaf before an established profile reaches resume.  Establish that
        # lifecycle precondition, so this is an exact before/after probe of
        # the logged-out refusal path rather than a first-root bootstrap test.
        with profile_custody_root_lock(tmp_path):
            pass
        before = {
            candidate.relative_to(tmp_path).as_posix(): candidate.read_bytes()
            for candidate in tmp_path.rglob("*")
            if candidate.is_file()
        }
        assert not path.exists()
        assert not lock_path.exists()

        outcome, dek = resume_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch=_EPOCH,
            now=_NOW,
        )

        assert outcome.refusal is ProfileSessionRefusalReason.ABSENT
        assert dek is None
        assert not path.exists()
        assert not lock_path.exists()
        assert {
            candidate.relative_to(tmp_path).as_posix(): candidate.read_bytes()
            for candidate in tmp_path.rglob("*")
            if candidate.is_file()
        } == before

    def test_independent_resume_observes_concurrent_mint_after_root_lock_release(self, tmp_path: Path) -> None:
        """An independent resume is linearized with a concurrent real mint.

        The child enters the production resume path and announces immediately
        before it requests the root lock.  The parent keeps that lock, mints
        through the production writer, then releases it.  Thus a successful
        mint must be visible to the child resume; it cannot race between an
        unlocked absence observation and the refusal return.
        """
        profile_id = _profile_id()
        started = tmp_path / "resume-started"
        finished = tmp_path / "resume-finished"
        script = """
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import (
    resume_profile_session,
)

root = Path(__import__("sys").argv[1])
profile_id = UUID(__import__("sys").argv[2])
started = Path(__import__("sys").argv[3])
finished = Path(__import__("sys").argv[4])
started.write_text("ready", encoding="utf-8")
outcome, dek = resume_profile_session(
    storage_root=root,
    profile_id=profile_id,
    custody_generation=1,
    dek_epoch="test-dek-epoch-1",
    now=datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC),
)
try:
    finished.write_text("resumed" if outcome.resumed else "refused", encoding="utf-8")
finally:
    if dek is not None:
        dek.clear()
"""
        child: subprocess.Popen[str] | None = None
        minted = False
        try:
            with profile_custody_root_lock(tmp_path):
                child = subprocess.Popen(  # noqa: S603 - fixed interpreter and production mint driver
                    [
                        sys.executable,
                        "-c",
                        script,
                        str(tmp_path),
                        str(profile_id),
                        str(started),
                        str(finished),
                    ],
                    cwd=Path.cwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                deadline = time.monotonic() + 30.0
                while not started.exists() and time.monotonic() < deadline:
                    assert child.poll() is None, "independent production resume exited before its call"
                    time.sleep(0.01)
                assert started.exists(), "independent production resume did not reach its call"
                time.sleep(0.1)
                assert not finished.exists(), "independent production resume bypassed the custody-root lock"

                try:
                    mint_profile_session(
                        storage_root=tmp_path,
                        profile_id=profile_id,
                        custody_generation=1,
                        dek_epoch=_EPOCH,
                        dek=secrets.token_bytes(32),
                        now=_NOW,
                        idle_minutes=_IDLE_MINUTES,
                        absolute_minutes=_ABSOLUTE_MINUTES,
                    )
                except KeyringUnavailableError:
                    pass
                else:
                    minted = True
                assert not finished.exists(), "independent resume crossed the custody-root lock before mint completed"
        finally:
            if child is not None:
                try:
                    stdout, stderr = child.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    child.kill()
                    stdout, stderr = child.communicate(timeout=60)
                    raise AssertionError(
                        "independent production resume did not finish after root-lock release"
                    ) from None
                assert child.returncode == 0, f"independent production resume failed: {stdout}\n{stderr}"
        assert finished.read_text(encoding="utf-8") == ("resumed" if minted else "refused")
        if minted:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    def test_oversize_leaf_is_refused_before_any_keychain_operation(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        path = self._path(tmp_path, profile_id)
        path.write_bytes(b"x" * (PROFILE_SESSION_RECORD_MAX_BYTES + 1))

        outcome, dek = resume_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch=_EPOCH,
            now=_NOW,
        )

        assert outcome.refusal is ProfileSessionRefusalReason.MALFORMED
        assert dek is None
        assert path.exists()

    def test_noncanonical_and_duplicate_json_are_refused_by_exact_bytes(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        record = _wrap(session_key=secrets.token_bytes(32), dek=secrets.token_bytes(32), profile_id=profile_id)
        canonical = _receipt_bytes(record)
        duplicate = canonical[:-1] + f',"profile_id":"{profile_id}"}}'.encode()

        for candidate in (b" " + canonical, duplicate):
            path = self._path(tmp_path, profile_id)
            path.write_bytes(candidate)

            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=1,
                dek_epoch=_EPOCH,
                now=_NOW,
            )

            assert outcome.refusal is ProfileSessionRefusalReason.MALFORMED
            assert dek is None
            assert not path.exists()

    def test_parent_link_leaf_link_and_nonregular_leaf_are_refused_without_opening_targets(
        self, tmp_path: Path
    ) -> None:
        profile_id = _profile_id()
        path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / path.name
        target.write_bytes(b"outside")
        keystore = path.parent.parent
        ensure_profile_custody_local_directory(keystore)
        os.symlink(outside, path.parent, target_is_directory=True)

        outcome, dek = resume_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch=_EPOCH,
            now=_NOW,
        )
        assert outcome.refusal is ProfileSessionRefusalReason.MALFORMED
        assert dek is None
        assert target.read_bytes() == b"outside"

        linked_profile = _profile_id()
        linked_path = self._path(tmp_path, linked_profile)
        linked_target = tmp_path / "linked-target.json"
        linked_target.write_bytes(b"target")
        os.symlink(linked_target, linked_path)
        linked, linked_dek = resume_profile_session(
            storage_root=tmp_path,
            profile_id=linked_profile,
            custody_generation=1,
            dek_epoch=_EPOCH,
            now=_NOW,
        )
        assert linked.refusal is ProfileSessionRefusalReason.MALFORMED
        assert linked_dek is None
        assert linked_target.read_bytes() == b"target"

        nonregular_profile = _profile_id()
        nonregular = self._path(tmp_path, nonregular_profile)
        nonregular.mkdir()
        refused, refused_dek = resume_profile_session(
            storage_root=tmp_path,
            profile_id=nonregular_profile,
            custody_generation=1,
            dek_epoch=_EPOCH,
            now=_NOW,
        )
        assert refused.refusal is ProfileSessionRefusalReason.MALFORMED
        assert refused_dek is None
        assert nonregular.is_dir()


class TestPendingRetirementRecovery:
    """Fresh-process recovery preserves an unavailable keyring's exact evidence."""

    @staticmethod
    def _prepare_sidecar(tmp_path: Path, profile_id: UUID) -> Path:
        path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
        ensure_profile_custody_local_directory(path.parent.parent)
        ensure_profile_custody_local_directory(path.parent)
        return path

    @staticmethod
    def _recover_in_fresh_process(tmp_path: Path, profile_id: UUID) -> str:
        script = """
from datetime import datetime
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import resume_profile_session

outcome, _ = resume_profile_session(
    storage_root=Path(__import__('sys').argv[1]),
    profile_id=UUID(__import__('sys').argv[2]),
    custody_generation=1,
    dek_epoch='test-dek-epoch-1',
    now=datetime.fromisoformat('2026-08-14T12:00:00+00:00'),
)
print(outcome.refusal.value if outcome.refusal is not None else 'resumed')
"""
        completed = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned recovery driver
            [sys.executable, "-c", script, str(tmp_path), str(profile_id)],
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            encoding="utf-8",
            text=True,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    def test_crash_before_successor_key_storage_preserves_or_converges_the_prepared_receipt(
        self,
        tmp_path: Path,
    ) -> None:
        """A process dies after journal publication but before keychain storage."""
        profile_id = _profile_id()
        self._prepare_sidecar(tmp_path, profile_id)
        successor = _receipt_bytes(
            _wrap(session_key=secrets.token_bytes(32), dek=secrets.token_bytes(32), profile_id=profile_id),
        )
        journal_path = _profile_session_retirement_path(storage_root=tmp_path, profile_id=profile_id)
        journal = _pending_retirement_bytes(profile_id=profile_id, predecessor=None, successor=successor)
        compare_and_replace_profile_custody_local_record(
            journal_path,
            expected=None,
            replacement=journal,
            maximum_bytes=24 * 1024,
        )

        recovered = self._recover_in_fresh_process(tmp_path, profile_id)

        if recovered == ProfileSessionRefusalReason.KEYRING_UNAVAILABLE.value:
            # The real WinVault boundary cannot prove successor deletion, so
            # it retains the bounded recovery instruction rather than hiding
            # an uncertain orphan behind a process-scoped login.
            assert journal_path.read_bytes() == journal
        else:
            assert recovered == ProfileSessionRefusalReason.ABSENT.value
            assert not journal_path.exists()

    def test_crash_after_displaced_retirement_before_journal_clear_preserves_or_converges(
        self,
        tmp_path: Path,
    ) -> None:
        """A fresh process completes only the exact recorded predecessor retirement."""
        profile_id = _profile_id()
        path = self._prepare_sidecar(tmp_path, profile_id)
        predecessor_record = _wrap(
            session_key=secrets.token_bytes(32),
            dek=secrets.token_bytes(32),
            profile_id=profile_id,
        )
        predecessor = _write_acceleration_receipt(
            storage_root=tmp_path,
            profile_id=profile_id,
            record=predecessor_record,
            predecessor=None,
        )
        successor_record = _wrap(
            session_key=secrets.token_bytes(32),
            dek=secrets.token_bytes(32),
            profile_id=profile_id,
        )
        successor = _receipt_bytes(successor_record)
        journal_path = _profile_session_retirement_path(storage_root=tmp_path, profile_id=profile_id)
        journal = _pending_retirement_bytes(
            profile_id=profile_id,
            predecessor=predecessor,
            successor=successor,
        )
        compare_and_replace_profile_custody_local_record(
            journal_path,
            expected=None,
            replacement=journal,
            maximum_bytes=24 * 1024,
        )
        _write_acceleration_receipt(
            storage_root=tmp_path,
            profile_id=profile_id,
            record=successor_record,
            predecessor=predecessor,
        )

        recovered = self._recover_in_fresh_process(tmp_path, profile_id)

        if recovered == ProfileSessionRefusalReason.KEYRING_UNAVAILABLE.value:
            assert journal_path.read_bytes() == journal
            assert path.read_bytes() == successor
        else:
            # On a usable keyring the deliberately absent successor account
            # becomes an ordinary logged-out receipt after predecessor
            # retirement and journal clearance.
            assert recovered == ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING.value
            assert not journal_path.exists()
            assert not path.exists()


class TestProfileSessionAcceleration:
    """Production mint/resume/revocation through the platform keychain."""

    def _mint(self, tmp_path: Path, profile_id: UUID) -> tuple[PersistedProfileSession, bytes]:
        dek = secrets.token_bytes(32)
        record = mint_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch=_EPOCH,
            dek=dek,
            now=_NOW,
            idle_minutes=_IDLE_MINUTES,
            absolute_minutes=_ABSOLUTE_MINUTES,
        )
        return record, dek

    @pytest.mark.os_keychain
    def test_mint_uses_random_session_id_and_exact_keychain_account(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        first, _ = self._mint(tmp_path, profile_id)
        second, _ = self._mint(tmp_path, profile_id)
        try:
            assert first.session_id != second.session_id
            assert (
                keyring.get_password(
                    PROFILE_SESSION_KEYCHAIN_SERVICE,
                    _account(profile_id, first.session_id),
                )
                is None
            )
            assert (
                keyring.get_password(
                    PROFILE_SESSION_KEYCHAIN_SERVICE,
                    _account(profile_id, second.session_id),
                )
                is not None
            )
            assert keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, str(profile_id)) is None
        finally:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    @pytest.mark.os_keychain
    def test_mint_then_resume_binds_exact_current_envelope_metadata(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        record, dek = self._mint(tmp_path, profile_id)
        try:
            outcome, resumed = resume_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=1,
                dek_epoch=_EPOCH,
                now=_NOW + timedelta(minutes=5),
            )
            assert outcome.resumed is True
            assert outcome.record == record
            assert resumed == dek
        finally:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    @pytest.mark.os_keychain
    def test_custody_rotation_revokes_old_receipt(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        record, _ = self._mint(tmp_path, profile_id)
        path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
        try:
            outcome, resumed = resume_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=2,
                dek_epoch=_EPOCH,
                now=_NOW + timedelta(minutes=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.CUSTODY_CHANGED
            assert resumed is None
            assert not path.exists()
            assert (
                keyring.get_password(
                    PROFILE_SESSION_KEYCHAIN_SERVICE,
                    _account(profile_id, record.session_id),
                )
                is None
            )
        finally:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    @pytest.mark.os_keychain
    def test_expired_receipt_removes_only_its_own_keychain_entry(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        record, _ = self._mint(tmp_path, profile_id)
        other_profile = _profile_id()
        other, _ = self._mint(tmp_path, other_profile)
        try:
            outcome, resumed = resume_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=1,
                dek_epoch=_EPOCH,
                now=_NOW + timedelta(minutes=_IDLE_MINUTES, seconds=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.EXPIRED_IDLE
            assert resumed is None
            assert (
                keyring.get_password(
                    PROFILE_SESSION_KEYCHAIN_SERVICE,
                    _account(profile_id, record.session_id),
                )
                is None
            )
            assert (
                keyring.get_password(
                    PROFILE_SESSION_KEYCHAIN_SERVICE,
                    _account(other_profile, other.session_id),
                )
                is not None
            )
        finally:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)
            delete_profile_session(storage_root=tmp_path, profile_id=other_profile)

    @pytest.mark.os_keychain
    def test_tampered_aad_record_is_refused_and_cleaned(self, tmp_path: Path) -> None:
        """A canonical receipt whose AAD-bound field was altered fails authentication.

        The tamper is re-encoded THROUGH the production canonical encoder on
        purpose. Rewriting the receipt with a plain ``json.dumps`` leaves bytes
        the canonical-form check refuses, so the resume returned MALFORMED from
        that check and the authenticated-data branch this test exists to cover
        was never evaluated -- for as long as the test existed, and it did not
        run at all until its module was given a lane.

        ``idle_deadline`` is the altered field because it is bound into the
        AEAD associated data, so a receipt that stays byte-canonical and
        well-formed still fails to unwrap. Extending it rather than shortening
        it also carries the record PAST the idle-expiry check above, so a pass
        here cannot be an expiry refusal wearing the tamper name.
        """
        profile_id = _profile_id()
        record, _ = self._mint(tmp_path, profile_id)
        path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
        try:
            forged = record.model_copy(update={"idle_deadline": _NOW + timedelta(hours=3)})
            path.write_bytes(_receipt_bytes(forged))
            outcome, resumed = resume_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=1,
                dek_epoch=_EPOCH,
                now=_NOW + timedelta(minutes=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.TAMPERED, (
                "a canonical receipt with an altered AAD field must fail authentication, "
                f"not any earlier check; got {outcome.refusal}"
            )
            assert resumed is None
            assert not path.exists()
            assert (
                keyring.get_password(
                    PROFILE_SESSION_KEYCHAIN_SERVICE,
                    _account(profile_id, record.session_id),
                )
                is None
            )
        finally:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    @pytest.mark.os_keychain
    def test_receipt_never_writes_plaintext_dek(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        record, dek = self._mint(tmp_path, profile_id)
        try:
            payload = profile_session_path(storage_root=tmp_path, profile_id=profile_id).read_bytes()
            assert dek not in payload
            assert base64.b64encode(dek) not in payload
            assert str(record.session_id).encode() in payload
        finally:
            delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    def test_nonpositive_windows_refuse_before_keychain_write(self, tmp_path: Path) -> None:
        profile_id = _profile_id()
        with pytest.raises(StorageValidationError):
            mint_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=1,
                dek_epoch=_EPOCH,
                dek=secrets.token_bytes(32),
                now=_NOW,
                idle_minutes=0,
                absolute_minutes=_ABSOLUTE_MINUTES,
            )
        assert not profile_session_path(storage_root=tmp_path, profile_id=profile_id).exists()
        assert not (tmp_path / ".profile-custody-root.lock").exists()
        assert not any(tmp_path.iterdir())

    def test_foreign_idle_renewal_refuses_before_custody_root_provisioning(self, tmp_path: Path) -> None:
        """A caller cannot materialise a root lock with another profile's receipt."""
        record = _wrap(session_key=secrets.token_bytes(32), dek=secrets.token_bytes(32), profile_id=_profile_id())
        with pytest.raises(StorageValidationError, match="belongs to another profile"):
            advance_persisted_profile_session_idle_deadline(
                storage_root=tmp_path,
                profile_id=_profile_id(),
                record=record,
                new_idle_deadline=_NOW + timedelta(minutes=30),
            )
        assert not (tmp_path / ".profile-custody-root.lock").exists()
        assert not any(tmp_path.iterdir())

    def test_naive_idle_renewal_refuses_before_custody_root_provisioning(self, tmp_path: Path) -> None:
        """A malformed renewal deadline cannot materialise a root lock."""
        profile_id = _profile_id()
        record = _wrap(session_key=secrets.token_bytes(32), dek=secrets.token_bytes(32), profile_id=profile_id)
        with pytest.raises(ValueError, match="timezone-aware UTC"):
            advance_persisted_profile_session_idle_deadline(
                storage_root=tmp_path,
                profile_id=profile_id,
                record=record,
                new_idle_deadline=datetime(2026, 8, 14, 12, 30, 0),
            )
        assert not (tmp_path / ".profile-custody-root.lock").exists()
        assert not any(tmp_path.iterdir())

    @pytest.mark.parametrize(
        ("profile_id", "custody_generation", "dek_epoch", "dek"),
        (
            (UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), 1, _EPOCH, secrets.token_bytes(32)),
            (_profile_id(), 0, _EPOCH, secrets.token_bytes(32)),
            (_profile_id(), 1, "", secrets.token_bytes(32)),
            (_profile_id(), 1, _EPOCH, secrets.token_bytes(31)),
        ),
        ids=("non-v4-profile", "nonpositive-generation", "empty-epoch", "wrong-dek-length"),
    )
    def test_malformed_mint_refuses_before_custody_root_provisioning(
        self,
        tmp_path: Path,
        profile_id: UUID,
        custody_generation: int,
        dek_epoch: str,
        dek: bytes,
    ) -> None:
        """Malformed mint input cannot create a durable custody coordination leaf."""
        with pytest.raises((EncryptionError, ValueError)):
            mint_profile_session(
                storage_root=tmp_path,
                profile_id=profile_id,
                custody_generation=custody_generation,
                dek_epoch=dek_epoch,
                dek=dek,
                now=_NOW,
                idle_minutes=_IDLE_MINUTES,
                absolute_minutes=_ABSOLUTE_MINUTES,
            )
        assert not (tmp_path / ".profile-custody-root.lock").exists()
        assert not any(tmp_path.iterdir())


@pytest.mark.os_keychain
def test_revocation_refuses_when_the_receipt_survives_the_clear(tmp_path: Path) -> None:
    """A receipt that cannot be cleared must not be reported as revoked.

    The compare-and-clear already computes whether the exact anchored bytes
    were removed, and the resume path branches on it. The revocation entry
    point discarded it and returned ``None``, so a login could report the
    prior profile closed while its acceleration receipt was still on disk --
    and the receipt is what makes a resume possible.

    The obstruction is a real open handle rather than a substituted payload.
    That matters for reachability: the row assumed the bytes had to change
    under the held per-profile lock, which is a narrow race, but an open
    handle reproduces the refusal deterministically on Windows and is the
    ordinary case -- another process reading the file, or a backup agent.
    """
    profile_id = _profile_id()
    dek = secrets.token_bytes(32)
    record = mint_profile_session(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=1,
        dek_epoch=_EPOCH,
        dek=dek,
        now=_NOW,
        idle_minutes=_IDLE_MINUTES,
        absolute_minutes=_ABSOLUTE_MINUTES,
    )
    path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    try:
        with path.open("rb"):
            with pytest.raises(AccelerationReceiptRevocationError):
                delete_profile_session(storage_root=tmp_path, profile_id=profile_id)
            assert path.exists(), "the refusal must be truthful: the receipt is still there"
        # The keychain secret is ALREADY gone at this point: revocation deletes
        # it before attempting the clear. So a refusal leaves an orphaned
        # receipt whose key is revoked, not a resumable one -- which bounds the
        # exposure without making the silent success acceptable, since the
        # caller is still told the profile is closed when an artefact remains.
        assert keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, _account(profile_id, record.session_id)) is None
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.os_keychain
def test_revocation_returns_normally_when_the_receipt_is_cleared(tmp_path: Path) -> None:
    """The control: an unobstructed revocation still succeeds and removes it.

    Without this the refusal above is satisfied by a revocation that raises
    unconditionally, which would break every logout.
    """
    profile_id = _profile_id()
    self_dek = secrets.token_bytes(32)
    mint_profile_session(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=1,
        dek_epoch=_EPOCH,
        dek=self_dek,
        now=_NOW,
        idle_minutes=_IDLE_MINUTES,
        absolute_minutes=_ABSOLUTE_MINUTES,
    )
    path = profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    assert path.exists()

    delete_profile_session(storage_root=tmp_path, profile_id=profile_id)

    assert not path.exists(), "an unobstructed revocation removes the receipt"
