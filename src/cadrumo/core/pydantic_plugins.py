"""The one place Cadrumo's own processes turn off pydantic plugin discovery.

Pydantic discovers plugins on the first model build by reading the entry-point
metadata of every installed distribution, which costs tens of milliseconds in
each process. Cadrumo declares no pydantic plugin, and a third-party plugin
would observe taxpayer models it has no business seeing. The switch is read
when pydantic first builds a model, so each process entry applies it before its
first pydantic import; this module imports nothing from pydantic.
"""

from __future__ import annotations

import os
from typing import Final

PYDANTIC_PLUGINS_VARIABLE: Final = "PYDANTIC_DISABLE_PLUGINS"
"""The environment variable pydantic reads to skip plugin discovery."""

PYDANTIC_PLUGINS_DISABLED: Final = "__all__"
"""The value that disables every plugin, which pydantic documents for this variable."""


def disable_pydantic_plugins() -> None:
    """Disable plugin discovery here and in every child process this one launches.

    An explicit value an operator already set stays, so a deliberate choice, including
    one that re-enables plugins, is never overridden. Children inherit the process
    environment: Cadrumo's own workers need the same setting, and the third-party
    programs launched from it do not use pydantic.
    """
    os.environ.setdefault(PYDANTIC_PLUGINS_VARIABLE, PYDANTIC_PLUGINS_DISABLED)


__all__ = ["PYDANTIC_PLUGINS_DISABLED", "PYDANTIC_PLUGINS_VARIABLE", "disable_pydantic_plugins"]
