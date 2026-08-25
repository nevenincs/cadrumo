"""Calculation-completeness manifest validation helpers.

Checks that each supplied :class:`ModeloRevision`'s manifest covers the
derived non-internal calculation closure, and that every manifest casilla
has legal and source grounding.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CalculationCompletenessCasilla, CasillaDefinition

from ....core import CasillaId
from .casilla_membership import casillas_by_id
from .record_design_coverage import calculation_closure_casilla_ids


def _identity_label(segmento: str | None, number: str) -> str:
    """Render a casilla's ``(segmento, number)`` identity for a failure message."""
    if segmento is None:
        return f"casilla number {number!r}"
    return f"casilla number {number!r} within segmento {segmento!r}"


def _absent_manifest_failure(prefix: str, revision: ModeloRevision, *, modelo_id: str) -> str | None:
    """The failure for a calculation-bearing revision that declares no manifest.

    A revision with an empty calculation closure legitimately carries no
    manifest, so only a non-empty closure is a violation.
    """
    closure = calculation_closure_casilla_ids(revision, modelo_id)
    if not closure:
        return None
    return (
        f"{prefix}: calculation-bearing revision declares no "
        "calculation-completeness manifest; closure casilla ids: "
        f"{', '.join(sorted(closure))}"
    )


def _missing_closure_failure(
    prefix: str,
    revision: ModeloRevision,
    *,
    modelo_id: str,
    manifest_casilla_ids: frozenset[CasillaId],
    declared_by_id: Mapping[CasillaId, CasillaDefinition],
) -> str | None:
    """The failure naming non-internal closure casillas the manifest omits.

    An internal-only casilla is excluded: it is part of the calculation
    closure but never reaches an official record, so the manifest is not
    expected to file a slot for it. A closure id the revision does not
    declare at all is still reported here.
    """
    missing_closure_ids = sorted(
        casilla_id
        for casilla_id in calculation_closure_casilla_ids(revision, modelo_id)
        if casilla_id not in manifest_casilla_ids
        and ((declared := declared_by_id.get(casilla_id)) is None or not declared.internal_only)
    )
    if not missing_closure_ids:
        return None
    return (
        f"{prefix}: calculation-completeness manifest omits non-internal "
        "calculation-closure casilla ids: "
        f"{', '.join(repr(casilla_id) for casilla_id in missing_closure_ids)}"
    )


def _manifest_casilla_failures(
    prefix: str,
    manifest_casilla: CalculationCompletenessCasilla,
    declared: CasillaDefinition | None,
) -> list[str]:
    """Identity and grounding failures for one manifest casilla.

    The three checks are ordered and short-circuiting: an undeclared casilla
    cannot be identity-checked, and a casilla whose identity already diverges
    is reported for that divergence rather than additionally for grounding,
    so one defect yields one failure.
    """
    if declared is None:
        return [
            f"{prefix}: calculation-completeness manifest requires casilla.id "
            f"{manifest_casilla.casilla_id!r} but the revision does not declare it",
        ]
    if declared.internal_only:
        return [
            f"{prefix}: calculation-completeness manifest includes internal-only "
            f"casilla.id {declared.id!r}; internal calculation nodes do not identify "
            "official filing slots and cannot enter the manifest denominator",
        ]
    expected_identity = manifest_casilla.record_design_metadata()
    observed_identity = (declared.segmento, declared.number)
    if observed_identity != expected_identity:
        return [
            f"{prefix}: calculation-completeness manifest casilla.id "
            f"{manifest_casilla.casilla_id!r} metadata mismatch; manifest declares "
            f"{_identity_label(*expected_identity)} but registry casilla declares "
            f"number {declared.number!r} within segmento {declared.segmento!r}",
        ]
    identity_label = _identity_label(*observed_identity)
    failures: list[str] = []
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
    return failures


def _emit_completeness_gate_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
    *,
    modelo_id: str,
) -> None:
    """Append a failure for every calculation-completeness manifest violation."""
    manifest = revision.completeness_manifest
    if manifest is None:
        absent = _absent_manifest_failure(prefix, revision, modelo_id=modelo_id)
        if absent is not None:
            failures.append(absent)
        return
    declared_by_id = casillas_by_id(revision)
    missing_closure = _missing_closure_failure(
        prefix,
        revision,
        modelo_id=modelo_id,
        manifest_casilla_ids=frozenset(casilla.casilla_id for casilla in manifest.casillas),
        declared_by_id=declared_by_id,
    )
    if missing_closure is not None:
        failures.append(missing_closure)
    for manifest_casilla in sorted(manifest.casillas, key=lambda item: item.casilla_id):
        failures.extend(
            _manifest_casilla_failures(
                prefix,
                manifest_casilla,
                declared_by_id.get(manifest_casilla.casilla_id),
            ),
        )


emit_completeness_gate_failures = _emit_completeness_gate_failures
