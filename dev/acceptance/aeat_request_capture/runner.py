"""Run planned flows under the listener, always leaving a report of what happened."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping

from .flows import LOGIN, ReadFlow
from .listener import RequestListener, observing_playwright
from .recorder import CaptureRecorder


async def run_flows[StateT](
    flows: Iterable[ReadFlow],
    drivers: Mapping[str, Callable[[StateT], Awaitable[None]]],
    state: StateT,
    *,
    recorder: CaptureRecorder,
    listener: RequestListener,
) -> None:
    """Drive each flow in order, keeping one flow's failure from losing the others' evidence.

    A failure is recorded by exception type alone, because an exception's text can
    quote a URL. When the login did not complete, flows that need its session do
    not run, since running them could only start another phone prompt.
    """
    planned = tuple(flows)
    for flow in planned:
        recorder.register_flow(flow.flow_id, flow.policy_ids)
    login_failed = False
    with observing_playwright(listener):
        for flow in planned:
            if flow.needs_session and login_failed:
                recorder.set_outcome(flow.flow_id, "not-run:no-session")
                continue
            recorder.begin_flow(flow.flow_id)
            try:
                await drivers[flow.flow_id](state)
            except Exception as exc:
                recorder.end_flow(flow.flow_id, f"failed:{type(exc).__name__}")
                login_failed = login_failed or flow.flow_id == LOGIN
            else:
                recorder.end_flow(flow.flow_id, "completed")
