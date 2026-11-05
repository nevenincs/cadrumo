"""The service loop reads its own lifetime end apart from a runtime that closed on it."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, Thread
from typing import NoReturn, cast

import pytest

from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import main
from ...service import AgentService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STALL_DEADLINE_SECONDS = 10.0
"""How long a stalled step waits for its counterpart; only a broken interleaving ever reaches it."""


class _Connection:
    def __init__(self) -> None:
        self.gone = Event()

    @property
    def closed(self) -> bool:
        return self.gone.is_set()

    def close(self) -> None:
        self.gone.set()


class _Service:
    """Closes its runtime connection on ``request_close``, as the agent service does, then stalls there.

    The stall holds the lifetime end between closing the connection and
    anything it does afterwards, so the loop handles the cut-short claim in
    exactly that window.
    """

    def __init__(self, connection: _Connection, stop: Event) -> None:
        self._connection = connection
        self._stop = stop
        self.released = Event()
        self.stop_set_at_close: bool | None = None

    def hold_for_recovery(self) -> float | None:
        return None

    def request_close(self) -> None:
        self.stop_set_at_close = self._stop.is_set()
        self._connection.close()
        assert self.released.wait(_STALL_DEADLINE_SECONDS), "the stalled close was never released"


class _Client:
    """A lease claim that waits for the runtime's reply until its connection is closed under it."""

    def __init__(self, connection: _Connection, while_waiting: Callable[[], object]) -> None:
        self.connection = connection
        self._while_waiting = while_waiting
        self.claims = 0

    def claim(self) -> NoReturn:
        self.claims += 1
        # A loop that claims again on a connection that is gone would spin forever.
        assert self.claims == 1, "claimed again after the connection closed"
        self._while_waiting()
        assert self.connection.gone.wait(_STALL_DEADLINE_SECONDS), "the connection never closed"
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)


def _run(client: _Client, service: _Service, stop: Event, wake: Event) -> None:
    main._run_service_loop(cast(InstalledServiceClient, client), cast(AgentService, service), stop, wake)


def test_the_lifetime_end_is_marked_before_the_connection_closes() -> None:
    stop, wake = Event(), Event()
    service = _Service(_Connection(), stop)
    service.released.set()
    main._end_lifetime(cast(AgentService, service), stop, wake)
    assert service.stop_set_at_close is True
    assert stop.is_set() and wake.is_set()


def test_a_claim_cut_short_by_the_service_lifetime_end_drains_without_a_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop, wake = Event(), Event()
    connection = _Connection()
    service = _Service(connection, stop)
    # The parent closes the service's input while a lease claim waits for its reply.
    lifetime = Thread(target=main._end_lifetime, args=(service, stop, wake), name="test-service-lifetime")
    client = _Client(connection, lifetime.start)
    try:
        with caplog.at_level(logging.DEBUG, logger="cadrumo_agent_service"):
            _run(client, service, stop, wake)
    finally:
        service.released.set()
        lifetime.join(_STALL_DEADLINE_SECONDS)
    assert not lifetime.is_alive()
    assert client.claims == 1
    assert [record for record in delivered_records(caplog) if record.levelno >= logging.WARNING] == []
    drained = delivered_records(caplog, "cadrumo_agent_service.main")
    assert [(record.levelno, record.getMessage()) for record in drained] == [
        (logging.INFO, "agent service lifetime ended during a lease claim")
    ]


def test_a_runtime_that_closes_the_connection_under_a_claim_stays_a_refusal() -> None:
    stop, wake = Event(), Event()
    connection = _Connection()
    client = _Client(connection, connection.close)
    with pytest.raises(RefusalError) as refused:
        _run(client, _Service(connection, stop), stop, wake)
    assert refused.value.reason is RefusalCode.CONNECTION_CLOSED
    assert not stop.is_set()
