"""Refuse a process-environment name that Cadrumo's settings own and no setting reads.

A name that nothing reads configures nothing, and a configuration that looks
applied but is not is worse than an absent one: a retired model option kept in
a shell profile reads as live long after the code that honoured it is gone.
:class:`~core.config.Settings` therefore refuses, when it loads, a process
environment name in a family it owns whole that is not one of its settings.

Only families that ``Settings`` owns whole are checked. Other ``CADRUMO_``
names are owned elsewhere -- the native host's launch contract, the agent's own
prefix, the development tools and the test harness -- and no single declaration
of them can be read from Python, so a family joins
:data:`SETTINGS_OWNED_NAME_PREFIXES` only while every name under it in the
repository's sources is a setting of this model. A gate under ``dev/quality``
keeps that true.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Final

from .errors.hierarchy import CoreError

SETTINGS_OWNED_NAME_PREFIXES: Final[tuple[str, ...]] = ("CADRUMO_LLM_",)
"""Environment families whose every name is a ``Settings`` field; matched without regard to case."""

_UNREAD_SETTING_LOCALE_KEY: Final = "errors.refused.refused_unread_setting"


class UnreadSettingError(CoreError):
    """The process environment carries a name in a family the settings own that no setting reads.

    ``context`` holds the names, never a value: the value of an unread name was
    meant for something that no longer exists and may still be a secret.
    """

    def __init__(self, names: Iterable[str]) -> None:
        """Name the unread settings; the message says they are not settings Cadrumo reads."""
        ordered = tuple(sorted(set(names)))
        listed = ", ".join(ordered)
        super().__init__(
            f"Not a setting Cadrumo reads: {listed}. Remove it from the environment.",
            translated_message=_UNREAD_SETTING_LOCALE_KEY,
            context={"names": listed, "count": len(ordered)},
        )
        self.names: tuple[str, ...] = ordered


def unread_setting_names(
    environment_names: Iterable[str],
    read_names: Collection[str],
    *,
    prefixes: Collection[str] = SETTINGS_OWNED_NAME_PREFIXES,
) -> tuple[str, ...]:
    """Return the names in an owned family that none of ``read_names`` matches, in name order.

    Args:
        environment_names: The names present in the process environment.
        read_names: Every name the settings read, in upper case.
        prefixes: The families to check, in upper case.

    Returns:
        The unread names in upper case, which is how the settings compare them.
    """
    owned = tuple(prefixes)
    upper = {name.upper() for name in environment_names}
    return tuple(sorted(name for name in upper if name.startswith(owned) and name not in read_names))


def require_no_unread_setting_names(
    environment_names: Iterable[str],
    read_names: Collection[str],
    *,
    prefixes: Collection[str] = SETTINGS_OWNED_NAME_PREFIXES,
) -> None:
    """Raise :class:`UnreadSettingError` when the environment carries an unread name in an owned family."""
    unread = unread_setting_names(environment_names, read_names, prefixes=prefixes)
    if unread:
        raise UnreadSettingError(unread)
