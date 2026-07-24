"""Root-callback session resume: silent when valid, instructive when not.

The CLI root callback no longer implicitly unlocks the profile. It
resumes the persisted session ``aeat config login`` minted, or refuses
naming that verb. These tests drive the REAL CLI against a REAL bucket
created through the real ``config profile create`` flow, with real files
and the real OS keychain.

"Fresh process" is simulated by evicting the active-session context
variable between invocations, which is exactly what a new ``aeat``
process starts with — the persisted artefacts are then the only thing
that can unlock the profile.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key import (
    close_active_bucket_session,
    current_active_bucket_session,
    delete_profile_session,
    mint_profile_session,
    profile_session_path,
)
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core._config_support import SecretStoreBackend
from ....core.config import load_settings, override_settings
from ....core.time import now as _now
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

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


def _invoke_decrypting_verb_without_the_secret_channel():
    """Run a real decrypting verb with no headless passphrase configured.

    Clearing the passphrase is what makes this test meaningful: with the
    sanctioned headless channel unset, ONLY a resumed persisted session
    can unlock the profile, so a passing invocation proves resume rather
    than the retired implicit unlock.
    """
    with override_settings(cadrumo_secret_passphrase=None):
        return invoke_cached_cli(["--format", "json", "app", "ledger", "list"])


class TestSilentResume:
    """A valid persisted session unlocks later invocations with no prompt."""

    def test_valid_session_resumes_with_no_authentication(self) -> None:
        _create_profile()
        _login()

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
        _login()
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
        bucket_id = self._mint_session_aged_by(minutes=20, storage_root=_isolated_root)
        assert profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)
        # Fail-closed: the lapsed artefacts are deleted, not left to be retried.
        assert not profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

    def test_absolute_cap_refuses(self, _isolated_root: Path) -> None:
        # Aged past the 240-minute cap while the idle window is still open,
        # so only the absolute deadline can be doing the refusing.
        bucket_id = self._mint_session_aged_by(minutes=300, storage_root=_isolated_root, idle_minutes=600)

        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)
        assert not profile_session_path(storage_root=_isolated_root, bucket_id=bucket_id).is_file()

    @staticmethod
    def _mint_session_aged_by(
        *,
        minutes: int,
        storage_root: Path,
        idle_minutes: int = 15,
    ) -> str:
        """Mint a genuine session record whose clock has already run out.

        Real record, real wrap, real keychain custody — only the login
        instant is in the past, which is exactly the state a CLI process
        finds after the operator walked away.
        """
        bucket_id = _create_profile()
        _login()
        session = current_active_bucket_session()
        assert session is not None
        dek = session.dek
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        mint_profile_session(
            storage_root=storage_root,
            bucket_id=bucket_id,
            backend_kind=SecretStoreBackend.FILE,
            dek=dek,
            now=_now() - timedelta(minutes=minutes),
            idle_minutes=idle_minutes,
            absolute_minutes=240,
        )
        close_active_bucket_session()
        return bucket_id


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
