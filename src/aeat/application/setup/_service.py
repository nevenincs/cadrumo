"""Backend service for workspace initialization."""

from __future__ import annotations

from ...domain.user_profile import UserProfileFact, new_profile_id
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile._orchestration import (
    _write_active_profile_pointer,
    capture_active_profile_pointer,
    register_active_profile,
    restore_active_profile_pointer,
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

    # Cold-start: the active-profile pointer must aim at the new UUID
    # before ``workflow_state_repository()`` opens its per-bucket
    # engine. ``ProfileRepository.create`` (inside ``register_active_
    # profile``) owns the cross-store unit of work — bucket directory,
    # manifest, encrypted record, AND the pointer — and rolls every
    # store back on a failure inside the create. The genuine prior
    # pointer is captured here and restored if the surrounding span
    # fails BEFORE or AROUND ``create`` (engine open, master-key
    # activation), the window the repository's own rollback cannot see.
    prior_pointer = capture_active_profile_pointer()
    _write_active_profile_pointer(profile_id)
    try:
        workflow_state_repository().update(
            lambda state: register_active_profile(
                state,
                profile_id=profile_id,
                display_name=command.profile_name,
                facts=tuple(facts),
            )
        )
    except Exception:
        restore_active_profile_pointer(prior_pointer)
        raise

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
