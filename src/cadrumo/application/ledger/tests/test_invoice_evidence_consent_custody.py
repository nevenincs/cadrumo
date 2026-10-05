"""Consent saves have short write custody with one cancellation owner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import pytest

from ....core.errors.hierarchy import InternalInvariantError
from ....core.operations import OperationEffect
from ...operations.owner import OperationExecutorContext
from ..invoice_evidence_consent_custody import InvoiceEvidenceConsentCustody

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Recorder:
    def __init__(self) -> None:
        self.timeline: list[tuple[str, object]] = []

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        owner = asyncio.current_task()
        self.timeline.append(("enter", owner))
        try:
            yield
        finally:
            self.timeline.append(("exit", asyncio.current_task()))

    async def effect(self, effect: OperationEffect) -> None:
        self.timeline.append(("effect", effect))


def test_each_save_has_one_owner_and_inference_runs_outside_commit() -> None:
    async def exercise() -> None:
        recorder = _Recorder()
        context = cast(OperationExecutorContext, type("Context", (), {"cancellation": recorder, "events": recorder})())
        custody = InvoiceEvidenceConsentCustody(context)

        await asyncio.wait_for(asyncio.to_thread(custody.before_save), timeout=5)
        assert [kind for kind, _ in recorder.timeline] == ["enter", "effect"]
        assert recorder.timeline[-1] == ("effect", OperationEffect.UNKNOWN)

        # This point is the synchronous encrypted save in the worker thread.
        recorder.timeline.append(("save", True))
        await asyncio.wait_for(asyncio.to_thread(custody.after_save, True), timeout=5)
        assert [kind for kind, _ in recorder.timeline] == ["enter", "effect", "save", "effect", "exit"]
        assert recorder.timeline[-2] == ("effect", OperationEffect.UPDATED)
        assert recorder.timeline[0][1] is recorder.timeline[-1][1]
        assert custody.current_effect is OperationEffect.UPDATED

        # A second model dispatch uses a separate short section. A failed save
        # leaves UNKNOWN, while the section still exits before inference resumes.
        await asyncio.wait_for(asyncio.to_thread(custody.before_save), timeout=5)
        await asyncio.wait_for(asyncio.to_thread(custody.after_save, False), timeout=5)
        assert recorder.timeline[-2] == ("effect", OperationEffect.UNKNOWN)
        assert recorder.timeline[-1][0] == "exit"
        assert recorder.timeline.count(("effect", OperationEffect.UPDATED)) == 1
        assert custody.current_effect is OperationEffect.UNKNOWN

    asyncio.run(exercise())


def test_custody_hook_refuses_event_loop_thread_to_avoid_deadlock() -> None:
    async def exercise() -> None:
        recorder = _Recorder()
        context = cast(OperationExecutorContext, type("Context", (), {"cancellation": recorder, "events": recorder})())
        custody = InvoiceEvidenceConsentCustody(context)
        with pytest.raises(InternalInvariantError, match="worker thread"):
            custody.before_save()
        assert recorder.timeline == []

    asyncio.run(exercise())
