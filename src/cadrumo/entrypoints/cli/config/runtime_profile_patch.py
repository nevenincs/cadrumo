"""Atomic wizard patch submission through the invocation's authenticated runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

import typer

from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.operations import (
    ProfilePatchOperationProjection,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
)
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....application.wizard.patch_edit import WizardPatchPersister, validate_profile_patch
from ..runtime_profile_binding import require_profile_client
from ._runtime_profile_mutation import execute_profile_mutation, mutation_deadline, read_mutation_baseline

if TYPE_CHECKING:
    from ....application.wizard.models import WizardFlow
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation


def runtime_patch_persister(
    ctx: typer.Context, *, flow: WizardFlow, operation: PinnedAuthorityOperation
) -> WizardPatchPersister:
    """Bind the wizard's persistence seam to one exact CLI connection."""

    def persist(
        *, profile_id: str, supplied: Mapping[str, str], colegio_concertado: bool | None
    ) -> tuple[dict[str, str], bool]:
        identity = UUID(profile_id)
        client = require_profile_client(ctx, expected_profile_id=identity)
        deadline = mutation_deadline()
        baseline = read_mutation_baseline(client, deadline=deadline)
        baseline_items = baseline.items(ProfileViewPageKind.FACTS)
        baseline_values = {item.path: item.value for item in baseline_items if isinstance(item, ProfileViewFactItem)}
        if len(baseline_values) != len(baseline_items):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        validate_profile_patch(
            flow=flow,
            current_values=baseline_values,
            setup_state=baseline.setup_state,
            supplied=supplied,
            colegio_concertado=colegio_concertado,
            operation=operation,
        )
        completed, current = execute_profile_mutation(
            client,
            ProfilePatchOperationRequest(
                profile_id=identity,
                expected_revision=baseline.record_revision,
                expected_content_digest=baseline.content_digest,
                values=tuple(ProfilePatchValue(question_id=key, value=value) for key, value in supplied.items()),
                colegio_concertado=colegio_concertado,
            ),
            deadline=deadline,
        )
        projection = completed.projection
        if not isinstance(projection, ProfilePatchOperationProjection):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        items = current.items(ProfileViewPageKind.FACTS)
        if not all(isinstance(item, ProfileViewFactItem) for item in items):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
        if len(facts) != len(items):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return facts, projection.changed

    return persist


__all__ = ["runtime_patch_persister"]
