"""Crash-injection tests for the profile-bucket composed verbs.

A profile bucket's durable state spans the plaintext manifest (M), the
encrypted SQLite record (S), the keystore wrapped DEK (K), and the active-
profile pointer. The create / rename / hard-delete verbs sequence writes across
those stores; these tests interrupt each verb at its crash window and prove the
existing rollback / detection / repair surface handles the torn state.

No storage primitive is patched. The create failure is driven by a genuine
schema-validation rejection at the record-write step (an incomplete fact set);
the rename torn state is driven by running only the record-side write of the
real rename; the delete partial-directory state is driven by corrupting the
manifest after the soft tombstone. Each test carries an anti-tautology proof so
the "absent" / "detected" assertions cannot pass vacuously.

Layer note: these tests live in the storage adapter surface but drive the
composed profile verbs, which are owned by the application layer. Importing
application symbols from an adapter test is the sanctioned outer->inner
direction of the layered architecture contract.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from .....core import read_pointer
from .....core.config import load_settings
from .....domain.user_profile import ProfileSchemaValidationError, UserProfileFact
from .....tests.secure_sql import isolated_profile_storage_root
from ..bucket import bucket_paths, manifest_path
from ..master_key import bucket_dek_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_FACTS: Mapping[str, str] = {
    "identity.tax_id": "00000000T",
    "identity.name": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "provenance.source": "manual_cli",
}
_INCOMPLETE_FACTS: Mapping[str, str] = {key: value for key, value in _VALID_FACTS.items() if key != "iva.regime"}

_CRASH_PROFILE_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
_SURVIVOR_PROFILE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
_RENAME_PROFILE_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
_DELETE_PROFILE_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"


@pytest.fixture
def backend(tmp_path: Path) -> Iterator[Path]:
    """A per-test storage root with file-backed custody."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _create_profile(profile_id: str, *, label: str, facts: Mapping[str, str]) -> None:
    """Run the production atomic create span for ``profile_id``."""
    from .....application.user_profile import (
        profile_create_storage_span,
        register_active_profile,
    )
    from .....application.workflow import workflow_state_repository

    fact_tuple = tuple(UserProfileFact(path=path, value=value) for path, value in facts.items())
    with profile_create_storage_span(profile_id) as routing_profile_id:
        workflow_state_repository().update(
            lambda state: register_active_profile(
                state,
                profile_id=profile_id,
                display_name=label,
                facts=fact_tuple,
                routing_profile_id=routing_profile_id,
            ),
        )


class TestCreateProfileCrashWindow:
    """The atomic-create rollback covers the K-without-S window."""

    def test_failed_create_rolls_back_the_minted_dek_manifest_and_pointer(self, backend: Path) -> None:
        # The DEK (K) is minted by the create span BEFORE the encrypted record
        # (S) is written. An incomplete fact set makes the schema validator
        # reject the record at the S write — the K-without-S crash window. The
        # rollback must clear the minted DEK, the manifest, and the pointer.
        with pytest.raises(ProfileSchemaValidationError):
            _create_profile(_CRASH_PROFILE_ID, label="Crash target", facts=_INCOMPLETE_FACTS)

        root = load_settings().cadrumo_local_storage_root
        paths = bucket_paths(root, _CRASH_PROFILE_ID)

        assert not bucket_dek_path(storage_root=root, bucket_id=_CRASH_PROFILE_ID).is_file(), (
            "K-without-S rollback left the minted wrapped DEK behind"
        )
        assert not manifest_path(paths).is_file(), "rollback left a manifest behind"
        assert read_pointer(root) is None, "rollback left a dangling active-profile pointer"

    def test_successful_create_lands_the_dek_a_failure_must_clear(self, backend: Path) -> None:
        # Anti-tautology: a successful create genuinely mints and persists the
        # wrapped DEK, so the failure test's "DEK absent" assertion is not
        # vacuously true against a never-created bucket.
        _create_profile(_SURVIVOR_PROFILE_ID, label="Survivor", facts=_VALID_FACTS)

        root = load_settings().cadrumo_local_storage_root
        paths = bucket_paths(root, _SURVIVOR_PROFILE_ID)

        assert bucket_dek_path(storage_root=root, bucket_id=_SURVIVOR_PROFILE_ID).is_file()
        assert manifest_path(paths).is_file()
        pointer = read_pointer(root)
        assert pointer is not None
        assert pointer.bucket_id == _SURVIVOR_PROFILE_ID


