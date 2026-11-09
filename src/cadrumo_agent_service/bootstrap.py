"""Console-script door of the hosted-agent service, before any model-building import."""

from __future__ import annotations

import sys

from cadrumo.core.pydantic_plugins import disable_pydantic_plugins


def main() -> None:
    """Apply the process switches that must precede the service's imports, then serve or sign in by hand.

    ``provider-login`` is the operator's console sign-in; every other command line is the service's own.
    """
    disable_pydantic_plugins()
    if sys.argv[1:2] == ["provider-login"]:
        from .adapters.provider_login import main as provider_login

        raise SystemExit(provider_login(sys.argv[2:]))
    from .main import main as serve

    serve()


__all__ = ["main"]
