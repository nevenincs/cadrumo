"""Typed frontend refusals and complete one-revision profile view collections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import ValidationError

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.sign_in_refusals import SignInRefusal
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.digest import ContentDigest
from ...core.request_faults import RequestFault, request_faults_text
from ...domain.user_profile.values import ProfileSetupState

if TYPE_CHECKING:
    from ...application.user_profile.view_operation import (
        ProfileViewItem,
        ProfileViewOperationProjection,
        ProfileViewPageKind,
    )


class RuntimeFrontendRefusedError(CadrumoError):
    """A safe, typed application refusal from the installed runtime."""

    def __init__(
        self,
        code: str,
        *,
        sign_in: SignInRefusal | None = None,
        custody_transaction_id: UUID | None = None,
        request_faults: tuple[RequestFault, ...] = (),
        holder_operation_id: str | None = None,
    ) -> None:
        """Retain an allowlisted refusal code and the reasons the runtime returned with it.

        ``request_faults`` are the reasons an operation's request was refused
        as invalid, in the validators' own messages, when the runtime returned
        them. ``holder_operation_id`` names the unsettled operation that holds
        a busy subject, so the person can follow, resume or report it.
        """
        self.reason = code
        self.sign_in = sign_in
        self.request_faults = request_faults
        # Every error context copies public attributes; only a refusal that has a holder names one.
        self._holder_operation_id = holder_operation_id
        context: dict[str, object] = {"reason": code}
        if holder_operation_id is not None:
            context["holder_operation_id"] = holder_operation_id
        if request_faults:
            context["request_faults"] = request_faults_text(request_faults)
        if custody_transaction_id is not None:
            context["transaction_id"] = str(custody_transaction_id)
        if sign_in is not None:
            context["sign_in_reason"] = sign_in.reason
            if sign_in.binding is not None:
                context["sign_in_binding"] = sign_in.binding
            if sign_in.remaining_seconds is not None:
                context["seconds"] = sign_in.remaining_seconds
        super().__init__(code, context=context)

    @property
    def holder_operation_id(self) -> str | None:
        """The unsettled operation that holds a busy subject, when the runtime named one."""
        return self._holder_operation_id


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
