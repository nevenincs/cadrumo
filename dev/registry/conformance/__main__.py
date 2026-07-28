"""Run the registry conformance governance CLI with ``python -m dev.registry.conformance``.

See Also:
    :mod:`~dev.registry.conformance.cli`
        Typer app executed by this module.
    :func:`~dev.registry.conformance.manager.load_conformance_report`
        Composed report behind every verb.
"""

from __future__ import annotations

from .cli import app

if __name__ == "__main__":
    app()
