"""Portable refusal and cleanup contracts for native Secret Service replies."""

from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody.linux_secret_cleanup import close_secret_bus_after_failure
from cadrumo.adapters.persistence.storage.custody.linux_secret_contracts import (
    SESSION_IFACE,
    secret_object_path,
    secret_reply_body,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.mark.parametrize("path", ["/org/freedesktop/secrets/session/s1", "/org/freedesktop/secrets/collection/login"])
def test_exact_secret_object_path_is_preserved(path: str) -> None:
    assert secret_object_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        None,
        b"/session/s1",
        "/",
        "session/s1",
        "/session//s1",
        "/session/s1/",
        "/session/s1\0",
        "/s-1",
        "/" + "s" * 1024,
    ],
)
def test_noncanonical_or_unbounded_secret_path_refuses(path: object) -> None:
    with pytest.raises(AutomationCustodyError) as caught:
        secret_object_path(path)
    assert caught.value.reason is AutomationCustodyCode.INVALID


def test_root_is_admitted_only_when_the_protocol_explicitly_allows_it() -> None:
    assert secret_object_path("/", allow_root=True) == "/"
    assert secret_reply_body((None, b"", 0), 3) == (None, b"", 0)


@pytest.mark.parametrize("body", [None, [], ["value"], (), ("value", "extra")])
def test_reply_body_requires_exact_tuple_arity(body: object) -> None:
    with pytest.raises(AutomationCustodyError) as caught:
        secret_reply_body(body, 1)
    assert caught.value.reason is AutomationCustodyCode.INVALID


class _FailingBus:
    def __init__(self, failure: BaseException) -> None:
        self.failure = failure
        self.closes = 0
        self.calls: list[tuple[str, str, str]] = []

    def close(self) -> None:
        self.closes += 1
        raise self.failure

    def call(
        self,
        path: str,
        interface: str,
        method: str,
        signature: str = "",
        body: tuple[Any, ...] = (),
        *,
        destination: str | None = None,
    ) -> tuple[Any, ...]:
        self.calls.append((path, interface, method))
        raise self.failure


@pytest.mark.parametrize("session_path", [None, "/org/freedesktop/secrets/session/s1"])
def test_failed_close_retains_the_primary_and_prior_retry_diagnostic(session_path: str | None) -> None:
    primary = RuntimeError("mutation result is uncertain")
    previous = AsyncResourceCleanupError(
        (), (OSError("earlier close failed"),), retry_task_name="existing-cleanup", close_attempts=1
    )
    primary.__dict__["cleanup_error"] = previous
    primary.__dict__["async_cleanup_error"] = previous
    close_failure = OSError("native close failed")
    bus = _FailingBus(close_failure)

    close_secret_bus_after_failure(bus, primary, session_path=session_path)

    retained = primary.__dict__["cleanup_error"]
    assert isinstance(retained, AsyncResourceCleanupError)
    assert primary.__dict__["async_cleanup_error"] is retained
    assert retained.__cause__ is close_failure
    assert "Secret-store close also failed; no native retry was retained" in primary.__notes__
    assert bus.closes == (1 if session_path is None else 0)
    assert bus.calls == ([] if session_path is None else [(session_path, SESSION_IFACE, "Close")])
