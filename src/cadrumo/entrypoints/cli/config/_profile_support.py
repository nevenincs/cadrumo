"""Import-light helpers shared by independently loaded profile commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....application.workflow.profile_bucket_models import ProfileBucketPointer


def profile_state():
    from ....application.workflow.persistence import workflow_state_repository

    return workflow_state_repository()


def resolve_profile_by_label(name: str) -> ProfileBucketPointer:
    from ....application.workflow.errors import ProfileLabelAmbiguousError
    from ....application.workflow.profile_bucket_scan import read_profile_bucket
    from ..errors import CliRefusedBoundaryError

    try:
        pointer = read_profile_bucket(name)
    except ProfileLabelAmbiguousError as error:
        raise CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from error
    except ValueError as error:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        ) from error
    if pointer is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        )
    return pointer


def resolve_active_profile_pointer() -> ProfileBucketPointer | None:
    from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from ....core.bucket_pointer import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    return None if active is None else read_profile_bucket_by_id(active)


def require_active_profile_pointer() -> ProfileBucketPointer:
    """Return the active profile pointer, refusing when none is selected.

    The refusing form beside the resolving one, because two command modules each
    wrapped the optional result in the same refusal and so each decided
    independently which message a missing profile produces.
    """
    from ..errors import CliRefusedBoundaryError

    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        )
    return pointer
