"""Backend service for workspace initialization."""

from __future__ import annotations

from ...domain.user_profile import UserProfileFact
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile._orchestration import register_active_profile
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

    repository = workflow_state_repository()

    # 1. Create profile and bucket atomically
    repository.update(
        lambda state: register_active_profile(
            state,
            profile_id=command.profile_name,
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

    # 3. Handle env configs (drafts_dir, submissions_dir, manuals_root)
    # Env configuration events are emitted only if env-file persistence survives.
    # We rely on the backend. Legacy setups are handled by setup_state migration.

    return InitializeWorkspaceResult(
        profile_id=command.profile_name,
        bucket_id=command.profile_name,
        auth_configured=auth_configured,
        migrated_legacy_state=False,
    )
