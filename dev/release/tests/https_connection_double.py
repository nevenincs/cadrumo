"""A recording stand-in for the HTTPS connection the package-index probe opens."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from .. import package_index_probe


@dataclass
class RecordedConnections:
    connection_args: list[tuple[str, int | None, int]] = field(default_factory=list)
    requests: list[tuple[str, str, dict[str, str]]] = field(default_factory=list)
    closed: list[bool] = field(default_factory=list)


def install_https_connection(
    monkeypatch: pytest.MonkeyPatch,
    response_type: Callable[[], object],
    *,
    close_error: OSError | None = None,
) -> RecordedConnections:
    """Replace the probe's HTTPS connection; ``close_error`` makes ``close`` raise after recording."""
    recorded = RecordedConnections()

    class _Connection:
        def __init__(self, hostname: str, port: int | None, *, timeout: int) -> None:
            recorded.connection_args.append((hostname, port, timeout))

        def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
            recorded.requests.append((method, target, headers))

        def getresponse(self) -> object:
            return response_type()

        def close(self) -> None:
            recorded.closed.append(True)
            if close_error is not None:
                raise close_error

    monkeypatch.setattr(package_index_probe.http.client, "HTTPSConnection", _Connection)
    return recorded
