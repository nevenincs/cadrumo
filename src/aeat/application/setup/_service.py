"""Backend service for workspace initialization."""

from __future__ import annotations

import contextlib

from ...adapters.persistence.storage.bucket._layout import provision_bucket_directory
from ...core.config import load_settings
from ...domain.user_profile import UserProfileFact, new_profile_id
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile._orchestration import (
    _write_active_profile_pointer,
    capture_active_profile_pointer,
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

    # 1. Cold-start provisioning: the per-bucket directory tree
    #    (db/, blobs/, audit/) must exist so the per-bucket SQLite
    #    engine can open, and the active-profile pointer must aim at
    #    the new UUID so ``Settings.aeat_database_url`` resolves to the
    #    per-bucket DB before the workflow-state repository eagerly
    #    opens its engine. ``ProfileRepository.create`` tolerates this
    #    pre-staged bare directory and rewrites the pointer idempotently
    #    — the cross-store write itself (manifest + record + rollback)
    #    lives solely in ``ProfileRepository``.
    root = load_settings().aeat_local_storage_root
    prior_pointer_text = capture_active_profile_pointer()
    with contextlib.suppress(FileExistsError):
        provision_bucket_directory(root, profile_id)
    _write_active_profile_pointer(profile_id)

    # 2. Register the profile. ``register_active_profile`` is a thin
    #    coordinator that delegates the cross-store create to
    #    ``ProfileRepository`` and threads the workflow-level event
    #    stream. The genuine pre-create pointer is handed down as the
    #    rollback anchor so a failed create restores it exactly. A
    #    label already carried by a live profile is refused with
    #    ``ProfileAlreadyRegisteredError``; that refusal propagates to
    #    the caller unchanged.
    repository = workflow_state_repository()
    repository.update(
        lambda state: register_active_profile(
            state,
            profile_id=profile_id,
            display_name=command.profile_name,
            facts=tuple(facts),
            prior_pointer_text=prior_pointer_text,
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
