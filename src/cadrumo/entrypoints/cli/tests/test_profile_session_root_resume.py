"""Root-callback session resume: silent when valid, instructive when not.

The CLI root callback no longer implicitly unlocks the profile. It
resumes the persisted session ``aeat config login`` minted, or refuses
naming that verb. These tests drive the REAL CLI against a REAL bucket
created through the real ``config profile create`` flow, with real
records, real AEAD wraps, and real files.

"Fresh process" is simulated by evicting the active-session context
variable between invocations, which is exactly what a new ``aeat``
process starts with — the persisted artefacts are then the only thing
that can unlock the profile.

The two halves have different host requirements, deliberately. The
refusal branches — absent, idle-elapsed, absolute-elapsed — are decided
before the OS keychain is ever consulted, so they run anywhere and are
asserted by refusal-reason name. Silent RESUME genuinely needs the
keychain, because unwrapping the record's DEK requires the session key
held there; on a host with no usable credential store those tests fail
at an explicit precondition naming that cause rather than misreporting a
resume defect.
"""

from __future__ import annotations

import contextlib
import json
import secrets
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key import (
    close_active_bucket_session,
    current_active_bucket_session,
    delete_profile_session,
    profile_session_path,
    wrap_profile_session_dek,
    write_profile_session,
)
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import ProfileSessionRefusalReason
from ....core.config import SecretStoreBackend, load_settings, override_settings
from ....core.time import now as _now
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@contextlib.contextmanager
def _unusable_credential_store() -> Iterator[None]:
    """Make the OS credential store genuinely unreachable for the block.

    Installs ``keyring.backends.fail.Keyring``, which is the real backend the
    keyring library itself resolves on a host with no usable credential store —
    not a stand-in for one. Every custody call then refuses at the production
    probe, which carries an explicit branch for this backend.
    """
    import keyring
    from keyring.backends import fail as fail_backend

    previous = keyring.get_keyring()
    keyring.set_keyring(fail_backend.Keyring())
    try:
        yield
    finally:
        keyring.set_keyring(previous)


_LABEL = "session-operator"


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path: Path) -> Iterator[Path]:
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            yield storage_root
        finally:
            close_active_bucket_session()
            bucket_id = _bucket_id_or_none()
            if bucket_id is not None:
                delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
            dispose_engine()


def _bucket_id_or_none() -> str | None:
    from ....application.workflow import read_profile_bucket

    pointer = read_profile_bucket(_LABEL)
    return pointer.bucket_id if pointer is not None else None


def _create_profile() -> str:
    """Create a real profile through the real CLI and return its bucket id."""
    created = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            _LABEL,
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Session",
            "--surnames",
            "Operator",
            "--activity",
            "design",
        ],
    )
    assert created.exit_code == 0, created.output
    close_active_bucket_session()
    bucket_id = _bucket_id_or_none()
    assert bucket_id is not None
    return bucket_id


def _login() -> None:
    """Establish the persisted session through the application login door."""
    from ....application.user_profile import login_profile

    login_profile()


def _login_and_require_persistence(storage_root: Path, bucket_id: str) -> None:
    """Log in and assert the persisted record this test needs actually exists.

    Login itself succeeds process-scoped on a host with no usable OS keychain
    (it warns and skips the mint rather than writing key material to disk), so
    without this precondition a cross-process resume test would fail later with
    a misleading "you are not logged in" refusal that reads like a resume
    defect. Asserting it here pins the failure on the missing custody instead.
    """
    _login()
    assert profile_session_path(storage_root=storage_root, bucket_id=bucket_id).is_file(), (
        "login did not persist a session record, so cross-process resume cannot be exercised; "
        "this host has no usable OS keychain to custody the session key"
    )


def _resume(bucket_id: str) -> ProfileSessionRefusalReason | None:
    """Drive the shared resume authority the root callback itself calls."""
    from ....application.user_profile import resume_active_profile_session

    return resume_active_profile_session(bucket_id=bucket_id)


def _invoke_decrypting_verb_without_the_secret_channel():
    """Run a real decrypting verb with no headless passphrase configured.

    Clearing the passphrase is what makes this test meaningful: with the
    sanctioned headless channel unset, ONLY a resumed persisted session
    can unlock the profile, so a passing invocation proves resume rather
    than the retired implicit unlock.
    """
    with override_settings(cadrumo_secret_passphrase=None):
        return invoke_cached_cli(["--format", "json", "app", "ledger", "list"])


