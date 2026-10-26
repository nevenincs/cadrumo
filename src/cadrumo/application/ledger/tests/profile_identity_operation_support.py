"""Focused executor identity-boundary probes for retained-profile reads."""

from __future__ import annotations

from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID

from pydantic import BaseModel

from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext


class RetainedProfileFactoryReachedError(RuntimeError):
    """The executor passed identity checks and reached its retained port factory."""


def unexpected_active_profile_lookup() -> NoReturn:
    raise AssertionError("retained-port read must not use the active profile pointer")


class PhaseProbe:
    def __init__(self) -> None:
        self.codes: list[str] = []

    async def phase(self, code: str) -> None:
        self.codes.append(code)


class PortFactoryProbe:
    def __init__(self, *, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args: object, **kwargs: object) -> NoReturn:
        del args
        self.calls.append(kwargs)
        bucket_id = kwargs.get("bucket_id")
        if bucket_id is None and kwargs.get("profile_id") is not None:
            bucket_id = str(kwargs["profile_id"])
        if bucket_id != str(self.profile_id):
            raise AssertionError("read executor did not request ports for the exact profile")
        raise RetainedProfileFactoryReachedError


def execution_context(
    request: OperationRequest[BaseModel],
    *,
    definition_id: str | None = None,
    subject_ref: str | None = None,
) -> tuple[OperationExecutorContext, PhaseProbe]:
    events = PhaseProbe()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=request.definition_id if definition_id is None else definition_id,
            subject_ref=request.subject_ref if subject_ref is None else subject_ref,
        ),
        events=events,
        authority_operation=object(),
    )
    return cast(OperationExecutorContext, context), events
