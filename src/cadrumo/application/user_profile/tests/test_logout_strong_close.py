"""Logout strong close: both session halves gone, and a clean second pass.

Real adapters throughout — a genuine bucket, the real file master-key
backend, the real OS keychain, and real files under a per-test storage
root. The proofs that matter are negative: after logout neither half of
the split-knowledge session survives, so neither a disk-only nor a
keychain-only attacker holds anything, and a resume can no longer
reconstruct the DEK.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key import (
    close_active_bucket_session,
    current_active_bucket_session,
    delete_profile_session,
    load_profile_session_key,
    login_throttle_path,
    profile_session_path,
    record_login_failure,
)
from ....core import ProfileSessionRefusalReason, read_pointer, resolve_active_bucket_id
from ....core.config import override_settings
from ....core.resources import resources
from ....core.time import now as _now
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import schema_valid_placeholder
from ...workflow import WorkflowState
from .._login_session import login_profile, resume_active_profile_session
from .._orchestration import (
    ProfileLogoutOverrideError,
    logout_active_profile,
    profile_create_storage_span,
    register_active_profile,
)
from .conftest import lay_down_session_for_live_login, require_keychain_custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "5e5e5e5e-5e5e-4e5e-8e5e-5e5e5e5e5e5e"


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            yield storage_root
        finally:
            close_active_bucket_session()
            delete_profile_session(storage_root=storage_root, bucket_id=_PROFILE_ID)


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        facts.extend(
            UserProfileFact(path=f"{section.key}.{field.key}", value=schema_valid_placeholder(field))
            for field in section.fields
            if field.required
        )
    return tuple(facts)


def _create_and_login(schema: ProfileSchemaDefinition) -> None:
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        register_active_profile(
            WorkflowState(),
            profile_id=_PROFILE_ID,
            display_name="Logout operator",
            facts=_required_facts(schema),
            schema=schema,
            enforce_unique_tax_id=False,
            routing_profile_id=routing_profile_id,
        )
    close_active_bucket_session()
    login_profile()


class TestStrongClose:
    """Logout removes every artefact that could re-open the session."""

    def test_logout_removes_the_persisted_record_and_clears_the_pointer(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """Every artefact logout can destroy without consulting the keychain.

        The security-load-bearing negative lives here: the on-disk half is
        gone and a resume can no longer reconstruct the DEK. Both are
        decided before ``resume_profile_session`` reaches the keychain, so
        this stays verifiable on a host that cannot custody a session key.
        The sibling case below owns the keychain half.
        """
        _create_and_login(schema)
        lay_down_session_for_live_login(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        record_path = profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        assert record_path.is_file()
        assert current_active_bucket_session() is not None

        signed_out = logout_active_profile()

        assert signed_out == _PROFILE_ID
        # 1. the live session is sealed and evicted
        assert current_active_bucket_session() is None
        # 2. the on-disk half of the split-knowledge session is gone
        assert not record_path.is_file()
        # 3. the pointer is cleared
        assert read_pointer(_storage_root) is None
        assert resolve_active_bucket_id() is None
        # 4. nothing can reconstruct the session any more
        assert resume_active_profile_session(bucket_id=_PROFILE_ID) is ProfileSessionRefusalReason.ABSENT
        assert current_active_bucket_session() is None

    @pytest.mark.os_keychain
    def test_logout_removes_the_keychain_half_of_the_session(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """The other half of the split-knowledge pair: the custodied key.

        Reading the session key back is the whole assertion subject, so
        unlike its sibling this case genuinely requires a usable OS
        keychain and states that precondition up front.
        """
        _create_and_login(schema)
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        assert load_profile_session_key(bucket_id=_PROFILE_ID) is not None

        logout_active_profile()

        assert load_profile_session_key(bucket_id=_PROFILE_ID) is None

    def test_logout_seals_the_live_session_key_buffers(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        _create_and_login(schema)
        session = current_active_bucket_session()
        assert session is not None
        assert session.sealed is False

        logout_active_profile()

        assert session.sealed is True
        from ....adapters.persistence.storage.bucket import BucketLockedError

        with pytest.raises(BucketLockedError):
            _ = session.dek

    def test_logout_clears_the_failed_login_backoff(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_and_login(schema)
        record_login_failure(storage_root=_storage_root, bucket_id=_PROFILE_ID, now=_now())
        assert login_throttle_path(storage_root=_storage_root, bucket_id=_PROFILE_ID).is_file()

        logout_active_profile()

        assert not login_throttle_path(storage_root=_storage_root, bucket_id=_PROFILE_ID).is_file()


class TestIdempotence:
    """A second logout, or one with nothing signed in, is a clean no-op."""

    def test_second_logout_is_a_clean_no_op(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_and_login(schema)
        assert logout_active_profile() == _PROFILE_ID

        assert logout_active_profile() is None

        assert current_active_bucket_session() is None
        assert read_pointer(_storage_root) is None
        assert not profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_ID).is_file()

    def test_logout_without_any_session_is_a_no_op(self) -> None:
        assert logout_active_profile() is None
        assert current_active_bucket_session() is None

    def test_login_after_logout_mints_a_fresh_session(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_and_login(schema)
        first_session = current_active_bucket_session()
        assert first_session is not None
        original_opened_at = first_session.opened_at
        # Give logout a real record to destroy, so the re-login below cannot
        # trivially miss a resume for want of anything to resume from.
        lay_down_session_for_live_login(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        record_path = profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        assert record_path.is_file()

        logout_active_profile()
        assert not record_path.is_file()

        # The pointer was cleared, so the profile must be named again; the
        # new session is a genuine re-authentication, not a resumed one.
        outcome = login_profile(name="Logout operator")

        assert outcome.already_authenticated is False
        assert outcome.authenticated_at >= original_opened_at


class TestOverrideRefusal:
    """An explicit per-invocation override still refuses, untouched."""

    def test_logout_refuses_under_an_active_profile_override(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        _create_and_login(schema)
        # Lay a record down so "nothing was torn down" is a real claim with a
        # destroyable artefact behind it rather than a vacuous one.
        lay_down_session_for_live_login(storage_root=_storage_root, bucket_id=_PROFILE_ID)

        with override_settings(cadrumo_active_profile=_PROFILE_ID), pytest.raises(ProfileLogoutOverrideError):
            logout_active_profile()

        # The refusal happens before any teardown: nothing was signed out.
        assert current_active_bucket_session() is not None
        assert profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_ID).is_file()
        assert read_pointer(_storage_root) is not None
