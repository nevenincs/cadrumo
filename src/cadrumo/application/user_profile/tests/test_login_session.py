"""Login orchestration over real storage: mint, idempotence, and handover.

Real adapters throughout — a genuine bucket created through the profile
create span, the real file master-key backend with its Argon2id unwrap,
the real OS keychain custody of the session key, and real files under a
per-test storage root. No mocks, fakes, or monkeypatching: a wrong
passphrase is driven through the production ``passphrase_callback``
parameter the CLI's ``--secrets-stdin`` channel uses.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import MasterKeyPassphraseMismatchError
from ....adapters.persistence.storage.master_key import (
    close_active_bucket_session,
    current_active_bucket_session,
    delete_profile_session,
    profile_session_path,
    record_login_failure,
)
from ....core import ProfileSessionRefusalReason, read_pointer, resolve_active_bucket_id
from ....core.config import load_settings
from ....core.resources import resources
from ....core.time import now as _now
from ....domain.user_profile import ProfileNotFoundError, ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow import WorkflowState
from .._login_session import (
    ProfileLoginThrottledError,
    login_profile,
    resume_active_profile_session,
)
from .._orchestration import profile_create_storage_span, register_active_profile
from .conftest import lay_down_session_for_live_login, require_keychain_custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_A = "3c3c3c3c-3c3c-4c3c-8c3c-3c3c3c3c3c3c"
_PROFILE_B = "4d4d4d4d-4d4d-4d4d-8d4d-4d4d4d4d4d4d"
# A deliberately-invalid passphrase: the point is that it does NOT unwrap.
_WRONG_PASSPHRASE = "definitely-not-the-right-passphrase"  # noqa: S105


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path) -> Iterator[Path]:
    """Run against an empty real storage root, purging keychain state after."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            yield storage_root
        finally:
            close_active_bucket_session()
            for bucket_id in (_PROFILE_A, _PROFILE_B):
                delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        facts.extend(
            UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder")
            for field in section.fields
            if field.required
        )
    return tuple(facts)


def _create_profile(schema: ProfileSchemaDefinition, *, profile_id: str, label: str) -> None:
    """Create one real profile bucket and leave no session open."""
    with profile_create_storage_span(profile_id) as routing_profile_id:
        register_active_profile(
            WorkflowState(),
            profile_id=profile_id,
            display_name=label,
            facts=_required_facts(schema),
            schema=schema,
            enforce_unique_tax_id=False,
            routing_profile_id=routing_profile_id,
        )
    close_active_bucket_session()


