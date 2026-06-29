"""Backend service for workspace initialization.

:func:`initialize_workspace` transforms an :class:`InitializeWorkspaceCommand`
into persisted :class:`UserProfileFact` records, creates a UUID
:class:`ProfileId`, provisions the matching storage :class:`BucketId`, and
returns an :class:`InitializeWorkspaceResult` for the newly created
profile/bucket pair.
"""

from __future__ import annotations

from ...core.logging import get_logger
from ...domain.user_profile import UserProfileFact, new_profile_id
from ..auth import AuthProviderReservedError, configure_operator_auth
from ..user_profile._orchestration import (
    profile_create_storage_span,
    register_active_profile,
)
from ..workflow._persistence import workflow_state_repository
from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult

_log = get_logger(__name__)


def initialize_workspace(command: InitializeWorkspaceCommand) -> InitializeWorkspaceResult:
    """Initialize a new active workspace profile and bucket.

    The service records :class:`UserProfileFact` values, registers the active
    profile inside the create-storage span, provisions the corresponding
    storage bucket, and returns an :class:`InitializeWorkspaceResult`. Reserved
    authentication providers are logged and reported as
    ``auth_configured=False`` without rolling back the profile/bucket creation.
    """
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

    with profile_create_storage_span(profile_id) as routing_profile_id:
        workflow_state_repository().update(
            lambda state: register_active_profile(
                state,
                profile_id=profile_id,
                display_name=command.profile_name,
                facts=tuple(facts),
                routing_profile_id=routing_profile_id,
            ),
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
            _log.debug(
                "initialize_workspace: reserved auth provider was not configured",
                extra={"auth_provider": command.auth_provider},
                exc_info=True,
            )
            auth_configured = False

    # 4. Handle env configs (drafts_dir, submissions_dir, manuals_root)
    return InitializeWorkspaceResult(
        profile_id=profile_id,
        bucket_id=profile_id,
        auth_configured=auth_configured,
    )
