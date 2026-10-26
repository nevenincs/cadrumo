"""The profile adapter composition stays resolvable for a whole frontend session.

A frontend enters the composition once and then serves work from later event
loops and worker threads. The ports it binds are context variables, so the
proof is that each port resolves to the composed binding, not to whatever an
outer scope bound, from every execution shape a session uses.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextvars import copy_context

import pytest

from ...application.user_profile.custody_ports import profile_custody_port
from ...application.user_profile.login_session_port import profile_login_session_port
from ...application.workflow.persistence import workflow_persistence_port
from ..adapter_composition import profile_adapter_composition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

type _Resolved = tuple[object, object, object]


def _resolve_ports() -> _Resolved:
    return profile_custody_port(), profile_login_session_port(), workflow_persistence_port()


def _resolve_in_thread(target: Callable[[], _Resolved]) -> _Resolved:
    results: list[_Resolved] = []
    worker = threading.Thread(target=lambda: results.append(target()))
    worker.start()
    worker.join()
    assert results, "the worker thread did not resolve the ports"
    return results[0]


def test_the_composed_ports_resolve_from_later_loops_and_context_carrying_threads() -> None:
    outer = _resolve_ports()
    with profile_adapter_composition():
        composed = _resolve_ports()
        assert all(inner is not before for inner, before in zip(composed, outer, strict=True))

        async def resolve_in_loop() -> _Resolved:
            return _resolve_ports()

        assert asyncio.run(resolve_in_loop()) == composed
        assert asyncio.run(resolve_in_loop()) == composed

        async def resolve_in_to_thread() -> _Resolved:
            return await asyncio.to_thread(_resolve_ports)

        assert asyncio.run(resolve_in_to_thread()) == composed

        session_context = copy_context()
        assert _resolve_in_thread(lambda: session_context.run(_resolve_ports)) == composed
    assert _resolve_ports() == outer
