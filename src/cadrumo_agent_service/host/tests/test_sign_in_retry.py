"""A failed or refused sign-in is logged with its cause and reference, and a retry always starts afresh."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo.core.redaction.rules import redact_for_log
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS
from cadrumo.tests.log_records import delivered_records, delivered_text
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_startup as service_module
from ...adapters.agent_programs import AgentImage
from ...providers.application.contracts import (
    ProviderSettingsActionAccepted,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderStatusEntry,
)
from ...providers.application.tests.synthetic_catalog import synthetic_catalog
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ..auth_attempt import AuthAttempt
from ..sign_in_refusal import new_log_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ATTEMPT_LOGGER = "cadrumo_agent_service.host.auth_attempt"
_REFUSAL_LOGGER = "cadrumo_agent_service.host.sign_in_refusal"
_SCRUBBER_SAMPLES = 512
"""Minted references checked against the scrubber; a shape it rewrites one time in ten fails at once."""
_REF = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _entry() -> ProviderStatusEntry:
    return ProviderStatusEntry.model_validate(
        {
            "id": "example_cli",
            "provider": "example",
            "transport": "cli",
            "display_name": "Example",
            "auth_kind": "provider_sign_in_only",
            "consumers": ["assistant"],
            "mode": "provider_sign_in",
            "credential_saved": False,
            "available": False,
            "source": "none",
            "readiness": "sign_in_required",
            "reason": None,
            "base_url": None,
            "default_base_url": None,
            "cli_state": None,
            "revision": "a" * 64,
        },
        strict=False,
    )


def _wait_finished(attempt: AuthAttempt) -> None:
    deadline = time.monotonic() + HANG_GUARD_SECONDS
    while not attempt.finished and time.monotonic() < deadline:
        time.sleep(0.02)
    assert attempt.finished


def _absent_helper(tmp_path: Path, **keywords: Any) -> AuthAttempt:
    """An attempt whose helper cannot be started, which is a genuine launch failure."""
    return AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=tmp_path / "absent.exe",
        arguments=(),
        directory=tmp_path,
        environment={},
        valid=lambda: True,
        **keywords,
    )


def test_a_helper_that_cannot_start_logs_its_cause_and_reference_and_serves_them(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_ATTEMPT_LOGGER):
        attempt = _absent_helper(tmp_path)
        _wait_finished(attempt)
        attempt.close()
        records = delivered_records(caplog, _ATTEMPT_LOGGER)
    served = attempt.observe()
    assert (served["event"], served["reason"], served["cause"]) == ("failed", "provider_error", "helper_start_failed")
    assert served["log_ref"] == attempt.log_ref
    assert _REF.fullmatch(attempt.log_ref)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    message = records[0].getMessage()
    assert "cause=helper_start_failed" in message
    assert f"log_ref={attempt.log_ref}" in message
    assert "launch:" in message


def test_an_exception_message_never_reaches_the_log(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    def prepare() -> None:
        raise RuntimeError("PRIVATE-DETAIL token=abc")

    with caplog.at_level(logging.DEBUG, logger=_ATTEMPT_LOGGER):
        attempt = _absent_helper(tmp_path, prepare=prepare)
        _wait_finished(attempt)
        attempt.close()
        text = delivered_text(caplog)
    assert "prepare:RuntimeError" in text
    assert "cause=agent_stop_failed" in text
    assert "PRIVATE-DETAIL" not in text
    assert "token=abc" not in text


def test_a_settled_callback_that_raises_still_ends_the_attempt(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def settled() -> None:
        raise RuntimeError("PRIVATE-DETAIL")

    with caplog.at_level(logging.DEBUG, logger=_ATTEMPT_LOGGER):
        attempt = _absent_helper(tmp_path, settled=settled)
        _wait_finished(attempt)
        attempt.close()
        text = delivered_text(caplog)
    assert not attempt.active
    assert "settled callback failed" in text
    assert "PRIVATE-DETAIL" not in text


def _service(tmp_path: Path) -> tuple[AgentService, SimpleNamespace]:
    client = SimpleNamespace(lease=SimpleNamespace(profile_id=uuid4()), connection=SimpleNamespace(close=lambda: None))
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    return service, client


def _connectable(service: AgentService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Let a connect reach a real attempt whose helper program is absent, without a provider or a browser."""
    image = AgentImage(tmp_path / "absent.exe", (), tmp_path / "agent")
    monkeypatch.setattr(service_module, "agent_image", lambda *_a, **_k: image)
    monkeypatch.setattr(service_module, "hosted_python", lambda: None)
    monkeypatch.setattr(service._catalog, "catalog", synthetic_catalog)
    monkeypatch.setattr(service._catalog, "sign_in_providers", lambda: ("example",))
    monkeypatch.setattr(service._catalog, "gui_sign_in_providers", lambda: ("example",))
    monkeypatch.setattr(service._catalog, "gui_sign_in_methods", lambda: {"example": ("browser",)})
    generations = object()
    monkeypatch.setattr(service._credentials, "current_generations", lambda **_k: generations)


