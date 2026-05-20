"""Backend service for workspace initialization."""

from __future__ import annotations

from ...adapters.persistence.storage.bucket._layout import bucket_paths, provision_bucket_directory
from ...core.config import load_settings
from ...core.i18n import tr
from ...domain.user_profile import UserProfileFact
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile import UserProfileLifecycleRepository
from ..user_profile._orchestration import (
    ProfileAlreadyRegisteredError,
    _write_active_profile_pointer,
    register_active_profile,
)
from ..workflow._persistence import workflow_state_repository
from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult
from ._errors import WorkspaceBucketTornError


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

    # 1. Provision the per-bucket directory tree (db/, blobs/, audit/)
    #    so SQLite can open its database file, and write the active-
    #    profile pointer so ``Settings.aeat_database_url`` resolves
    #    to the per-bucket DB before the workflow-state repository
    #    eagerly opens its engine. The bucket MANIFEST is intentionally
    #    NOT written here: ``register_active_profile`` owns the manifest
    #    write, and its duplicate-name guard keys on the manifest's
    #    presence. ``provision_bucket_directory`` is fail-closed, so a
    #    re-run against an existing tree falls back to ``bucket_paths``.
    root = load_settings().aeat_local_storage_root
    try:
        provision_bucket_directory(root, command.profile_name)
    except FileExistsError:
        bucket_paths(root, command.profile_name)
    _write_active_profile_pointer(command.profile_name)

    # 2. Register the profile through the canonical atomic-create
    #    surface. ``register_active_profile`` writes the bucket
    #    manifest, the encrypted profile record, and rolls every
    #    write back on failure. A profile whose manifest already
    #    exists is refused with ``ProfileAlreadyRegisteredError``.
    #
    #    That refusal carries two distinct states. A genuinely
    #    initialized workspace has both the manifest AND the encrypted
    #    profile record, so a re-run is a benign no-op. A bucket that
    #    crashed between disaster-ADR Ruling-3 steps 2 and 4 has the
    #    manifest but NOT the record — a torn bucket. Distinguish the
    #    two with a no-decryption DB-existence check: the profile
    #    value object key is plaintext, so ``exists`` is a pure
    #    SELECT-by-key that needs no master key. A present record means
    #    idempotent re-run (return normally); an absent record means
    #    the bucket is torn and the operator must route through an
    #    explicit repair verb rather than silently overlay new data.
    repository = workflow_state_repository()
    try:
        repository.update(
            lambda state: register_active_profile(
                state,
                profile_id=command.profile_name,
                display_name=command.profile_name,
                facts=tuple(facts),
            )
        )
    except ProfileAlreadyRegisteredError:
        lifecycle = UserProfileLifecycleRepository(bucket_id=command.profile_name)
        if not lifecycle.exists(command.profile_name):
            raise WorkspaceBucketTornError(
                tr(
                    "application.setup.errors.workspace_bucket_torn",
                    default=(
                        "Profile bucket '%{profile}' has a manifest but no profile "
                        "record; initialization did not complete. Run `aeat config "
                        "repair profile --clear-active --yes`, then create the "
                        "profile again."
                    ),
                    profile=command.profile_name,
                ),
            ) from None

    # 2. Configure auth
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
    return InitializeWorkspaceResult(
        profile_id=command.profile_name,
        bucket_id=command.profile_name,
        auth_configured=auth_configured,
    )
