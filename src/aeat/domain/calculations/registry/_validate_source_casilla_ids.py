"""Shared source-casilla-id helpers for cross-model validation.

Returns the canonical casilla ids a :class:`ModeloRevision` can expose to
cross-model relation validators.
"""

from __future__ import annotations

from ._casilla_membership import declared_casilla_ids
from ._ids import CasillaId
from ._schema import ModeloRevision


def revision_output_ids(revision: ModeloRevision) -> set[CasillaId]:
    outputs = set(declared_casilla_ids(revision))
    outputs.update(output for binding in revision.algorithm_bindings for output in binding.output_casilla_ids.values())
    return outputs
