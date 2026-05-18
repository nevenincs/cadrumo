"""Backend service for workspace initialization."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from ...adapters.persistence.storage.bucket._layout import bucket_paths, provision_bucket_directory
from ...adapters.persistence.storage.bucket._manifest import BucketManifest, KdfParams
from ...adapters.persistence.storage.bucket._manifest_io import manifest_path, write_manifest
from ...core.config import load_settings
from ...domain.user_profile import UserProfileFact
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile._orchestration import register_active_profile
from ..workflow._persistence import workflow_state_repository
from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult

# OWASP 2024 baseline Argon2id parameters; mirrors the master-key
# helper KdfParams.default() factory at
# adapters/persistence/storage/master_key/_kdf_params.py:81 so the
# manifest the workspace writes at init records the same parameter
# set the future recovery enrollment will derive its KEK under.
_ARGON2_V13 = 0x13
_BASELINE_MEMORY_KIB = 19_456  # 19 MiB
_BASELINE_TIME_COST = 2
_BASELINE_PARALLELISM = 1
_BASELINE_SALT_BYTES = 16
_BASELINE_OUTPUT_BYTES = 32


def _baseline_kdf_params() -> KdfParams:
    """Return a fresh KdfParams record with a per-bucket Argon2id salt.

    The bucket records its KDF parameters at provisioning so a future
    recovery-enrollment flow consumes the same salt + cost vector.
    Argon2 salts are public per the algorithm contract.
    """

    return KdfParams(
        algorithm="argon2id",
        version=_ARGON2_V13,
        memory_cost=_BASELINE_MEMORY_KIB,
        time_cost=_BASELINE_TIME_COST,
        parallelism=_BASELINE_PARALLELISM,
        salt=secrets.token_bytes(_BASELINE_SALT_BYTES),
        output_length=_BASELINE_OUTPUT_BYTES,
    )


def _provision_bucket_directory_idempotent(*, bucket_id: str) -> None:
    """Provision the per-bucket directory tree + manifest, idempotently.

    ``provision_bucket_directory`` is fail-closed (refuses if the
    bucket dir already exists); the workspace initializer must
    tolerate re-runs against a pre-existing tree, so this helper
    swallows the FileExistsError on subsequent provisions while
    leaving the recursive directory contract intact.
    """

    settings = load_settings()
    root = settings.aeat_local_storage_root
    try:
        paths = provision_bucket_directory(root, bucket_id)
    except FileExistsError:
        paths = bucket_paths(root, bucket_id)

    target = manifest_path(paths)
    if target.is_file():
        # A manifest already exists for this bucket; the workspace
        # has been initialized before. Re-writing would clobber the
        # bucket's KDF salt, breaking any recovery enrollment that
        # was performed against the old salt.
        return

    manifest = BucketManifest(
        bucket_id=bucket_id,
        label=bucket_id,
        created_at=datetime.now(UTC),
        last_unlocked_at=None,
        kdf_params=_baseline_kdf_params(),
        recovery_enrolled=False,
        schema_version=1,
    )
    write_manifest(paths, manifest)


def initialize_workspace(command: InitializeWorkspaceCommand) -> InitializeWorkspaceResult:
    """Initialize a new active workspace profile and bucket."""

    facts: list[UserProfileFact] = [
        UserProfileFact(path="identity.tax_id", value=command.tax_id),
        UserProfileFact(path="activities.description", value=command.activity),
        UserProfileFact(path="iva.regime", value=command.iva_regime),
    ]
    if command.tax_residence_ccaa is not None:
        facts.append(UserProfileFact(path="tax_residence.ccaa", value=command.tax_residence_ccaa))
    if command.output_language is not None:
        facts.append(UserProfileFact(path="preferences.output_language", value=command.output_language))

    repository = workflow_state_repository()

    # 1. Provision the per-bucket on-disk directory tree + manifest
    #    (idempotent on re-runs; the salt is captured once at first
    #    provision and never regenerated).
    _provision_bucket_directory_idempotent(bucket_id=command.profile_name)

    # 2. Create profile and bucket atomically
    repository.update(
        lambda state: register_active_profile(
            state,
            profile_id=command.profile_name,
            display_name=command.profile_name,
            facts=tuple(facts),
        )
    )

    # 3. Configure auth
    auth_configured = False
    if command.auth_provider and command.auth_provider.lower() != "none":
        try:
            configure_operator_auth(
                provider=command.auth_provider,
                certificate_path=command.certificate_path,
            )
            auth_configured = True
        except AuthProviderReservedError:
            auth_configured = False

    # 4. Handle env configs (drafts_dir, submissions_dir, manuals_root)
    # Env configuration events are emitted only if env-file persistence survives.
    # We rely on the backend. Legacy setups are handled by setup_state migration.

    return InitializeWorkspaceResult(
        profile_id=command.profile_name,
        bucket_id=command.profile_name,
        auth_configured=auth_configured,
        migrated_legacy_state=False,
    )
