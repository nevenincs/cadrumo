"""Lightweight classification of runtime-owned command arguments."""

from __future__ import annotations

from collections.abc import Sequence

OWNED_COMMAND_ROOTS = frozenset({"config"})
_ROOT_VALUE_OPTIONS = frozenset(
    {
        "--language",
        "--lang",
        "--profile",
        "--profile-secrets-fd",
        "--profile-auth-method",
        "--profile-credential-ref",
        "--format",
    }
)
_ROOT_FLAG_OPTIONS = frozenset({"--profile-secrets-stdin", "--quiet", "--verbose", "--debug", "--help"})


def owns_command_args(arguments: Sequence[str]) -> bool:
    """Classify runtime-owned command argv after declared root options.

    Unknown options stop classification so a server option such as
    ``--storage-root config`` remains owned by the daemon parser.
    """
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            return False
        if argument in OWNED_COMMAND_ROOTS:
            return True
        if argument in _ROOT_FLAG_OPTIONS:
            index += 1
            continue
        option, separator, _value = argument.partition("=")
        if option in _ROOT_VALUE_OPTIONS:
            if separator:
                index += 1
                continue
            if index + 1 >= len(arguments):
                return False
            index += 2
            continue
        if argument.startswith("-"):
            return False
        return False
    return False


__all__ = ["OWNED_COMMAND_ROOTS", "owns_command_args"]
