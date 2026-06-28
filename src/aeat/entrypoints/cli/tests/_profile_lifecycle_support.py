"""Shared helpers for the profile-lifecycle CLI verb tests.

Both ``test_profile_lifecycle_verbs`` (record-level show / create / edit /
switch / repair) and ``test_profile_lifecycle_navigation`` (per-bucket
rename / import / delete / navigation from a no-active-session state) drive
the same ``aeat config profile`` surface, so they share one ``seed`` primitive
and one torn-bucket stager. Keeping those helpers in one module avoids
duplicating the storage-provisioning subtleties (key material, active-pointer
clearing) across two test files. The storage fixtures themselves stay local to
each test module so they cannot leak into the wider CLI test package.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from ....adapters.persistence.storage.bucket._layout import provision_bucket_directory
from ....adapters.persistence.storage.bucket._manifest import (
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from ....adapters.persistence.storage.bucket._manifest_io import write_manifest
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import load_settings
from ....core.identity import nif_check_letter
from ....tests.cli_runner import invoke_cached_cli


def stage_bucket_manifest(bucket_id: str, *, label: str) -> None:
    """Stage a ``missing_profile_record`` torn-bucket state under a real key.

    A bucket directory and plaintext manifest with no encrypted
    profile-value row is exactly the ``missing_profile_record`` torn
    state these CLI verbs must detect; this helper materialises that
    state directly through the bucket-layout primitives, since
    ``ProfileRepository`` always writes the record alongside.

    Unlike the unsecured-backend version, this implementation uses
    ``profile_create_storage_span`` to provision real key material for
    the bucket so the CLI can open a ``profile_storage_session`` and
    reach the point where the missing record is detected. Without key
    material the session open fails before the torn state is observable.
    """

    # Provision the master key for the staged bucket so CLI commands can
    # open a session and reach the profile-record-missing detection point.
    with profile_create_storage_span(bucket_id):
        pass

    root = load_settings().aeat_local_storage_root
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=datetime.now(UTC),
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
    # Clear the active-profile pointer after provisioning so the staged
    # profile is not reported as the active one; the torn-state tests
    # specifically test non-active torn profiles.
    from ....application.user_profile._orchestration import logout_active_profile

    logout_active_profile()


def seed(name: str = "default", *, tax_id: str | None = None) -> None:
    # ``register_minimal_profile`` derives a profile-unique NIF by
    # default so two ``seed`` calls never collide on the
    # duplicate-tax-id refusal; a test that asserts a specific tax id
    # passes it explicitly.
    #
    # profile_create_storage_span provisions key material for the named
    # bucket and activates a real session so the profile lifecycle service
    # can resolve the file-backed secure-object repository.
    #
    # enforce_unique_tax_id=False avoids the cross-bucket scan: in
    # per-bucket-storage mode each profile's encrypted record lives in
    # its own SQLite file, so loading another bucket's record while a
    # different session is active would fail. Matches the CLI path.
    overrides = {"identity.tax_id": tax_id} if tax_id is not None else None
    with profile_create_storage_span(name):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=name,
                overrides=overrides,
                enforce_unique_tax_id=False,
            ),
        )


def distinct_nif(name: str) -> str:
    """Return a checksum-valid NIF derived deterministically from ``name``.

    ``profile create`` refuses two profiles that share a tax id, so a
    test creating several profiles needs a distinct, valid NIF per
    profile rather than one hard-coded literal.
    """

    number = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16) % 100_000_000
    return f"{number:08d}{nif_check_letter(number)}"


def create_profile_via_cli(name: str, *, tax_id: str | None = None) -> None:
    """Create a profile through the real cached root CLI command."""

    result = invoke_cached_cli(
        (
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--tax-id",
            tax_id or distinct_nif(name),
            "--name",
            name.capitalize(),
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        )
    )
    assert result.exit_code == 0, f"create {name!r} failed: {result.output}"
