"""One retained, read-only native observation for a bounded stop attempt."""

from __future__ import annotations

import time
from concurrent.futures import Future
from threading import Thread

from cadrumo.application.user_profile.access_contracts import Availability
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.transport import ConnectionContext

type NoticeConnections = tuple[tuple[ConnectionContext, LoginEvidence], ...]
type NoticeObservation = Future[tuple[ConnectionContext, ...] | None]


def start_notice_observation(connections: NoticeConnections, *, deadline: float) -> NoticeObservation:
    """Return a retained task; it cannot enqueue notices or request runtime stop.

    Native observation has no cancellation port. A stalled observation therefore
    remains the single retained worker; its daemon thread cannot extend process
    shutdown. The owner refuses retries until completion and never consumes an
    earlier attempt's result.
    """
    result: NoticeObservation = Future()

    def observe() -> None:
        eligible: list[ConnectionContext] = []
        try:
            for context, login in connections:
                if time.monotonic() >= deadline:
                    result.set_result(None)
                    return
                observation = login.observe(credential_facilities=Availability.UNAVAILABLE)
                if time.monotonic() >= deadline:
                    result.set_result(None)
                    return
                if observation.active and observation.unlocked:
                    eligible.append(context)
            result.set_result(tuple(eligible) if time.monotonic() < deadline else None)
        except Exception as error:
            result.set_exception(error)

    try:
        Thread(target=observe, name="runtime-upgrade-observation", daemon=True).start()
    except Exception as error:
        result.set_exception(error)
    return result
