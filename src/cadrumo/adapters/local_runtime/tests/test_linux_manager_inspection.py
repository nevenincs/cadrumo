"""Portable classification of bounded systemd inspection responses."""

from __future__ import annotations

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeManagerProcessState

from .. import linux_manager
from ..linux_manager import LinuxUserManager
from ..manager_commands import ManagerCommandResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_MISSING_UNIT = "\n".join(
    (
        "LoadState=not-found",
        "ActiveState=inactive",
        "FragmentPath=",
        "DropInPaths=",
        "UnitFileState=",
        "NeedDaemonReload=no",
    )
)


def _parser_subject() -> LinuxUserManager:
    # Constructor owner/root checks have native tests. These tests isolate the
    # already-bound manager's response parser without pretending to run Linux.
    manager = object.__new__(LinuxUserManager)
    manager._name = "synthetic.service"
    manager._definition = "synthetic unit body"
    return manager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "reason"),
    (
        (ManagerCommandResult(returncode=0, output="UnknownProperty=value"), RuntimeRefusalCode.INVALID_FRAME),
        (ManagerCommandResult(returncode=1, output="UnknownProperty=value"), RuntimeRefusalCode.INVALID_FRAME),
        (ManagerCommandResult(returncode=0, output=""), RuntimeRefusalCode.INVALID_FRAME),
        (
            ManagerCommandResult(returncode=0, output=_MISSING_UNIT + "\nLoadState=not-found"),
            RuntimeRefusalCode.INVALID_FRAME,
        ),
    ),
)
async def test_malformed_manager_output_remains_a_typed_refusal(
    monkeypatch: pytest.MonkeyPatch, response: ManagerCommandResult, reason: RuntimeRefusalCode
) -> None:
    async def respond(*_args: object) -> ManagerCommandResult:
        return response

    monkeypatch.setattr(linux_manager, "run_manager_command", respond)
    with pytest.raises(RuntimeRefusalError) as caught:
        await _parser_subject().inspect()
    assert caught.value.reason is reason
    if response.output:
        assert response.output not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", (RuntimeRefusalCode.INVALID_FRAME, RuntimeRefusalCode.DEADLINE_EXCEEDED))
async def test_command_frame_or_timeout_refusal_is_not_reported_as_unavailable(
    monkeypatch: pytest.MonkeyPatch, reason: RuntimeRefusalCode
) -> None:
    async def refuse(*_args: object) -> ManagerCommandResult:
        raise RuntimeRefusalError(reason)

    monkeypatch.setattr(linux_manager, "run_manager_command", refuse)
    with pytest.raises(RuntimeRefusalError) as caught:
        await _parser_subject().inspect()
    assert caught.value.reason is reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    (
        ManagerCommandResult(returncode=1, output=""),
        ManagerCommandResult(returncode=1, output=_MISSING_UNIT),
    ),
)
async def test_absent_manager_or_missing_unit_has_truthful_availability(
    monkeypatch: pytest.MonkeyPatch, response: ManagerCommandResult
) -> None:
    async def respond(*_args: object) -> ManagerCommandResult:
        return response

    monkeypatch.setattr(linux_manager, "run_manager_command", respond)
    observed = await _parser_subject().inspect()
    assert observed.available is bool(response.output)
    assert not observed.provisioned
    assert not observed.binding_matches
    assert observed.process_state is (
        RuntimeManagerProcessState.STOPPED if response.output else RuntimeManagerProcessState.UNKNOWN
    )


@pytest.mark.asyncio
async def test_missing_native_manager_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(*_args: object) -> ManagerCommandResult:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    monkeypatch.setattr(linux_manager, "run_manager_command", refuse)
    observed = await _parser_subject().inspect()
    assert not observed.available and not observed.provisioned
    assert observed.process_state is RuntimeManagerProcessState.UNKNOWN