class TestFirstLogin:
    """A first login authenticates, opens a session, and mints a resumable record."""

    @pytest.mark.os_keychain
    def test_first_login_mints_a_resumable_persisted_session(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Login operator")

        outcome = login_profile()

        # Minting the record IS the custody step, and resuming it below needs
        # the session key back, so this case cannot run without a keychain.
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_A)

        assert outcome.bucket_id == _PROFILE_A
        assert outcome.label == "Login operator"
        assert outcome.already_authenticated is False
        assert outcome.closed_previous_bucket_id is None
        assert outcome.session_persisted is True
        assert outcome.idle_deadline <= outcome.absolute_deadline
        assert outcome.absolute_deadline > outcome.authenticated_at

        # The persisted artefact exists and the live session is bound.
        assert profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_A).is_file()
        live = current_active_bucket_session()
        assert live is not None
        assert live.bucket_id == _PROFILE_A

        # A later process resumes it with no authentication at all: drop the
        # in-process session, then resume purely from the persisted artefacts.
        close_active_bucket_session()
        assert current_active_bucket_session() is None
        assert resume_active_profile_session(bucket_id=_PROFILE_A) is None
        resumed = current_active_bucket_session()
        assert resumed is not None
        assert resumed.bucket_id == _PROFILE_A
        assert resumed.absolute_deadline == outcome.absolute_deadline

    def test_login_selects_and_authenticates_a_named_profile(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Named operator")
        # Point the pointer away so the NAME argument is doing the selection.
        from .._profile_pointer_transaction import active_profile_pointer_transaction

        with active_profile_pointer_transaction() as transaction:
            transaction.clear()
        assert resolve_active_bucket_id() is None

        outcome = login_profile(name="Named operator")

        assert outcome.bucket_id == _PROFILE_A
        assert outcome.already_authenticated is False
        pointer = read_pointer(_storage_root)
        assert pointer is not None
        assert pointer.bucket_id == _PROFILE_A

    def test_login_refuses_an_unknown_name(self, schema: ProfileSchemaDefinition) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Known operator")
        with pytest.raises(ProfileNotFoundError):
            login_profile(name="no-such-profile")


@pytest.mark.os_keychain
class TestIdempotentGuard:
    """A retry against a still-valid session is a no-op, not a second login.

    Both cases are custody-bound: the guard fires only when the persisted
    record can be RESUMED, and resuming unwraps the DEK under the session
    key held in the OS credential store. Laying a record down without
    custody would not reach the guard, so neither case has a
    keychain-free half to keep in the default lane.
    """

    def test_valid_session_retry_is_a_no_op(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Retry operator")
        first = login_profile()
        # The guard fires only when the persisted record can be resumed, which
        # unwraps the DEK under the keychain-held session key.
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_A)
        record_path = profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_A)
        first_bytes = record_path.read_bytes()

        # A fresh process: no live session, only the persisted artefacts.
        close_active_bucket_session()
        second = login_profile()

        assert second.already_authenticated is True
        # The ORIGINAL login instant and cap survive: no re-stamp, no new record.
        assert second.authenticated_at == first.authenticated_at
        assert second.absolute_deadline == first.absolute_deadline
        assert second.bucket_id == first.bucket_id
        assert second.closed_previous_bucket_id is None
        # The record may only have advanced its sliding idle deadline; the
        # absolute cap is what proves no second session was minted.
        assert record_path.is_file()
        assert second.idle_deadline >= first.idle_deadline
        assert len(record_path.read_bytes()) == len(first_bytes)

    def test_retry_with_a_wrong_passphrase_still_no_ops(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """The guard returns before authentication, so no passphrase is consulted."""
        _create_profile(schema, profile_id=_PROFILE_A, label="Guarded operator")
        first = login_profile()
        # Without custody the guard cannot fire and the wrong passphrase reaches
        # the unwrap, raising the very error this case exists to deny. State the
        # precondition so that failure cannot be misread as a guard defect.
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_A)
        close_active_bucket_session()

        second = login_profile(passphrase_callback=lambda: _WRONG_PASSPHRASE)

        assert second.already_authenticated is True
        assert second.authenticated_at == first.authenticated_at


class TestCrossProfileHandover:
    """Logging into a different profile closes the previous session first."""

    def test_handover_closes_the_previous_profile_session(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="First operator")
        _create_profile(schema, profile_id=_PROFILE_B, label="Second operator")

        login_profile(name="First operator")
        # Give the handover a real record to tear down. The teardown path is
        # keychain-free end to end — the record delete, and the ABSENT refusal
        # below, are both decided before any keychain call — so laying the
        # record down directly keeps this case honest on a host that cannot
        # custody a session key. Whether login MINTS one is a different claim,
        # owned by TestFirstLogin.
        lay_down_session_for_live_login(storage_root=_storage_root, bucket_id=_PROFILE_A)
        assert profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_A).is_file()

        handover = login_profile(name="Second operator")

        assert handover.bucket_id == _PROFILE_B
        assert handover.closed_previous_bucket_id == _PROFILE_A
        assert handover.already_authenticated is False
        # The previous profile's on-disk half is gone, and nothing can
        # reconstruct its key material any more.
        assert not profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_A).is_file()
        assert resume_active_profile_session(bucket_id=_PROFILE_A) is ProfileSessionRefusalReason.ABSENT
        # The new profile is the selected one and holds the live session.
        live = current_active_bucket_session()
        assert live is not None
        assert live.bucket_id == _PROFILE_B
        pointer = read_pointer(_storage_root)
        assert pointer is not None
        assert pointer.bucket_id == _PROFILE_B


