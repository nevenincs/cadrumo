"""Name a profile's provider homes for the desktop console, as the bundled agent lays them out.

The agent owns where each provider program keeps its sign-in: its public
``hosted_locations`` derives every location beneath a hosted root, and its
public ``PROVIDER_SIGN_INS`` says which provider home each sign-in uses and
which variable points the provider program at it. This module reads both and
keeps only the homes the console may carry, so a console program finds the
same sign-in the service's provider sign-in wrote. Nothing here reads a home's
contents.

Only the standard library is imported, so the agent's own interpreter can run
this function against the agent's own modules.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Final

LAYOUT_MODULE: Final = "cadrumo_agent.control.state_layout"
"""The agent's public module that derives every location beneath a hosted root."""
SIGN_IN_MODULE: Final = "cadrumo_agent.providers.provider_login"
"""The agent's public module that declares each provider sign-in and its home."""
CONSOLE_HOME_VARIABLES: Final = frozenset({"CLAUDE_CONFIG_DIR", "CODEX_HOME"})
"""The provider home variables a console carries; a sign-in that seats ``HOME`` itself is not one."""


def provider_homes(agent_root: Path, *, layout: ModuleType, sign_ins: ModuleType) -> dict[str, str]:
    """Return each console provider home variable and the home the agent derives for it under ``agent_root``.

    Raises:
        ValueError: When the agent names a provider home it cannot derive.
    """
    locations = layout.hosted_locations(agent_root)
    homes: dict[str, str] = {}
    for sign_in in sign_ins.PROVIDER_SIGN_INS.values():
        variable = sign_in.home_environment
        if variable in CONSOLE_HOME_VARIABLES:
            homes[variable] = str(locations.provider_home(sign_in.home_provider))
    return homes


__all__ = ["CONSOLE_HOME_VARIABLES", "LAYOUT_MODULE", "SIGN_IN_MODULE", "provider_homes"]
