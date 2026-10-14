"""Attended lifecycle notices use human stderr without changing machine output."""

import sys
from collections.abc import Callable
from typing import override
from uuid import uuid4

import pytest
import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.i18n.render import tr
from cadrumo_client.commands import profile_binding as binding
from cadrumo_client.contracts.session_events import LifecycleNotice
from cadrumo_client.transport.frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class NoticeClient(FrontendClient):
    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._frontend = OperationFrontendProjection.CLI
        self.receive: Callable[[LifecycleNotice], None] | None = None

    @override
    def subscribe_lifecycle_notices(self, receive: Callable[[LifecycleNotice], None]) -> Callable[[], None]:
        self.receive = receive

        def unsubscribe() -> None:
            self.receive = None

        return unsubscribe


@pytest.mark.parametrize("machine,terminal", [(False, True), (True, True), (False, False)])
def test_cli_notice_never_contaminates_json_or_unattended_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], machine: bool, terminal: bool
) -> None:
    client = NoticeClient()
    monkeypatch.setattr(binding, "json_output_requested", lambda: machine)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: terminal)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: terminal)
    monkeypatch.setattr(binding, "_release_profile_client", lambda *_: None)
    context = typer.Context(typer.main.TyperCommand(name="notice"))
    with context:
        binding.bind_profile_client(context, client, profile_id=client.profile_id)
        if machine or not terminal:
            assert client.receive is None
        else:
            assert client.receive is not None
            client.receive(LifecycleNotice(runtime_boot_id=uuid4(), connection_id=uuid4(), notice_id=uuid4()))
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == (tr("common.manager.update_pending") + "\n" if terminal and not machine else "")
    assert client.receive is None