@pytest.mark.os_keychain
class TestSilentResume:
    """A valid persisted session unlocks later invocations with no prompt.

    Custody-bound end to end: resuming means unwrapping the record's DEK
    under the session key the OS credential store holds, so a host that
    cannot custody one cannot exhibit a silent resume at all. The
    fail-closed refusals below are the keychain-free half and stay in the
    default lane -- they are decided BEFORE any credential call.
    """

    def test_valid_session_resumes_with_no_authentication(self, _isolated_root: Path) -> None:
        bucket_id = _create_profile()
        _login_and_require_persistence(_isolated_root, bucket_id)

        # Fresh process: nothing in memory, only the persisted artefacts.
        close_active_bucket_session()
        assert current_active_bucket_session() is None

        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code == 0, result.output
        output = semantic_cli_output(result)
        assert "aeat config login" not in output
        # The verb decrypted its read model, so the session really opened.
        assert '"rows"' in output or "rows" in output

    def test_resume_advances_the_idle_deadline(self, _isolated_root: Path) -> None:
        bucket_id = _create_profile()
        _login_and_require_persistence(_isolated_root, bucket_id)
        session = current_active_bucket_session()
        assert session is not None
        original_idle_deadline = session.idle_deadline
        original_absolute = session.absolute_deadline

        close_active_bucket_session()
        result = _invoke_decrypting_verb_without_the_secret_channel()
        assert result.exit_code == 0, result.output

        from ....application.user_profile import resume_active_profile_session

        close_active_bucket_session()
        assert resume_active_profile_session(bucket_id=bucket_id) is None
        resumed = current_active_bucket_session()
        assert resumed is not None
        # The sliding window rolled forward, while the absolute cap - fixed at
        # the original login - is untouched, so activity cannot extend a session
        # past its lifetime.
        assert resumed.idle_deadline >= original_idle_deadline
        assert resumed.absolute_deadline == original_absolute


