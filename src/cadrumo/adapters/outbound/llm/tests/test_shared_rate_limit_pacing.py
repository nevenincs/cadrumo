"""One rate limit paces the whole run, not one request.

A retry schedule paces the request that owns it. A run of N documents therefore
discovers the same account-wide limit N times and issues N calls into a window
that already refused the first -- which is not a rate limit being respected but
N of them being ignored in sequence.

Every case runs the client's own dispatch loop with an adapter that answers the
first item with a rate limit carrying a server delay, and observes the window
on the SECOND item, which is the one a per-request policy cannot pace.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....core.config_support import LLMProvider
from .....tests.fixtures.settings import EnvFileFreeSettings
from .. import client as client_module
from ..client import LLMClient, LLMRetryPolicy
from ..errors import LLMRateLimitError
from ._client_process_state import reset_client_process_state
from .scripted_adapter_support import COMPLETION_TEXT, ScriptedAdapter, provider_request

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RETRY_AFTER_S = 0.6


@pytest.fixture(autouse=True)
def _fresh_process_state() -> Iterator[None]:
    """Clear the process-wide gates around each case.

    The pacing outlives a single client by design -- that is the property under
    test -- so a case would otherwise inherit a window armed by its predecessor
    and observe a wait it did not cause.
    """
    reset_client_process_state()
    yield
    reset_client_process_state()


def _rate_limited() -> ScriptedAdapter:
    return ScriptedAdapter([LLMRateLimitError(retry_after_seconds=_RETRY_AFTER_S)])


def _answering() -> ScriptedAdapter:
    return ScriptedAdapter([None])


def _client(tmp_path: Path, *, attempts: int = 1, budget_s: float = 30.0) -> LLMClient:
    settings = EnvFileFreeSettings(cadrumo_storage_root=tmp_path)
    return LLMClient(
        settings=settings,
        retry_policy=LLMRetryPolicy(
            max_attempts=attempts, initial_backoff_s=0.01, max_backoff_s=0.02, budget_s=budget_s
        ),
    )


def _dispatch(client: LLMClient, adapter: ScriptedAdapter, prompt: str) -> str:
    return asyncio.run(client._complete_with_retries(adapter, provider_request(prompt))).text


def test_a_rate_limit_on_one_item_paces_the_next_item(tmp_path: Path) -> None:
    """The run-wide property: the second dispatch waits on the first one's window.

    Measured on the gap between the two items' arrivals at their adapters,
    because a client that recorded a delay and dispatched anyway would look
    identical from inside.
    """
    client = _client(tmp_path)
    first, second = _rate_limited(), _answering()
    with pytest.raises(LLMRateLimitError):
        _dispatch(client, first, "first item")

    assert client_module._PROVIDER_PACING.remaining_s(LLMProvider.AGENT) > 0, "the shared window was never armed"

    assert _dispatch(client, second, "second item") == COMPLETION_TEXT
    gap = second.arrived_at[0] - first.arrived_at[0]
    assert gap >= _RETRY_AFTER_S * 0.8, (
        f"the second dispatch arrived {gap:.2f}s after the first, inside the {_RETRY_AFTER_S}s window "
        "the provider asked for; the backoff paced one request rather than the run"
    )


def test_without_a_rate_limit_the_second_item_is_not_delayed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The positive control, and the proof that the window OPENS rather than merely closing.

    Same two dispatches, same client -- only the rate limit differs. The window
    each dispatch's pacing gate saw is recorded at the gate itself rather than
    inferred from arrival gaps, which under load measure the host, not the
    pacing.
    """
    observed_windows: list[float] = []
    gate = LLMClient._await_shared_pacing

    async def recording_gate(provider: LLMProvider, policy: LLMRetryPolicy) -> None:
        observed_windows.append(client_module._PROVIDER_PACING.remaining_s(provider))
        await gate(provider, policy)

    monkeypatch.setattr(LLMClient, "_await_shared_pacing", staticmethod(recording_gate))
    client = _client(tmp_path)
    _dispatch(client, _answering(), "first item")
    _dispatch(client, _answering(), "second item")

    assert observed_windows == [0.0, 0.0], f"an unlimited run still asked its dispatches to wait: {observed_windows}"
    assert client_module._PROVIDER_PACING.remaining_s(LLMProvider.AGENT) == 0


def test_the_window_is_shared_across_clients(tmp_path: Path) -> None:
    """A second client is a second batch item, and the limit belongs to the account.

    Per-client state would pace neither: a run that builds one client per
    document -- which is how the readers are constructed -- would rediscover the
    same limit for every document.
    """
    first, second = _rate_limited(), _answering()
    with pytest.raises(LLMRateLimitError):
        _dispatch(_client(tmp_path / "first"), first, "first item")

    _dispatch(_client(tmp_path / "second"), second, "second item")

    assert second.arrived_at[0] - first.arrived_at[0] >= _RETRY_AFTER_S * 0.8


def test_a_limit_discovered_on_the_last_attempt_still_paces_the_run(tmp_path: Path) -> None:
    """The item that gives up must not be the one that tells nobody.

    Arming only where the loop decides to retry would leave the final attempt's
    limit unrecorded, and the next item would walk straight into it -- the
    failure being least visible exactly when the run is already struggling.
    """
    # One attempt: the loop never reaches its retry branch at all.
    with pytest.raises(LLMRateLimitError):
        _dispatch(_client(tmp_path, attempts=1), _rate_limited(), "only attempt")

    assert client_module._PROVIDER_PACING.remaining_s(LLMProvider.AGENT) > 0


def test_the_shared_wait_is_bounded_by_the_retry_budget(tmp_path: Path) -> None:
    """A vendor may name a window measured in minutes; a batch must not silently sleep it.

    The window stays armed and readable so a surface can report it, but no
    single dispatch blocks longer than the budget it was given.
    """
    client = _client(tmp_path, budget_s=0.2)
    with pytest.raises(LLMRateLimitError):
        _dispatch(client, _rate_limited(), "first item")

    started = time.monotonic()
    _dispatch(client, _answering(), "second item")
    waited = time.monotonic() - started

    assert waited < _RETRY_AFTER_S, f"the dispatch slept {waited:.2f}s, past the 0.2s budget it was given"
