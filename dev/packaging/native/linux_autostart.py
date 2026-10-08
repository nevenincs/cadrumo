"""Author scoped XDG login entries without registering anything on the build host."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from .identity import DistributionIdentity


@dataclass(frozen=True)
class AutostartEntry:
    """Installer-owned destination and complete desktop-entry contents."""

    destination: PurePosixPath
    contents: str


def _absolute(value: PurePosixPath) -> str:
    text = value.as_posix()
    if not value.is_absolute() or ".." in value.parts or any(ord(char) < 32 for char in text):
        raise ValueError("Autostart paths must be absolute and contain no traversal or control characters")
    return text


def _exec_argument(value: str) -> str:
    # Exec quoting is applied before the desktop file's general backslash decoding.
    # Percent is a field-code prefix even inside quotes, so literal percent is doubled.
    argument = value.replace("%", "%%")
    for char in ("\\", '"', "$", "`"):
        argument = argument.replace(char, "\\" + char)
    return '"' + argument.replace("\\", "\\\\") + '"'


def author_autostart(
    identity: DistributionIdentity,
    entrypoint: PurePosixPath,
    scope: Literal["user", "machine"],
    *,
    user_config: PurePosixPath | None = None,
) -> AutostartEntry:
    """Describe registration of an already verified version-independent manager.

    The installer supplies the admitted stable entrypoint and user's explicit XDG
    configuration directory. This author does no install, home discovery or opt-out
    mutation. Native package ownership and admission remain the installer's job.
    """
    if not identity.target.startswith("linux-"):
        raise ValueError("XDG autostart requires a Linux distribution")
    if not identity.manager_id or any(
        not (char.isascii() and (char.isalnum() or char in "._-")) for char in identity.manager_id
    ):
        raise ValueError("Invalid manager desktop identifier")
    if any(ord(char) < 32 for char in identity.manager_name):
        raise ValueError("Manager name contains desktop-entry control characters")
    executable = _absolute(entrypoint)
    if scope == "machine":
        if user_config is not None:
            raise ValueError("Machine registration must not write a user configuration")
        directory = PurePosixPath("/etc/xdg/autostart")
    elif scope == "user" and user_config is not None:
        _absolute(user_config)
        directory = user_config / "autostart"
    else:
        raise ValueError("User registration requires an explicit admitted XDG configuration directory")
    name = identity.manager_name.replace("\\", "\\\\")
    return AutostartEntry(
        destination=directory / f"{identity.manager_id}.desktop",
        contents=(
            "[Desktop Entry]\nType=Application\n"
            f"Name={name}\n"
            f"Exec={_exec_argument(executable)} --sign-in\n"
            "Terminal=false\nNoDisplay=true\n"
        ),
    )
