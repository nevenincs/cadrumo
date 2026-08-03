"""Destroying a profile takes its session artefacts with it.

Login mints a keychain entry per bucket, but only ``logout`` and the
login-time handover ever removed one. Nothing reaped on a DESTROY path, so
every profile deleted, reset, or rolled back without an explicit logout left
its entry behind permanently — and the OS credential store is finite. A
saturated store makes ``CredWrite`` fail, at which point ``mint_profile_session``
raises and every later login silently downgrades to process-scoped
(``session_persisted: false``): "log in once" stops working machine-wide, for
every profile, with only a warning notice to show for it.

That is not hypothetical — it is how this was found, with 552 orphaned
``<uuid>@cadrumo:profile-session`` entries accumulated on one workstation.

Real adapters throughout, mirroring ``test_logout_strong_close``: a genuine
bucket, the real file master-key backend, the real OS keychain, and real files
under a per-test storage root. The split-knowledge pair is asserted in two
halves so the on-disk half stays verifiable on a host whose credential store is
unreachable, and only the keychain half carries the ``os_keychain`` marker.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import bucket_paths
from ....adapters.persistence.storage.master_key import (
    close_active_bucket_session,
    delete_profile_session,
    load_profile_session_key,
    profile_session_path,
)
from ....core.resources import resources
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import schema_valid_placeholder
from ...workflow import WorkflowState
from .._login_session import login_profile
from .._orchestration import (
    delete_profile_with_lifecycle_span,
    profile_create_storage_span,
    register_active_profile,
    remove_profile_bucket_directory,
)
from .conftest import lay_down_session_for_live_login, require_keychain_custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "7d7d7d7d-7d7d-4d7d-8d7d-7d7d7d7d7d7d"


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
            display_name="Destroy operator",
            facts=_required_facts(schema),
            schema=schema,
            enforce_unique_tax_id=False,
            routing_profile_id=routing_profile_id,
        )
    close_active_bucket_session()
    login_profile()


class TestTombstoneReapsTheSession:
    """``profile delete`` retires the session along with the profile."""

    def test_tombstone_removes_the_persisted_record(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """The half decidable without ever consulting the keychain.

        A tombstoned profile can never be logged into again, so leaving a
        resumable session record behind is both dead state and a live
        credential for a profile the operator believes they retired.
        """
        _create_and_login(schema)
        lay_down_session_for_live_login(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        record_path = profile_session_path(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        assert record_path.is_file()

        delete_profile_with_lifecycle_span(_PROFILE_ID)

        assert not record_path.is_file()

    @pytest.mark.os_keychain
    def test_tombstone_removes_the_keychain_half(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """The half that actually leaked, and the one the store runs out of.

        The on-disk record dies with the bucket directory anyway; the keychain
        entry is the one that outlives it, because it lives outside the storage
        root entirely. This is the assertion that guards the saturation.
        """
        _create_and_login(schema)
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        assert load_profile_session_key(bucket_id=_PROFILE_ID) is not None

        delete_profile_with_lifecycle_span(_PROFILE_ID)

        assert load_profile_session_key(bucket_id=_PROFILE_ID) is None


class TestDirectoryRemovalReapsTheSession:
    """The physical-erase path reaps too, including when it no-ops."""

    @pytest.mark.os_keychain
    def test_removing_the_bucket_directory_removes_the_keychain_key(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """Erasing the bucket must not strand a key outside it."""
        _create_and_login(schema)
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        close_active_bucket_session()
        assert load_profile_session_key(bucket_id=_PROFILE_ID) is not None

        remove_profile_bucket_directory(_PROFILE_ID)

        assert load_profile_session_key(bucket_id=_PROFILE_ID) is None

    @pytest.mark.os_keychain
    def test_the_key_is_reaped_even_when_the_directory_is_already_gone(
        self,
        schema: ProfileSchemaDefinition,
        _storage_root: Path,
    ) -> None:
        """The ordering that decides whether re-runs can strand a key.

        The keychain entry lives outside the bucket directory, so every path
        that reaches removal with the directory already absent — an interrupted
        erase, a re-run, an atomic-create rollback that never finished
        provisioning — would return early and strand the key if the reap sat
        behind the existence check.

        The directory is erased out from under the profile with a plain
        ``rmtree`` rather than by calling the removal twice: the first call
        would reap the key itself, leaving the second pass nothing to strand
        and the assertion vacuous. This reproduces the real shape — a previous
        erase took the directory and stopped before the key — and the removal
        must still reap on a pass that deletes no directory at all.
        """
        import shutil

        _create_and_login(schema)
        require_keychain_custody(storage_root=_storage_root, bucket_id=_PROFILE_ID)
        close_active_bucket_session()
        bucket_dir = bucket_paths(_storage_root, _PROFILE_ID).bucket_dir
        shutil.rmtree(bucket_dir, ignore_errors=True)
        assert not bucket_dir.exists()
        assert load_profile_session_key(bucket_id=_PROFILE_ID) is not None

        remove_profile_bucket_directory(_PROFILE_ID)

        assert load_profile_session_key(bucket_id=_PROFILE_ID) is None
