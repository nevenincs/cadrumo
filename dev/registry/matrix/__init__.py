"""Per-modelo support/capability matrix report for the AEAT registry.

Answers "what does modelo X actually support" for every modelo the registry
can load: whether it has a registry revision at all, whether that revision is
calc-grade (a non-empty calculation closure), whether it declares a
calculation-completeness manifest, whether it registers a fichero-BOE and/or
xml_dictionary export layout, and whether it registers an extraction profile
(PDF/justificante parsing back into casilla values).

Run via ``python -m dev.registry.matrix`` (add ``--json`` for a
machine-readable payload).

Major declarations:

* :class:`~dev.registry.matrix.manager.ModeloCapabilityRow` — one modelo's
  probed capability row.
* :func:`~dev.registry.matrix.manager.build_capability_matrix` — probes the
  bundled registry authority and returns every row.
* :func:`~dev.registry.matrix.manager.render_matrix_table` — renders the
  matrix as a human-readable fixed-width table.

See Also:
    :mod:`~dev.registry.matrix.cli`
        Typer CLI surface for printing the matrix as text or JSON.
    :mod:`~dev.registry.matrix.manager`
        Registry-authority probe and fixed-width renderer.
    :func:`~application.modelo.registry_support_matrix`
        Application-facing support-matrix facade used by the operator CLI.
    :class:`~domain.calculations.registry.ModeloEntry`
        Domain DTO used by the production registry query surface.
"""

from __future__ import annotations

from .manager import (
    ModeloCapabilityRow,
    build_capability_matrix,
    render_matrix_table,
)

__all__ = [
    "ModeloCapabilityRow",
    "build_capability_matrix",
    "render_matrix_table",
]
