"""Backend service for workspace initialization."""

from __future__ import annotations

from ...adapters.persistence.storage.bucket._layout import bucket_paths, provision_bucket_directory
from ...core.config import load_settings
from ...domain.user_profile import UserProfileFact, new_profile_id
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile._orchestration import (
    _write_active_profile_pointer,
    register_active_profile,
)
from ..workflow._persistence import workflow_state_repository
from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult


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

    # The profile identity is a fresh immutable UUID. The operator-
    # chosen ``profile_name`` becomes the decoupled display label.
    profile_id = new_profile_id()

    # 1. Provision the per-bucket directory tree (db/, blobs/, audit/)
    #    so SQLite can open its database file, and write the active-
    #    profile pointer so ``Settings.aeat_database_url`` resolves
    #    to the per-bucket DB before the workflow-state repository
    #    eagerly opens its engine. The pointer carries the profile
    #    UUID. The bucket MANIFEST is intentionally NOT written here:
    #    ``register_active_profile`` owns the manifest write.
    #    ``provision_bucket_directory`` is fail-closed, so a re-run
    #    against an existing tree falls back to ``bucket_paths``.
    root = load_settings().aeat_local_storage_root
    try:
        provision_bucket_directory(root, profile_id)
    except FileExistsError:
        bucket_paths(root, profile_id)
    _write_active_profile_pointer(profile_id)

    # 2. Register the profile through the canonical atomic-create
    #    surface. ``register_active_profile`` writes the bucket
    #    manifest, the encrypted profile record, and rolls every
    #    write back on failure. A label already carried by a live
    #    profile is refused with ``ProfileAlreadyRegisteredError``;
    #    that refusal propagates to the caller unchanged.
    repository = workflow_state_repository()
    repository.update(
        lambda state: register_active_profile(
            state,
            profile_id=profile_id,
            display_name=command.profile_name,
            facts=tuple(facts),
        )
    )

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
        profile_id=profile_id,
        bucket_id=profile_id,
        auth_configured=auth_configured,
    )
