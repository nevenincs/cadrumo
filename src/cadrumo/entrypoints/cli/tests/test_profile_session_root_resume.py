"""Root-callback session resume: silent when valid, instructive when not.

The CLI root callback no longer implicitly unlocks the profile. It
resumes the persisted session ``aeat config login`` minted, or refuses
naming that verb. These tests drive the REAL CLI against a REAL bucket
created through current credential registration, with real records, real
AEAD wraps, and real files.

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

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage import custody
from ....adapters.persistence.storage.custody import (
    delete_profile_session,
    mint_profile_session,
    profile_session_path,
)
from ....adapters.persistence.storage.master_key import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import ProfileSessionRefusalReason
from ....core.config import load_settings, override_settings
from ....core.time import now as _now
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli, semantic_cli_output
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from .._common import cli_policy_refusal_projection
from .._errors import CliRefusedBoundaryError, error_boundary_under_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_LABEL = "session-operator"
_PASSPHRASE = "session-root-passphrase"  # noqa: S105
_PROFILE_SECRET_PAYLOAD = json.dumps({"profile_passphrase": _PASSPHRASE})
_LOGIN_SECRET_PAYLOAD = json.dumps({"passphrase": _PASSPHRASE})


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
                delete_profile_session(storage_root=storage_root, profile_id=UUID(bucket_id))
            dispose_engine()


def _bucket_id_or_none(label: str = _LABEL) -> str | None:
    from ....application.workflow import read_profile_bucket

    pointer = read_profile_bucket(label)
    return pointer.bucket_id if pointer is not None else None


def _create_profile(label: str = _LABEL, *, tax_id: str = "12345678Z") -> str:
    """Register one current credential capsule and return its immutable UUID."""
    from ....application.user_profile import register_profile_with_credentials

    del tax_id  # Current registration creates the initial incomplete fact record.
    created = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=label, passphrase=_PASSPHRASE
    )
    close_active_bucket_session()
    assert _bucket_id_or_none(label) == created.bucket_id
    return created.bucket_id


def _login() -> None:
    """Establish the persisted session through the application login door."""
    from ....application.user_profile import login_profile

    login_profile(passphrase_callback=lambda: _PASSPHRASE)


def _login_and_require_persistence(storage_root: Path, bucket_id: str) -> None:
    """Log in and assert the persisted record this test needs actually exists.

    Login itself succeeds process-scoped on a host with no usable OS keychain
    (it warns and skips the mint rather than writing key material to disk), so
    without this precondition a cross-process resume test would fail later with
    a misleading "you are not logged in" refusal that reads like a resume
    defect. Asserting it here pins the failure on the missing custody instead.
    """
    _login()
    assert profile_session_path(storage_root=storage_root, profile_id=UUID(bucket_id)).is_file(), (
        "login did not persist a session record, so cross-process resume cannot be exercised; "
        "this host has no usable OS keychain to custody the session key"
    )


def _resume(bucket_id: str) -> ProfileSessionRefusalReason | None:
    """Drive the shared resume authority the root callback itself calls."""
    from ....application.user_profile import bind_resumed_profile_session

    return bind_resumed_profile_session(bucket_id=bucket_id)


def _invoke_decrypting_verb_without_the_secret_channel():
    """Run a real decrypting verb with no headless passphrase configured.

    Clearing the passphrase is what makes this test meaningful: with the
    substrate passphrase unavailable, ONLY a resumed persisted session
    can unlock the profile, so a passing invocation proves resume rather
    than the retired implicit unlock.
    """
    with override_settings(cadrumo_secret_passphrase=None):
        return invoke_cached_cli(["--format", "json", "app", "ledger", "list"])


def _invoke_with_root_profile_secret(arguments: list[str]):
    """Establish the exact root-gate session before dispatching ``arguments``."""
    return invoke_cached_cli(
        ["--profile-secrets-stdin", *arguments],
        input=_PROFILE_SECRET_PAYLOAD,
    )


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

        from ....application.user_profile import bind_resumed_profile_session

        close_active_bucket_session()
        assert bind_resumed_profile_session(bucket_id=bucket_id) is None
        resumed = current_active_bucket_session()
        assert resumed is not None
        # The sliding window rolled forward, while the absolute cap - fixed at
        # the original login - is untouched, so activity cannot extend a session
        # past its lifetime.
        assert resumed.idle_deadline >= original_idle_deadline
        assert resumed.absolute_deadline == original_absolute


class TestProfileDiscoveryStaysReachableWhileLoggedOut:
    """Enumerating profiles never requires the login it tells you to run.

    ``config profile list`` answers "which profiles exist, and what is the
    label ``config login`` wants". Gating it behind that login is a deadlock:
    the answer is only reachable once you already know it. The verb reads the
    plaintext per-bucket ``manifest.toml`` files and decrypts nothing, so it
    needs no session to be correct.

    The substrate passphrase is cleared throughout. Without that programmatic
    channel would unlock the profile outright and the test would pass on a
    bypass rather than on the exemption it exists to pin.
    """

    def test_profile_list_succeeds_with_no_session(self) -> None:
        _create_profile()
        # Never logged in: no persisted session exists at all.
        close_active_bucket_session()

        with override_settings(cadrumo_secret_passphrase=None):
            result = invoke_cached_cli(["--format", "json", "config", "profile", "list"])

        assert result.exit_code == 0, result.output
        document = json.loads(semantic_cli_output(result))
        assert document["status"] != "error"
        # The created profile is actually enumerated - an empty-but-successful
        # listing would satisfy a bare exit-code assertion while still hiding
        # the label the operator came for.
        assert [row for row in document["result"]["profiles"] if row["name"] == _LABEL], document

    def test_the_login_gate_still_refuses_a_decrypting_verb(self) -> None:
        """The exemption opened one door, not the gate.

        Same logged-out state as above, driven through a verb that genuinely
        decrypts. If this ever passes, ``profile list`` is reachable because
        the session gate stopped working rather than because the verb needs no
        session, and the test above proves nothing.
        """
        _create_profile()
        close_active_bucket_session()

        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)


@pytest.mark.os_keychain
class TestFailClosedRefusals:
    """Absent and expired sessions refuse, naming the verb that fixes it."""

    def test_unnamed_validate_is_gated_as_an_active_profile_read(self) -> None:
        _create_profile()
        close_active_bucket_session()

        with override_settings(cadrumo_secret_passphrase=None):
            result = invoke_cached_cli(["--format", "json", "config", "profile", "validate"])

        assert result.exit_code != 0
        document = json.loads(semantic_cli_output(result))
        assert document["error"]["context"]["reason"] == "absent", document
        assert document["error"]["category"] == "REFUSED", document

    def test_explicit_validate_is_not_preempted_by_the_active_profile_gate(self) -> None:
        _create_profile()
        close_active_bucket_session()

        result = _invoke_with_root_profile_secret(
            ["--format", "json", "config", "profile", "validate", _LABEL],
        )

        document = json.loads(semantic_cli_output(result))
        assert document["command"] == "config.profile.validate", document
        assert "error" not in document, document

    def test_unnamed_history_reads_the_authenticated_active_profile(self) -> None:
        bucket_id = _create_profile()

        with open_test_profile_session(bucket_id):
            result = invoke_cached_cli(["--format", "json", "config", "profile", "history"])

        assert result.exit_code == 0, result.output
        document = json.loads(semantic_cli_output(result))
        assert document["command"] == "config.bucket.history", document
        assert document["active_profile"] == _LABEL, document
        assert document["result"]["bucket_id"] == "<bucket-id>", document

    def test_explicit_history_reads_the_requested_profile_repository(self) -> None:
        first_bucket_id = _create_profile("history-first")
        from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
        from ....adapters.persistence.storage import secure_object_repository_for_bucket

        with open_test_profile_session(first_bucket_id):
            first_catalogue = BucketEventHistoryRepository(
                objects=secure_object_repository_for_bucket(first_bucket_id),
            ).load()
        assert first_catalogue.events
        first_event = next(iter(first_catalogue.events.values()))

        _create_profile("history-second", tax_id="87654321X")
        with open_test_profile_session(first_bucket_id):
            result = invoke_cached_cli(
                [
                    "--format",
                    "json",
                    "config",
                    "profile",
                    "history",
                    "history-first",
                    "--object-id",
                    first_event.object_id,
                ],
            )

        assert result.exit_code == 0, result.output
        document = json.loads(semantic_cli_output(result))
        assert document["active_profile"] == "history-first", document
        assert document["result"]["bucket_id"] == "<bucket-id>", document
        assert document["result"]["events"], document

    def test_absent_session_refuses_naming_login(self) -> None:
        _create_profile()
        # Never logged in: no persisted session exists at all.
        close_active_bucket_session()

        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)

    def test_absent_session_login_action_keeps_the_executable_profile_label(self) -> None:
        """The typed login action carries the public label, never the bucket UUID."""
        bucket_id = _create_profile()
        close_active_bucket_session()

        json_result = _invoke_decrypting_verb_without_the_secret_channel()
        assert json_result.exit_code != 0
        json_text = semantic_cli_output(json_result)
        document = json.loads(json_text)
        action = document["error"]["action"]
        assert document["active_profile"] == _LABEL
        assert action["action"]["action"]["action_id"] == "operator.profile.login"
        assert action["evidence"][0]["values"]["profile_name"] == _LABEL
        assert action["argument_bindings"] == [
            {
                "argument_name": "name",
                "status": "resolved",
                "value": _LABEL,
                "source": "operator_action.verdict_context",
                "source_key": "name",
                "source_evidence_id": None,
            },
        ]
        assert bucket_id not in json_text

        with override_settings(cadrumo_secret_passphrase=None):
            text_result = invoke_cached_cli(["app", "ledger", "list"])
        assert text_result.exit_code != 0
        text = semantic_cli_output(text_result)
        assert f'"value":"{_LABEL}"' in text
        assert bucket_id not in text

        dispatched = invoke_cached_cli(
            ["config", "login", _LABEL, "--secrets-stdin"],
            input=_LOGIN_SECRET_PAYLOAD,
        )
        assert dispatched.exit_code == 0, dispatched.output

    def test_absent_session_root_refusal_carries_the_login_action(self) -> None:
        _create_profile()
        close_active_bucket_session()

        with (
            override_settings(cadrumo_secret_passphrase=None),
            error_boundary_under_test(),
            pytest.raises(CliRefusedBoundaryError) as raised,
        ):
            cadrumo_click_command().main(
                args=["--format", "json", "app", "ledger", "list"],
                prog_name="aeat",
                standalone_mode=False,
            )

        projection = cli_policy_refusal_projection(raised.value)
        assert projection is not None
        assert projection.requested_leaf is not None
        assert projection.requested_leaf.subject_leaf_key == "ledger.list"
        assert projection.precondition_action.failed_condition_id == "profile.session.logged_in"
        assert projection.precondition_action.action is not None
        assert projection.precondition_action.action.action_id == "operator.profile.login"
        assert projection.precondition_action.argument_bindings[0].value == _LABEL

    def test_idle_expiry_refuses(self, _isolated_root: Path) -> None:
        bucket_id, dek = self._aged_session_material(storage_root=_isolated_root, minutes=20)
        assert profile_session_path(storage_root=_isolated_root, profile_id=UUID(bucket_id)).is_file()

        # The elapsed sliding window is what refuses, and the lapsed record is
        # deleted rather than left to be retried.
        assert _resume(bucket_id) is ProfileSessionRefusalReason.EXPIRED_IDLE, (
            "an elapsed idle deadline must refuse on the idle branch"
        )
        assert not profile_session_path(storage_root=_isolated_root, profile_id=UUID(bucket_id)).is_file()

        # The operator-facing half: the same lapse refuses the real verb and
        # names the verb that fixes it.
        self._write_aged_session(storage_root=_isolated_root, bucket_id=bucket_id, dek=dek, minutes=20)
        result = _invoke_decrypting_verb_without_the_secret_channel()

        assert result.exit_code != 0
        assert "aeat config login" in semantic_cli_output(result)
        assert not profile_session_path(storage_root=_isolated_root, profile_id=UUID(bucket_id)).is_file()

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
        assert not profile_session_path(storage_root=_isolated_root, profile_id=UUID(bucket_id)).is_file()

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
        assert not profile_session_path(storage_root=_isolated_root, profile_id=UUID(bucket_id)).is_file()

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
        delete_profile_session(storage_root=storage_root, profile_id=UUID(bucket_id))
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
        """Mint an actual current receipt with a deliberately old issue time."""

        profile_id = UUID(bucket_id)
        envelope = custody.load_committed_profile_password_material(profile_id, root=storage_root).envelope
        mint_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=envelope.password_generation,
            dek_epoch=envelope.dek_epoch,
            dek=dek,
            now=_now() - timedelta(minutes=minutes),
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
        )


class TestAmbientSecretIsNotACliChannel:
    """Configured substrate material cannot authenticate a CLI invocation."""

    def test_configured_passphrase_is_ignored_without_an_explicit_root_channel(self) -> None:
        _create_profile()
        close_active_bucket_session()
        assert load_settings().cadrumo_secret_passphrase is not None

        result = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

        assert result.exit_code == 2, result.output
