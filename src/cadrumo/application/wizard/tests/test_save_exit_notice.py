"""Real-behavior tests for the create-mode save-and-exit disclosure notice.

A save-and-exit leaves the profile ``SETUP_INCOMPLETE``, so the command
emits no created/active success. Instead :func:`_emit_save_exit_notice`
surfaces an info :class:`Notice` (``config.profile.create.saved_resume_later``)
telling the operator the setup was saved and how to resume, so a save-exit
is never a silent exit.

Coordinated transient: ``application.wizard.notices.setup_saved_resume_later``
lands in the coordinator's serialized locale pass right after this code
commits. The tests assert the notice CODE, severity, and resume
``suggestion`` structurally, and the message via KEY IDENTITY
(``tr(<key>)``) — holding against the humanised fallback now and the
landed string later.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import click
import pytest

from ....core.i18n import tr
from ....core.json_contract import NoticeSeverity
from .._commands import _SAVE_EXIT_RESUME_CODE, _emit_save_exit_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SAVE_EXIT_MESSAGE = tr("application.wizard.notices.setup_saved_resume_later", name="probe-profile")


@pytest.fixture
def _json_context() -> Iterator[None]:
    with click.Context(click.Command("probe"), obj={"json": True}):
        yield


def test_save_exit_envelope_carries_resume_later_notice(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """The save-exit envelope carries the info notice with the resume suggestion."""
    _emit_save_exit_notice("probe-profile")

    document = json.loads(capsys.readouterr().out)
    codes = {notice["code"]: notice for notice in document["notices"]}
    assert _SAVE_EXIT_RESUME_CODE in codes
    notice = codes[_SAVE_EXIT_RESUME_CODE]
    assert notice["severity"] == NoticeSeverity.INFO.value
    assert notice["message"] == _SAVE_EXIT_MESSAGE
    assert notice["suggestion"] == "aeat config profile create probe-profile"


def test_save_exit_text_output_names_the_resume_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Text-mode save-exit surfaces the message and the resume command."""
    _emit_save_exit_notice("probe-profile")

    output = capsys.readouterr().out
    assert _SAVE_EXIT_MESSAGE in output
    assert "aeat config profile create probe-profile" in output
