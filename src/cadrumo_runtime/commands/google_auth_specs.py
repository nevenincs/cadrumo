"""Import-light production command authority for the config Google family."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.execution_policies import (
    GOOGLE_DESTRUCTIVE,
    GOOGLE_READ,
    GOOGLE_WRITE,
    state_free_group_spec,
)
from cadrumo_client.commands.leaf_specs import ModuleLeafBuilder
from cadrumo_client.contracts.command_ports import ProfileAuthenticationPosture

# Every dynamically resolved handler module is named here as a WHOLE dotted path.
# The path used to be built with an f-string, which meant no static reader -- grep,
# the import-boundary checker, or a dead-code sweep -- could see the edge, so all of
# these modules read as orphaned while backing live verbs. A wrong key now raises
# at spec-build time instead of failing lazily on first invocation.
_HANDLER_MODULES: Final[dict[str, str]] = {
    "_google": ".google",
    "_google_folder": "._google_folder",
    "_google_folder_payloads": "._google_folder_payloads",
    "_google_payloads": "cadrumo_client.commands.google_payloads",
}
_leaf = ModuleLeafBuilder(_HANDLER_MODULES, __package__, ProfileAuthenticationPosture.RESUME_FALLBACK).leaf


RUNTIME_GOOGLE_AUTH_COMMAND_SPECS = (
    state_free_group_spec("config_google", "config", "google", "cli.config.google.help"),
    _leaf(
        "config_google_login",
        "config_google",
        "login",
        "cli.config.google.login_help",
        "_google",
        "google_login",
        "_google_payloads",
        "GoogleLoginResult",
        GOOGLE_WRITE,
    ),
    _leaf(
        "config_google_status",
        "config_google",
        "status",
        "cli.config.google.status_help",
        "_google",
        "google_status",
        "_google_payloads",
        "GoogleStatusResult",
        GOOGLE_READ,
    ),
    _leaf(
        "config_google_logout",
        "config_google",
        "logout",
        "cli.config.google.logout_help",
        "_google",
        "google_logout",
        "_google_payloads",
        "GoogleLogoutResult",
        GOOGLE_DESTRUCTIVE,
    ),
)


__all__ = ["RUNTIME_GOOGLE_AUTH_COMMAND_SPECS"]
