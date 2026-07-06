"""Run the modelo support-matrix CLI with ``python -m dev.registry.matrix``.

See Also:
    :mod:`~dev.registry.matrix.cli`
        Typer app executed by this module.
    :func:`~dev.registry.matrix.manager.build_capability_matrix`
        Registry-authority probe behind the CLI report.
"""

from __future__ import annotations

from .cli import app

if __name__ == "__main__":
    app()
