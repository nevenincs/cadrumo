"""Typed frontend refusals and complete one-revision profile view collections."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.view_operation import (
    ProfileViewItem,
    ProfileViewOperationProjection,
    ProfileViewPageKind,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.digest import ContentDigest
from ...domain.user_profile.values import ProfileSetupState


class RuntimeFrontendRefusedError(CadrumoError):
    """A safe, typed application refusal from the installed runtime."""

    def __init__(self, code: str) -> None:
        """Retain an allowlisted refusal code without private diagnostic text."""
        self.reason = code
        super().__init__(code)


def frontend_failure_code(error: Exception) -> str:
    """Return the public code for a failed frontend exchange.

    Typed runtime and application refusals keep their own code, a reply that
    fails its contract is an invalid frame, and any other failure leaves the
    runtime unavailable without exposing its private diagnostic.
    """
    if isinstance(error, RuntimeFrontendRefusedError):
        return error.reason
    if isinstance(error, RuntimeRefusalError):
        return error.reason.value
    if isinstance(error, ValidationError):
        return RuntimeRefusalCode.INVALID_FRAME.value
    return RuntimeRefusalCode.UNAVAILABLE.value


@dataclass(frozen=True, slots=True)
class ProfileViewCollection:
    """Only complete page streams from one exact encrypted profile revision."""

    profile_id: UUID
    record_revision: int
    content_digest: ContentDigest
    setup_state: ProfileSetupState
    schema_version: int
    valid: bool
    page_kinds: tuple[ProfileViewPageKind, ...]
    pages: tuple[ProfileViewOperationProjection, ...]

    def items(self, kind: ProfileViewPageKind) -> tuple[ProfileViewItem, ...]:
        """Return the ordered items of one fully collected requested stream."""
        if kind not in self.page_kinds:
            raise ValueError("profile view stream was not requested")
        return tuple(item for page in self.pages if page.page_kind is kind for item in page.items)
