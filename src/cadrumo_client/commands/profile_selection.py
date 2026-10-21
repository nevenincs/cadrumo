"""Ask the running runtime which profile a command means, before any profile session exists.

A command neither resolves an operator's profile text nor reads the selection
itself: the runtime answers both on a connection that holds no session and
gains none. With no runtime the question is refused as unavailable, as the
sign-in that follows it would be.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import NamedTuple

from cadrumo_client.contracts.profile_selection import ActiveProfileReply
from cadrumo_client.transport.installation_client import InstallationClient, open_installed_installation_client


class LoginTarget(NamedTuple):
    """The live profile the runtime resolved an operator's text to."""

    bucket_id: str
    label: str


def _asked[T](question: Callable[[InstallationClient], T]) -> T:
    """Open one sessionless connection, ask one question and close it."""
    client = asyncio.run(open_installed_installation_client())
    try:
        return question(client)
    finally:
        client.close()


def runtime_login_target(name: str) -> LoginTarget | None:
    """Return the live profile ``name`` names by identifier or exact label, or ``None`` when it names none."""
    reply = _asked(lambda client: client.login_target(name))
    if reply.profile_id is None or reply.label is None:
        return None
    return LoginTarget(str(reply.profile_id), reply.label)


def require_runtime_login_target(name: str) -> LoginTarget:
    """Return the live profile ``name`` names, or refuse it as an unknown profile.

    Raises:
        ProfileNotFoundError: ``name`` names no live profile.
    """
    from cadrumo.domain.user_profile.errors import ProfileNotFoundError

    target = runtime_login_target(name) if name.strip() else None
    if target is None:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile", context={"name": name.strip() or name}
        )
    return target


def runtime_active_profile() -> ActiveProfileReply:
    """Return the runtime's answer to which profile is selected and which holds the live sign-in."""
    return _asked(lambda client: client.active_profile())


def runtime_selected_profile_id() -> str | None:
    """Return the profile the runtime has selected, or ``None`` when none is.

    Raises:
        ActiveProfilePointerError: The runtime could not read the selection,
            which never reads as nothing selected.
    """
    from cadrumo.core.errors.hierarchy import ActiveProfilePointerError
    from cadrumo_client.contracts.sign_in import SignInPresence

    answer = runtime_active_profile()
    if answer.selected_profile_id is None:
        if answer.presence is SignInPresence.UNKNOWN:
            raise ActiveProfilePointerError(path="active-profile selection")
        return None
    return str(answer.selected_profile_id)


def command_profile_id() -> str | None:
    """Return the profile this command is bound to, or else the one the runtime has selected.

    An admitted command is bound to its exact profile for the rest of the
    invocation; only a command not yet bound asks the runtime which profile is
    selected.

    Raises:
        ActiveProfilePointerError: The runtime could not read the selection.
    """
    from cadrumo.core.config import load_settings

    bound = (load_settings().cadrumo_active_profile or "").strip()
    return bound or runtime_selected_profile_id()


__all__ = [
    "LoginTarget",
    "command_profile_id",
    "require_runtime_login_target",
    "runtime_active_profile",
    "runtime_login_target",
    "runtime_selected_profile_id",
]