class TestRenameProfileCrashWindow:
    """A crash between the record label (S) and the manifest label (M) is detected."""

    def test_partial_rename_leaves_a_drift_the_integrity_gate_refuses(self, backend: Path) -> None:
        from .....application.user_profile import (
            ProfileIntegrityError,
            ProfileRepository,
            RenameProfileCommand,
            build_lifecycle_service,
            profile_storage_session,
        )
        from ..bucket import read_manifest

        _create_profile(_RENAME_PROFILE_ID, label="Original Label", facts=_VALID_FACTS)
        root = load_settings().cadrumo_local_storage_root
        paths = bucket_paths(root, _RENAME_PROFILE_ID)

        # Drive ONLY the record-side write of the real rename (S), simulating a
        # crash before the manifest label projection (M) is rewritten. This is
        # the production lifecycle service, not a patched write.
        with profile_storage_session(_RENAME_PROFILE_ID):
            build_lifecycle_service(bucket_id=_RENAME_PROFILE_ID).rename(
                RenameProfileCommand(profile_id=_RENAME_PROFILE_ID, target_display_name="Renamed Label"),
            )

        # The stores now disagree on the label: record says "Renamed Label",
        # manifest still says "Original Label".
        assert read_manifest(paths).label == "Original Label"

        # The integrity gate run on every load refuses the drifted profile,
        # naming the label-drift stores — never serving the stale label.
        with profile_storage_session(_RENAME_PROFILE_ID), pytest.raises(ProfileIntegrityError) as excinfo:
            ProfileRepository().load(_RENAME_PROFILE_ID)
        assert excinfo.value.context is not None
        assert "label" in str(excinfo.value.context["mismatches"])

    def test_synced_rename_loads_cleanly(self, backend: Path) -> None:
        # Anti-tautology: the full rename keeps the record and manifest labels
        # in sync, so the load succeeds — proving the drift test's refusal is
        # caused by the partial write, not by rename per se.
        from .....application.user_profile import ProfileRepository, profile_storage_session
        from ..bucket import read_manifest

        _create_profile(_RENAME_PROFILE_ID, label="Original Label", facts=_VALID_FACTS)
        root = load_settings().cadrumo_local_storage_root
        paths = bucket_paths(root, _RENAME_PROFILE_ID)

        with profile_storage_session(_RENAME_PROFILE_ID):
            ProfileRepository().rename(_RENAME_PROFILE_ID, new_label="Renamed Label")
            aggregate = ProfileRepository().load(_RENAME_PROFILE_ID)

        assert aggregate.label == "Renamed Label"
        assert read_manifest(paths).label == "Renamed Label"


class TestHardDeleteCrashWindow:
    """Soft tombstone is off the live surface; a partial directory is detected and reclaimable."""

    def test_tombstone_without_removal_is_off_live_surface_but_repair_visible(self, backend: Path) -> None:
        from .....application.user_profile import delete_profile_with_lifecycle_span
        from .....application.workflow import (
            read_profile_bucket,
            read_profile_bucket_by_id,
        )
        from .....domain.user_profile import UserProfileStatus

        _create_profile(_DELETE_PROFILE_ID, label="Delete target", facts=_VALID_FACTS)

        # Soft tombstone only (the first half of the hard delete); the bucket
        # directory is intentionally left intact — the "tombstone without
        # removal" crash window.
        delete_profile_with_lifecycle_span(_DELETE_PROFILE_ID)

        # Off every live surface (list / switch / name-uniqueness read the
        # manifest status), but still resolvable by id for repair / audit.
        assert read_profile_bucket("Delete target") is None
        by_id = read_profile_bucket_by_id(_DELETE_PROFILE_ID)
        assert by_id is not None
        assert by_id.status is UserProfileStatus.TOMBSTONED

    def test_partial_directory_is_detected_and_reclaimable_idempotently(self, backend: Path) -> None:
        from .....application.user_profile import (
            delete_profile_with_lifecycle_span,
            remove_profile_bucket_directory,
        )
        from .....application.workflow import list_profile_bucket_scan_issues
        from .....core.external_constants import UTF_8_ENCODING

        _create_profile(_DELETE_PROFILE_ID, label="Delete target", facts=_VALID_FACTS)
        delete_profile_with_lifecycle_span(_DELETE_PROFILE_ID)

        root = load_settings().cadrumo_local_storage_root
        paths = bucket_paths(root, _DELETE_PROFILE_ID)

        # Anti-tautology: before the partial-removal corruption, the scan finds
        # no issue for this bucket.
        assert not any(issue.bucket_id == _DELETE_PROFILE_ID for issue in list_profile_bucket_scan_issues(root=root))

        # Simulate a partial directory removal that damaged the manifest (the
        # Windows in-place rmtree fallback can leave a torn manifest).
        manifest_path(paths).write_text("this is not valid toml = = =\n", encoding=UTF_8_ENCODING)

        issues = list_profile_bucket_scan_issues(root=root)
        assert any(issue.bucket_id == _DELETE_PROFILE_ID for issue in issues), (
            "repair-integrity scan did not detect the partial/torn bucket directory"
        )

        # The removal is idempotent: it reclaims the partial directory, and a
        # re-run is a clean no-op.
        remove_profile_bucket_directory(_DELETE_PROFILE_ID)
        assert not paths.bucket_dir.exists()
        remove_profile_bucket_directory(_DELETE_PROFILE_ID)
        assert not paths.bucket_dir.exists()