class TestFailClosedRefusals:
    """Absent and expired sessions refuse, naming the verb that fixes it."""

    def test_absent_session_refuses_naming_login(self) -> None:
        _create_profile()
        # Never logged in: no persisted session exists at all.
        close_active_bucket_session()

        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)

    def test_idle_expiry_refuses(self, _isolated_root: Path) -> None:
        bucket_id, dek = self._aged_session_material(storage_root=_isolated_root, minutes=20)
        assert profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

        # The elapsed sliding window is what refuses, and the lapsed record is
        # deleted rather than left to be retried.
        assert _resume(bucket_id) is ProfileSessionRefusalReason.EXPIRED_IDLE, (
            "an elapsed idle deadline must refuse on the idle branch"
        )
        assert not profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

        # The operator-facing half: the same lapse refuses the real verb and
        # names the verb that fixes it.
        self._write_aged_session(storage_root=_isolated_root, bucket_id=bucket_id, dek=dek, minutes=20)
        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)
        assert not profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

    def test_absolute_cap_refuses(self, _isolated_root: Path) -> None:
        # Aged well past the 240-minute cap. Mint clamps the idle deadline to the
        # absolute one, so both are elapsed here; asserting the branch by name is
        # what proves the immutable cap - not the sliding window - did the
        # refusing, since the absolute deadline is evaluated first.
        bucket_id, dek = self._aged_session_material(
            storage_root=_isolated_root,
            minutes=300,
            idle_minutes=600,
        )

        assert _resume(bucket_id) is ProfileSessionRefusalReason.EXPIRED_ABSOLUTE, (
            "a session past its absolute cap must refuse on the absolute branch"
        )
        assert not profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

        self._write_aged_session(
            storage_root=_isolated_root,
            bucket_id=bucket_id,
            dek=dek,
            minutes=300,
            idle_minutes=600,
        )
        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)
        assert not profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

    def test_unreadable_credential_store_refuses_as_custody_not_as_logout(
        self,
        _isolated_root: Path,
    ) -> None:
        """An unreachable credential store refuses on its own terms.

        The operator logged in while the credential store was healthy and it
        later became unreachable (a locked keyring, a changed logon session).
        The record is intact and unexpired, so no deadline branch fires and the
        resume reaches the keychain, which cannot answer.

        This is deliberately NOT routed to the "run `aeat config login`"
        refusal: re-authenticating cannot fix an unreachable credential store —
        the login would have nowhere to custody its session key either — so
        naming it would loop the operator. The contract is that the custody
        failure surfaces as its own typed, actionable refusal on the shared
        envelope spine rather than escaping the root callback unhandled.

        The unreachable store is CONSTRUCTED here, by installing keyring's own
        ``fail.Keyring`` — the backend the library resolves on a host with no
        usable credential store, and the exact shape the production probe has
        a named branch for. Without it the test asserted this contract against
        a record whose key was simply never stored, which is the ordinary
        logged-out state and correctly yields the
        ``KEYCHAIN_ENTRY_MISSING`` refusal instead. It therefore passed only
        on hosts whose keychain happened to be broken and failed wherever one
        worked, which is backwards.
        """
        bucket_id, _dek = self._aged_session_material(storage_root=_isolated_root, minutes=0)
        assert profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

        with _unusable_credential_store():
            result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        document = json.loads(semantic_cli_output(result))
        assert document["status"] == "error"
        error = document["error"]
        assert error["category"] == "AUTH"
        assert error["code"] == "AUTH_STORAGE_KEYRING_UNAVAILABLE"
        # The operator is handed a next action, not a dead end.
        assert error["suggestion"]

    @classmethod
    def _aged_session_material(
        cls,
        *,
        storage_root: Path,
        minutes: int,
        idle_minutes: int = 15,
    ) -> tuple[str, bytes]:
        """Create a real profile and lay down a real, already-lapsed record."""
        bucket_id = _create_profile()
        _login()
        session = current_active_bucket_session()
        assert session is not None
        dek = session.dek
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        cls._write_aged_session(
            storage_root=storage_root,
            bucket_id=bucket_id,
            dek=dek,
            minutes=minutes,
            idle_minutes=idle_minutes,
        )
        close_active_bucket_session()
        return bucket_id, dek

    @staticmethod
    def _write_aged_session(
        *,
        storage_root: Path,
        bucket_id: str,
        dek: bytes,
        minutes: int,
        idle_minutes: int = 15,
        absolute_minutes: int = 240,
    ) -> None:
        """Write a genuine session record whose clock has already run out.

        Real AEAD wrap of a real logged-in DEK, real atomic on-disk write,
        real deadline arithmetic — mirroring ``mint_profile_session`` exactly,
        including its clamp of the idle deadline to the absolute cap. Only the
        login instant is in the past, which is the state a CLI process finds
        after the operator walked away.

        The ephemeral session key is deliberately generated and dropped rather
        than placed in the OS keychain. That is not a stand-in for custody: an
        elapsed record is refused by the deadline branches of
        ``resume_profile_session``, which run BEFORE the keychain is ever
        consulted, so the expiry decision this exercises is reached identically
        either way. Keeping the record keychain-free makes expiry verifiable on
        hosts whose credential store is unreachable, and the callers assert the
        refusal branch BY NAME so a test can never pass on the unrelated
        ``KEYCHAIN_ENTRY_MISSING`` branch that a missing key would otherwise
        produce.
        """
        authenticated_at: datetime = _now() - timedelta(minutes=minutes)
        absolute_deadline = authenticated_at + timedelta(minutes=absolute_minutes)
        record = wrap_profile_session_dek(
            session_key=secrets.token_bytes(32),
            dek=dek,
            bucket_id=bucket_id,
            backend_kind=SecretStoreBackend.FILE,
            authenticated_at=authenticated_at,
            idle_deadline=min(authenticated_at + timedelta(minutes=idle_minutes), absolute_deadline),
            absolute_deadline=absolute_deadline,
        )
        write_profile_session(storage_root=storage_root, bucket_id=bucket_id, record=record)


class TestHeadlessSecretChannel:
    """The declared non-interactive secret channel keeps working unchanged."""

    def test_configured_passphrase_unlocks_without_a_persisted_session(self) -> None:
        _create_profile()
        # No login, no persisted session — only the headless secret channel,
        # which is the authentication factor supplied non-interactively.
        close_active_bucket_session()
        assert load_settings().cadrumo_secret_passphrase is not None

        result = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

        assert result.exit_code == 0, result.output
