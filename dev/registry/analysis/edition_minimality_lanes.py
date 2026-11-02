"""Standing minimality observations the registry status report turns into lanes.

Two independent measures of the authored source: the casilla delta screen over
the validated authority, and the all-family assessment over each modelo's
authored tree. Each returns the reasons it must fail a gate; an empty tuple
means it held. A measure that examined nothing returns a reason too, because
zero findings over zero examined members is not the same as minimal.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..edition_delta_assessment import assess_migration_state
from .delta_minimality import check_authority, definition_findings, definitions_census

__all__ = ("definitions_minimality_reasons", "delta_minimality_reasons", "edition_assessment_reasons")


def delta_minimality_reasons(authority: ValidatedRegistryAuthority | None) -> tuple[str, ...]:
    """Return why the casilla delta screen fails; an authority that did not validate was not measured."""
    if authority is None:
        return ("the registry did not validate, so casilla delta minimality was not measured",)
    return definitions_minimality_reasons({str(modelo.id): modelo for modelo in authority.modelos})


def definitions_minimality_reasons(definitions: Mapping[str, ModeloDefinition]) -> tuple[str, ...]:
    """Return why the casilla delta screen fails over the given modelo definitions, keyed by modelo id."""
    findings = tuple(
        item
        for modelo_id in sorted(definitions)
        for item in definition_findings(definitions[modelo_id], modelo_id=modelo_id)
    )
    return check_authority(findings, definitions_census(definitions))


def edition_assessment_reasons(registry_root: Path) -> tuple[str, ...]:
    """Return why the all-family assessment fails over every modelo tree under the registry root.

    A modelo fails when it carries an override equal to its hydrated baseline,
    any other repeated payload, work the assessor could not judge, or inputs that
    moved while it read them.
    """
    modelo_dirs = sorted(path for path in (registry_root / "modelos").iterdir() if path.is_dir())
    if not modelo_dirs:
        return ("no modelo tree was assessed, so edition delta minimality was not measured",)
    reasons: list[str] = []
    for modelo_dir in modelo_dirs:
        assessment = assess_migration_state(modelo_dir)
        if assessment.minimal:
            continue
        reasons.append(
            f"modelo {modelo_dir.name}: {len(assessment.unresolved_duplication)} repeated payload finding(s), "
            f"{len(assessment.blocked_work)} unassessed item(s), inputs stable={assessment.inputs_stable}"
        )
    return tuple(reasons)
