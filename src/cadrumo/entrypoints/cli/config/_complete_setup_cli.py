"""CLI projection for the registered exact-profile setup declaration."""

from __future__ import annotations

from uuid import UUID

import typer

from ....application.user_profile.operations import (
    ProfileCompleteSetupOperationProjection,
    ProfileCompleteSetupOperationRequest,
)
from ....application.user_profile.view_operation import ProfileViewMissingItem, ProfileViewPageKind
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.i18n.render import tr
from ....domain.user_profile.values import ProfileSetupState
from ..common import bad, emit_envelope, no_active_profile_refusal
from ..runtime_profile_binding import require_profile_client
from ._complete_setup_payloads import ProfileCompleteSetupResult
from ._runtime_profile_mutation import execute_profile_mutation, mutation_deadline, read_mutation_baseline


def profile_complete_setup(ctx: typer.Context) -> None:
    """Promote the exact active profile after native authority rechecks."""
    profile_id = resolve_active_bucket_id()
    if profile_id is None:
        raise no_active_profile_refusal()

    parsed_profile_id = UUID(profile_id)
    client = require_profile_client(ctx, expected_profile_id=parsed_profile_id)
    deadline = mutation_deadline()
    baseline = read_mutation_baseline(client, deadline=deadline, page_kind=ProfileViewPageKind.OVERVIEW)
    missing = tuple(
        item.path for item in baseline.items(ProfileViewPageKind.OVERVIEW) if isinstance(item, ProfileViewMissingItem)
    )
    if baseline.setup_state is ProfileSetupState.INCOMPLETE and missing:
        raise bad(tr("cli.config.profile.complete_setup.incomplete", paths=", ".join(missing)))

    completed, current = execute_profile_mutation(
        client,
        ProfileCompleteSetupOperationRequest(
            profile_id=parsed_profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
        ),
        deadline=deadline,
        expected_setup_state=ProfileSetupState.COMPLETE,
    )
    promoted = completed.projection
    if not isinstance(promoted, ProfileCompleteSetupOperationProjection):
        raise TypeError("registered setup promotion returned another projection")
    result = ProfileCompleteSetupResult.model_validate(
        {
            "profile_id": profile_id,
            "setup_state": current.setup_state.value,
            "record_revision": promoted.record_revision,
            "already_complete": promoted.already_complete,
        },
    )
    emit_envelope(
        ctx,
        command="config.profile.complete_setup",
        result=result,
        lines=[
            tr(
                "cli.config.profile.complete_setup.already_complete"
                if promoted.already_complete
                else "cli.config.profile.complete_setup.completed"
            )
        ],
    )


__all__ = ["profile_complete_setup"]
