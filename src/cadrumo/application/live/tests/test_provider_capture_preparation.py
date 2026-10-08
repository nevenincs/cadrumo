"""Provider refusal must precede construction and ownership of capture resources."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

import pytest

from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.capabilities import OperationOwnedResource
from ...operations.owner import OperationExecutorContext
from ...operations.tests.test_executor import EventEmitter
from ..filed_history_operation import FiledHistoryComposition
from ..live_operation_execution import prepare_provider_capture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Events(EventEmitter):
    def __init__(self, trace: list[str]) -> None:
        self.trace = trace

    @override
    async def phase(self, phase_code: str) -> None:
        self.trace.append(phase_code)

    @override
    async def effect(self, effect: OperationEffect) -> None:
        self.trace.append(effect.value)


class _Resources:
    @contextmanager
    def activate(self) -> Iterator[None]:
        yield

    async def close(self) -> None: ...


class _Cleanup:
    def __init__(self, trace: list[str], resource: _Resources) -> None:
        self.trace = trace
        self.resource = resource

    def own(self, resource: object, *, family: OperationOwnedResource) -> None:
        assert resource is self.resource
        assert family is OperationOwnedResource.PROCESS
        self.trace.append("owned")


@pytest.mark.parametrize("may_write", [True, False])
@pytest.mark.parametrize("refuse", [True, False])
@pytest.mark.asyncio
async def test_preflight_precedes_resource_ownership_and_preview_retains_session_accounting(
    tmp_path: Path, may_write: bool, refuse: bool
) -> None:
    trace: list[str] = []
    profile_id = UUID("11111111-1111-4111-8111-111111111111")
    resources = _Resources()
    # CAST-RATIONALE-PROVIDER-PREPARATION: the helper forwards authority and
    # composition by identity; no registry or capture-port method is invoked.
    authority = cast(PinnedAuthorityOperation, object())
    composition = cast(FiledHistoryComposition, object())
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(events=_Events(trace), cleanup=_Cleanup(trace, resources), authority_operation=authority),
    )

    def preflight(target: UUID, operation: PinnedAuthorityOperation) -> None:
        assert target == profile_id and operation is authority
        trace.append("preflight")
        if refuse:
            raise OSError("provider refused")

    def compose(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
        assert output_root == tmp_path and operation is authority
        trace.append("compose")
        return composition

    def browser() -> _Resources:
        trace.append("browser")
        return resources

    invocation = prepare_provider_capture(
        context,
        profile_id,
        tmp_path,
        compose,
        browser,
        preflight,
        preflight_phase="checking",
        acquire_phase="acquiring",
        may_write=may_write,
    )
    if refuse:
        with pytest.raises(OSError, match="provider refused"):
            await invocation
        assert trace == ["checking", "preflight"]
        return
    prepared, owned, receipt = await invocation
    assert prepared is composition and owned is resources
    assert trace == ["checking", "preflight", "compose", "browser", "owned", "acquiring"] + (
        [OperationEffect.UNKNOWN.value] if may_write else []
    )
    await receipt(OperationEffect.UPDATED)
    assert receipt.combine(OperationEffect.NONE) is OperationEffect.UPDATED
