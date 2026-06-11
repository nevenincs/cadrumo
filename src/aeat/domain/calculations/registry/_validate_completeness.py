"""Calculation-completeness manifest validation helpers.

Checks that every casilla named in the completeness manifest of a
:class:`ModeloRevision` is declared with legal and source grounding.
"""

from __future__ import annotations

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
    declared_by_identity = {(casilla.segmento, casilla.number): casilla for casilla in revision.casillas}
    for manifest_casilla in sorted(manifest.casillas, key=lambda item: (item.segmento or "", item.number)):
        identity = manifest_casilla.identity()
        segmento, number = identity
        declared = declared_by_identity.get(identity)
        if declared is None:
            if segmento is None:
                failures.append(
                    f"{prefix}: calculation-completeness manifest requires casilla number "
                    f"{number!r} but the revision does not declare it",
                )
            else:
                failures.append(
                    f"{prefix}: calculation-completeness manifest requires casilla number "
                    f"{number!r} within segmento {segmento!r} but the revision does not "
                    "declare it at that identity",
                )
            continue
        identity_label = (
            f"casilla number {number!r}"
            if segmento is None
            else f"casilla number {number!r} within segmento {segmento!r}"
        )
        if not declared.legal_refs:
            failures.append(
                f"{prefix}: calculation-completeness manifest {identity_label} "
                "is declared without legal_refs grounding",
            )
        if not declared.source_refs:
            failures.append(
                f"{prefix}: calculation-completeness manifest {identity_label} "
                "is declared without source_refs grounding",
            )
