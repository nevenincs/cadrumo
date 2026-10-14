"""The profile repair work every frontend runs: resolve, inspect, and judge the pointer's target.

``config repair profile`` either inspects one named profile's record or
repairs a degraded active-profile pointer. The pointer repair itself is
:func:`~cadrumo.application.workflow.profile_health.repair_active_profile_pointer`.
This module holds the rest of the work that is neither parsing nor rendering,
so the command line and the runtime's repair act reach the same verdicts.
The inspected :class:`UserProfileRecord` supplies the profile identity and state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, Protocol, Self

from pydantic import BaseModel, model_validator

from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ...core.identity.bucket import BucketId
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.values import ProfileSetupState
from ..operator_actions.models import PreconditionVerdict
from .errors import ProfileLabelAmbiguousError
from .profile_bucket_models import ProfileBucketPointer
from .profile_bucket_scan import read_profile_bucket
from .profile_health import ProfileHealthStatus, unavailable_profile_record_verdict

if TYPE_CHECKING:
    from ...domain.user_profile.values import UserProfileRecord

_LOGGER = get_logger(__name__)

_BOUNDARY_REFUSAL_CODE: Final = "REFUSED_CLI_BOUNDARY"
"""The registered code the command line refuses a repair request under."""


@dataclass(frozen=True, slots=True)
class ProfileRepairRefusal:
    """Why one profile repair request is refused before anything is read or changed.

    The command line raises it at its own boundary. A frontend that reaches
    the repair through the runtime is refused with :meth:`recorded`, which
    carries the same registered code, message and context.
    """

    message_key: str
    context: Mapping[str, str] | None = None

    def recorded(self) -> RecordedRegisteredError:
        """Return the refusal under the registered code the command line refuses with."""
        return RecordedRegisteredError(
            _BOUNDARY_REFUSAL_CODE, context=self.context, translated_message=self.message_key
        )


class ProfileRecordReader(Protocol):
    """Read one profile's record through whatever session this process already holds."""

    def __call__(self, *, profile_id: str, bucket_id: str) -> UserProfileRecord:
        """Return the record, or raise ``ProfileNotFoundError`` when no session here serves it."""
        ...


class ProfileRecordInspection(BaseModel):
    """Whether one named profile's record could be read, without any of its contents.

    ``status`` is absent exactly when the record was read, and ``setup_state``
    is the record's own and present only then. A record that was not read
    carries the verdict that says what, if anything, recovers it.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: BucketId
    display_name: str
    registered_bucket: bool
    profile_record_present: bool
    setup_state: ProfileSetupState | None = None
    status: (
        Literal[ProfileHealthStatus.MISSING_PROFILE_RECORD, ProfileHealthStatus.PROFILE_RECORD_UNREADABLE] | None
    ) = None
    error: str | None = None
    precondition_verdict: PreconditionVerdict | None = None

    @model_validator(mode="after")
    def _closed_shape(self) -> Self:
        if self.profile_record_present != (self.status is None):
            raise ValueError("a profile record inspection names a fault exactly when the record was not read")
        if (self.setup_state is not None) != self.profile_record_present:
            raise ValueError("a setup state belongs to exactly the record that was read")
        if (self.precondition_verdict is None) != self.profile_record_present:
            raise ValueError("a record that was not read carries its recovery verdict")
        return self


def resolve_repair_profile(label: str) -> ProfileBucketPointer:
    """Resolve the committed profile ``label`` names, refusing as the command line refuses.

    Raises:
        RecordedRegisteredError: More than one live profile carries the label.
        ProfileNotFoundError: No live profile carries it.
    """
    try:
        pointer = read_profile_bucket(label)
    except ProfileLabelAmbiguousError as error:
        raise ProfileRepairRefusal("errors.refused.refused_profile_label_ambiguous").recorded() from error
    except ValueError:
        pointer = None
    if pointer is None:
        raise ProfileNotFoundError(translated_message="cli.config.profile.unknown_profile", context={"name": label})
    return pointer


def pointer_repair_refusal(
    named: tuple[str, ProfileBucketPointer] | None, *, clear_active: bool, confirmed: bool
) -> ProfileRepairRefusal | None:
    """Return why a pointer repair request is refused, or ``None`` when it may run.

    ``named`` is the name the request gave and the profile it resolved to. A
    pointer repair acts on the active selection only, so a request that names
    another profile is refused instead of having a different profile's
    selection assessed or cleared. Clearing the selection is refused until the
    request confirms it.
    """
    if named is not None and named[1].bucket_id != resolve_active_bucket_id():
        return ProfileRepairRefusal(
            message_key="cli.config.repair.profile_clear_active_mismatch", context={"profile": named[0]}
        )
    if clear_active and not confirmed:
        return ProfileRepairRefusal(message_key="cli.config.repair.profile_requires_yes")
    return None


def inspect_profile_record(
    pointer: ProfileBucketPointer, *, read_profile_record: ProfileRecordReader
) -> ProfileRecordInspection:
    """Report whether the record of the profile ``pointer`` names can be read here.

    A reader fault is a finding and never propagates: an absent record and an
    unreadable one are told apart, and an unreadable one names only the type
    of the fault that stopped the read.
    """
    profile_id = pointer.bucket_id
    try:
        record = read_profile_record(profile_id=profile_id, bucket_id=profile_id)
    except ProfileNotFoundError:
        return _unread(pointer, status=ProfileHealthStatus.MISSING_PROFILE_RECORD, error=None)
    except Exception as exc:
        if not isinstance(exc, CadrumoError):
            _LOGGER.debug("config repair profile wrapped unexpected profile-record exception", exc_info=True)
        return _unread(pointer, status=ProfileHealthStatus.PROFILE_RECORD_UNREADABLE, error=type(exc).__name__)
    return ProfileRecordInspection(
        profile_id=profile_id,
        display_name=pointer.label,
        registered_bucket=True,
        profile_record_present=True,
        setup_state=record.setup_state,
    )


def _unread(
    pointer: ProfileBucketPointer,
    *,
    status: Literal[ProfileHealthStatus.MISSING_PROFILE_RECORD, ProfileHealthStatus.PROFILE_RECORD_UNREADABLE],
    error: str | None,
) -> ProfileRecordInspection:
    return ProfileRecordInspection(
        profile_id=pointer.bucket_id,
        display_name=pointer.label,
        registered_bucket=True,
        profile_record_present=False,
        status=status,
        error=error,
        precondition_verdict=unavailable_profile_record_verdict(
            status=status, source="none", repairable_by_clearing_pointer=False
        ),
    )


__all__ = [
    "ProfileRecordInspection",
    "ProfileRecordReader",
    "inspect_profile_record",
    "pointer_repair_refusal",
    "resolve_repair_profile",
]