def _connect(service: AgentService) -> dict[str, Any]:
    return service.admin("connect", provider="example_cli", expected_revision="0" * 64, method="browser")


def _entry_accepted(service: AgentService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service._providers, "set_assistant_auth", lambda *_a, **_k: ProviderSettingsActionAccepted(entry=_entry())
    )


def test_a_retry_after_a_failed_attempt_starts_a_new_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service, _client = _service(tmp_path)
    _connectable(service, tmp_path, monkeypatch)
    _entry_accepted(service, monkeypatch)
    with caplog.at_level(logging.DEBUG):
        first = _connect(service)
        first_attempt = service._auth_attempt
        assert first_attempt is not None and first["attempt_id"] == first_attempt.id
        _wait_finished(first_attempt)
        second = _connect(service)
        second_attempt = service._auth_attempt
        assert second_attempt is not None
        _wait_finished(second_attempt)
    assert second.get("code") != "busy"
    assert second["attempt_id"] == second_attempt.id != first_attempt.id
    assert first_attempt.observe()["log_ref"] == first_attempt.log_ref
    assert second_attempt.observe()["log_ref"] == second_attempt.log_ref
    assert first_attempt.log_ref != second_attempt.log_ref
    first_attempt.close()
    second_attempt.close()


def test_a_retry_after_unconfirmed_cleanup_abandons_the_old_attempt_and_starts_afresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service, _client = _service(tmp_path)
    _connectable(service, tmp_path, monkeypatch)
    _entry_accepted(service, monkeypatch)
    stuck = Event()
    reader = Thread(target=stuck.wait, daemon=True)
    reader.start()
    try:
        with caplog.at_level(logging.DEBUG):
            _connect(service)
            old = service._auth_attempt
            assert old is not None
            _wait_finished(old)
            # A pipe reader that never ends is the very cleanup a failed job termination leaves unconfirmed.
            old._readers = [reader]
            old._clean = False
            assert old.active
            answer = _connect(service)
            fresh = service._auth_attempt
            assert fresh is not None and fresh is not old
            _wait_finished(fresh)
            text = delivered_text(caplog)
        assert answer.get("code") != "busy"
        assert answer["attempt_id"] == fresh.id
        assert old in service._abandoned_attempts
        assert "cause=previous_cleanup_unconfirmed" in text
        assert f"log_ref={old.log_ref}" in text
    finally:
        stuck.set()
        reader.join(HANG_GUARD_SECONDS)
    old.close()
    fresh.close()


def test_a_live_attempt_refuses_another_as_busy_with_a_logged_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service, _client = _service(tmp_path)
    _connectable(service, tmp_path, monkeypatch)
    _entry_accepted(service, monkeypatch)
    release = Event()
    live = _absent_helper(tmp_path, prepare=release.wait)
    service._auth_attempt = live
    try:
        with caplog.at_level(logging.DEBUG, logger=_REFUSAL_LOGGER):
            answer = _connect(service)
            records = delivered_records(caplog, _REFUSAL_LOGGER)
        assert (answer["kind"], answer["code"], answer["cause"]) == ("refused", "busy", "sign_in_in_progress")
        assert _REF.fullmatch(answer["log_ref"])
        (record,) = records
        assert record.levelno == logging.WARNING
        assert f"log_ref={answer['log_ref']}" in record.getMessage()
        assert "cause=sign_in_in_progress" in record.getMessage()
    finally:
        release.set()
        _wait_finished(live)
        live.close()


@pytest.mark.parametrize("failure", ["raises", "refuses"])
def test_a_refused_or_failed_settings_change_is_logged_without_its_message(
    failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service, _client = _service(tmp_path)
    _connectable(service, tmp_path, monkeypatch)

    def change(*_a: object, **_k: object) -> ProviderSettingsRefusal:
        if failure == "raises":
            raise OSError("PRIVATE-DETAIL C:/secret/path")
        return ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.REVISION_CONFLICT)

    monkeypatch.setattr(service._providers, "set_assistant_auth", change)
    with caplog.at_level(logging.DEBUG, logger=_REFUSAL_LOGGER):
        answer = _connect(service)
        text = delivered_text(caplog)
    expected = (
        ("service_failed", "settings_change_failed")
        if failure == "raises"
        else (
            "revision_conflict",
            "settings_refused",
        )
    )
    assert (answer["code"], answer["cause"]) == expected
    assert f"log_ref={answer['log_ref']}" in text
    assert f"cause={expected[1]}" in text
    assert "PRIVATE-DETAIL" not in text
    assert "secret/path" not in text
    if failure == "raises":
        assert "error_class=OSError" in text
    assert service._auth_attempt is None


def test_a_minted_log_reference_survives_the_log_scrubber() -> None:
    # A served reference must be findable in its own log line; the scrubber pseudonymises some short hex words.
    for log_ref in (new_log_ref() for _ in range(_SCRUBBER_SAMPLES)):
        line = f"provider sign-in refused cause=prepare_failed log_ref={log_ref}"
        assert redact_for_log(line) == line, log_ref
