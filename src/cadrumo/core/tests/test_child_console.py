"""Helper children share the console unless this process isolated them."""

from __future__ import annotations

import subprocess
import sys

import pytest

from ..child_console import ChildConsole, child_console, child_console_binding, child_console_creation_flags

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_unbound_process_shares_its_console_and_launches_children_unchanged() -> None:
    with child_console_binding.override(None):
        assert child_console() is ChildConsole.SHARED
        assert child_console_creation_flags() == 0


def test_an_isolating_process_gives_children_a_windowless_console_in_their_own_ctrl_c_group() -> None:
    with child_console_binding.override(ChildConsole.OWN):
        flags = child_console_creation_flags()
    if sys.platform != "win32":
        assert flags == 0
        return
    assert flags == subprocess.CREATE_NO_WINDOW
    # A new process group would make the child ignore Ctrl+C; a detached child has no console.
    assert not flags & (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
