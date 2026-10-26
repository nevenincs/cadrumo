"""XDG authoring keeps installation scope and literal executable arguments."""

from pathlib import PurePosixPath

import pytest

from ..identity import identity
from ..linux_autostart import author_autostart

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_both_scopes_use_the_channel_identity_and_explicit_stable_entrypoint() -> None:
    value = identity("linux-x86-64", "preview")
    entry = PurePosixPath("/opt/cadrumo-preview/cadrumo-manager")
    machine = author_autostart(value, entry, "machine")
    user = author_autostart(value, entry, "user", user_config=PurePosixPath("/home/example/.config"))
    assert machine.destination == PurePosixPath(f"/etc/xdg/autostart/{value.manager_id}.desktop")
    assert user.destination == PurePosixPath(f"/home/example/.config/autostart/{value.manager_id}.desktop")
    assert machine.contents == user.contents
    assert f'Exec="{entry}" --sign-in\n' in machine.contents
    assert "Hidden=true" not in machine.contents


def test_exec_quotes_metacharacters_and_never_interprets_percent_field_codes() -> None:
    entry = PurePosixPath('/opt/space %F $HOME `echo x`/manager"')
    result = author_autostart(identity("linux-x86-64"), entry, "machine")
    assert 'Exec="/opt/space %%F \\\\$HOME \\\\`echo x\\\\`/manager\\\\"" --sign-in\n' in result.contents


@pytest.mark.parametrize("entry", ["relative/manager", "/opt/../manager", "/opt/line\nbreak"])
def test_ambiguous_entrypoints_are_refused(entry: str) -> None:
    with pytest.raises(ValueError):
        author_autostart(identity("linux-x86-64"), PurePosixPath(entry), "machine")


def test_scope_cannot_guess_a_home_or_cross_into_user_data() -> None:
    value = identity("linux-x86-64")
    entry = PurePosixPath("/opt/cadrumo/cadrumo-manager")
    with pytest.raises(ValueError):
        author_autostart(value, entry, "user")
    with pytest.raises(ValueError):
        author_autostart(value, entry, "machine", user_config=PurePosixPath("/home/example/.config"))
