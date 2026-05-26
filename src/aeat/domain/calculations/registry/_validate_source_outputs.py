"""Shared source-output helpers for cross-model validation."""

from __future__ import annotations

from ._schema import ModeloRevision


def revision_output_ids(revision: ModeloRevision) -> set[str]:
    outputs = {casilla.id for casilla in revision.casillas}
    outputs.update(binding.id for binding in revision.bindings)
    outputs.update(output for binding in revision.algorithm_bindings for output in binding.outputs.values())
    return outputs
