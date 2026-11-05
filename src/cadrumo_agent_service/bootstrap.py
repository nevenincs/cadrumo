"""Console-script door of the hosted-agent service, before any model-building import."""

from __future__ import annotations

from cadrumo.core.pydantic_plugins import disable_pydantic_plugins


def main() -> None:
    """Apply the process switches that must precede the service's imports, then serve."""
    disable_pydantic_plugins()
    from .main import main as serve

    serve()


__all__ = ["main"]
