"""Entry point for the sweep cadence CLI: ``python -m dev.docs.terminology.sweep``.

Mirrors the ``apidocs`` / ``preprocess`` developer-CLI precedents: a thin module
that exposes the sweep Typer app so the cadence re-run verb is invokable from the
command line.
"""

from __future__ import annotations

from ._sweep_cli import app

if __name__ == "__main__":
    app()
