"""Calculation-completeness manifest validation helpers.

Checks that every casilla named in the completeness manifest of a
:class:`ModeloRevision` is declared with legal and source grounding.
"""

from __future__ import annotations

from ._casilla_membership import casillas_by_id
from ._schema import ModeloRevision


def _emit_completeness_gate_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    """Append a failure for every calculation-completeness manifest violation."""
    manifest = revision.completeness_manifest
    if manifest is None:
        return
    declared_by_id = casillas_by_id(revision)
    for manifest_casilla in sorted(manifest.casillas, key=lambda item: item.casilla_id):
        declared = declared_by_id.get(manifest_casilla.casilla_id)
        if declared is None:
            failures.append(
                f"{prefix}: calculation-completeness manifest requires casilla.id "
                f"{manifest_casilla.casilla_id!r} but the revision does not declare it",
            )
            continue
        expected_identity = manifest_casilla.record_design_metadata()
        observed_identity = (declared.segmento, declared.number)
        if observed_identity != expected_identity:
            segmento, number = expected_identity
            expected_label = (
                f"casilla number {number!r}"
                if segmento is None
                else f"casilla number {number!r} within segmento {segmento!r}"
            )
            failures.append(
                f"{prefix}: calculation-completeness manifest casilla.id "
                f"{manifest_casilla.casilla_id!r} metadata mismatch; manifest declares "
                f"{expected_label} but registry casilla declares number {declared.number!r} "
                f"within segmento {declared.segmento!r}",
            )
            continue
        segmento, number = observed_identity
        identity_label = (
            f"casilla number {number!r}"
            if segmento is None
            else f"casilla number {number!r} within segmento {segmento!r}"
        )
        if not declared.legal_refs:
            failures.append(
                f"{prefix}: calculation-completeness manifest casilla.id {declared.id!r} ({identity_label}) "
                "is declared without legal_refs grounding",
            )
        if not declared.source_refs:
            failures.append(
                f"{prefix}: calculation-completeness manifest casilla.id {declared.id!r} ({identity_label}) "
                "is declared without source_refs grounding",
            )