class TestThrottleAndAuthenticationFailure:
    """The backoff is evaluated before any key derivation runs."""

    def test_wrong_passphrase_refuses_and_records_a_failure(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Throttle operator")

        with pytest.raises(MasterKeyPassphraseMismatchError):
            login_profile(passphrase_callback=lambda: _WRONG_PASSPHRASE)

        # No session, no persisted record: the failed login left nothing behind.
        assert current_active_bucket_session() is None
        assert not profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_A).is_file()

        # The recorded failure now throttles the immediate retry, and the
        # refusal carries the remaining wait for the operator.
        with pytest.raises(ProfileLoginThrottledError) as refusal:
            login_profile()
        assert refusal.value.remaining_seconds > 0
        assert refusal.value.context is not None
        assert refusal.value.context["seconds"] == str(refusal.value.remaining_seconds)

    def test_throttle_clears_once_the_backoff_window_elapses(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Backoff operator")
        instant = _now()
        record_login_failure(storage_root=_storage_root, bucket_id=_PROFILE_A, now=instant)

        with pytest.raises(ProfileLoginThrottledError):
            login_profile(now=instant)

        # Waiting the window out clears the refusal; a successful login then
        # resets the counter so the next attempt is unthrottled.
        outcome = login_profile(now=instant + timedelta(seconds=120))
        assert outcome.already_authenticated is False
        assert load_settings().cadrumo_local_storage_root == _storage_root


class TestSessionPersistenceContract:
    """``session_persisted`` couples to disk, and a degraded host fails closed.

    ``ProfileLoginOutcome.session_persisted`` is the application-layer claim
    for whether the login left a resumable record behind, and this module
    OWNS it — every other assertion of it reaches it only transitively,
    through a CLI subprocess. Persisted-session custody hard-requires the OS
    keychain: a host that cannot custody the session key writes no artefact
    at all rather than spilling one half of the split-knowledge pair to disk,
    so the login degrades to a process-scoped session instead of refusing.
    This case holds on either kind of host by coupling the claim to the
    filesystem rather than presuming custody.
    """

    def test_persistence_claim_couples_to_the_on_disk_record(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_profile(schema, profile_id=_PROFILE_A, label="Contract operator")

        outcome = login_profile()

        # The login succeeds whatever the custody outcome: a live in-process
        # session is bound before the mint is even attempted, so the
        # process-scoped half of the contract holds on every host.
        assert outcome.already_authenticated is False
        live = current_active_bucket_session()
        assert live is not None
        assert live.bucket_id == _PROFILE_A

        # THE COUPLING: the claim must match the filesystem. A login reporting
        # a saved session without writing one -- or writing one while
        # reporting otherwise -- fails here on any host.
        record_path = profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_A)
        on_disk = record_path.is_file()
        assert outcome.session_persisted is on_disk, (
            f"session_persisted={outcome.session_persisted} disagrees with the on-disk "
            f"record at {record_path} (is_file={on_disk})"
        )

        if not outcome.session_persisted:
            # Fail-closed: the degraded login writes no persisted artefact at
            # all, and a later process therefore finds nothing to reconstruct.
            # The shared resume authority reads disk directly (never the live
            # session) and decides ABSENT before it ever consults the
            # keychain, so this branch is reachable on a credential-less host.
            # Drop the process-scoped session first so the "a later process
            # finds nothing" framing is literal.
            assert not record_path.is_file()
            close_active_bucket_session()
            assert resume_active_profile_session(bucket_id=_PROFILE_A) is ProfileSessionRefusalReason.ABSENT
        else:
            # Custody host: the record is on disk, the resumable half of the
            # split-knowledge pair.
            assert record_path.is_file()
