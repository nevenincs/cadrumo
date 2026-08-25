"""Import-light helpers shared by independently loaded profile commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer


def profile_state():
    from cadrumo.application.workflow.persistence import workflow_state_repository

    return workflow_state_repository()


def resolve_profile_by_label(name: str) -> ProfileBucketPointer:
    from cadrumo.application.workflow.errors import ProfileLabelAmbiguousError
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
    from .._errors import CliRefusedBoundaryError

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
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from ....core.bucket_pointer import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    return None if active is None else read_profile_bucket_by_id(active)
