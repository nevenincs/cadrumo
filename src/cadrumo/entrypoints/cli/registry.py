"""Read-only registry verification CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.registry.diff import RegistryRevisionDiffReport, diff_registry_revisions
from ...application.registry.filed_state import verify_filed_state
from ...application.registry.tree import RegistryTreeReport, inspect_registry_tree, verify_registry_tree
from ...core.i18n._render import tr
from ...core.json_contract import strict_round_trip
from ...core.resources._boundary import bundled_path
from ._common import emit_envelope, resolve_optional_root
from ._registry_diff_payloads import RegistryDiffRevisionsResult
from ._registry_payloads import (
    RegistryInspectResult,
    RegistryVerifyFiledStateResult,
)


def _metric_line(key: str, value: object) -> str:
    line = f"{tr('cli.registry.metrics.' + key)}={value}"
    return line


def _join(values: tuple[object, ...] | list[object] | set[object]) -> str:
    return ",".join(str(value) for value in values)


def _registry_tree_metric_lines(report: RegistryTreeReport) -> tuple[str, ...]:
    """Render the shared registry-tree inventory metrics common to inspect and verify.

    ``verify`` prepends its own ``verified`` row; every other count row is
    identical across both commands, so it is one shared projection.
    """
    return (
        _metric_line("modelo_count", report.modelo_count),
        _metric_line("revision_count", report.revision_count),
        _metric_line("legal_reference_count", report.legal_reference_count),
        _metric_line("source_reference_count", report.source_reference_count),
        _metric_line("casilla_count", report.casilla_count),
        _metric_line("formula_count", report.formula_count),
        _metric_line("extraction_profile_count", report.extraction_profile_count),
        _metric_line("cross_reference_count", report.cross_reference_count),
        _metric_line("workbook_parity_ref_count", report.workbook_parity_ref_count),
        _metric_line("verification_expectation_count", report.verification_expectation_count),
        _metric_line("application_link_count", report.application_link_count),
        _metric_line("application_link_surfaces", _join(list(report.application_link_surfaces))),
        _metric_line("modelos", _join(list(report.modelos))),
    )


def inspect_registry_cmd(
    ctx: typer.Context,
    registry_root: Path | None = None,
) -> None:
    """Load the read-only registry tree and report inventory counts."""
    registry_root = resolve_optional_root(registry_root, lambda: bundled_path("registry", "aeat"))
    report = inspect_registry_tree(registry_root)
    emit_envelope(
        ctx,
        command="registry.inspect",
        result=strict_round_trip(RegistryInspectResult, report),
        lines=_registry_tree_metric_lines(report),
    )


def verify_registry_cmd(
    ctx: typer.Context,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> None:
    """Validate every registry modelo against shared legal/source catalogues."""
    registry_root = resolve_optional_root(registry_root, lambda: bundled_path("registry", "aeat"))
    resolved_source_root = resolve_optional_root(source_root, bundled_path)
    report = verify_registry_tree(registry_root, source_root=resolved_source_root)
    emit_envelope(
        ctx,
        command="registry.verify",
        result=strict_round_trip(RegistryInspectResult, report),
        lines=(
            _metric_line("verified", report.verified),
            _metric_line("verified_invariant_families", _join(list(report.verified_invariant_families))),
            _metric_line("unverified_invariant_families", _join(list(report.unverified_invariant_families))),
            *_registry_tree_metric_lines(report),
        ),
    )


def verify_filed_state_cmd(
    ctx: typer.Context,
    observation_path: Path,
    source_observation_paths: list[Path] | None = None,
    registry_root: Path | None = None,
    source_root: Path | None = None,
    required_casilla_refs: list[str] | None = None,
) -> None:
    """Verify local registry calculation output against captured filed state."""
    report = verify_filed_state(
        observation_path=observation_path,
        source_observation_paths=tuple(source_observation_paths or ()),
        registry_root=resolve_optional_root(registry_root, lambda: bundled_path("registry", "aeat")),
        source_root=resolve_optional_root(source_root, bundled_path),
        required_casilla_ids=tuple(required_casilla_refs or ()),
    )
    comparison = report.comparison
    lines = [
        _metric_line("status", comparison.status),
        _metric_line("modelo", comparison.modelo),
        _metric_line("revision", comparison.revision),
        _metric_line("compared_casilla_ids", ",".join(comparison.compared_casilla_ids)),
        _metric_line("missing_local_casilla_ids", ",".join(comparison.missing_local_casilla_ids)),
        _metric_line("missing_filed_casilla_ids", ",".join(comparison.missing_filed_casilla_ids)),
        _metric_line("drift_count", len(comparison.drifts)),
    ]
    for drift in comparison.drifts:
        lines.append(
            _metric_line(
                "drift",
                f"{drift.casilla_id}\tlocal={drift.local_value}\tfiled={drift.filed_value}\tdelta={drift.delta}",
            ),
        )
    emit_envelope(
        ctx,
        command="registry.verify_filed_state",
        result=RegistryVerifyFiledStateResult(
            observation_path=report.observation_path,
            source_observation_paths=list(report.source_observation_paths),
            comparison=report.comparison,
        ),
        lines=lines,
    )


def diff_revisions_cmd(
    ctx: typer.Context,
    modelo: str,
    from_year: int,
    to_year: int,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> None:
    """Diff the two registry revisions of one modelo that cover ``--from-year`` and ``--to-year``.

    Surfaces what changed in the AEAT filing rulebook year-to-year: added,
    removed, and renumbered casillas; changed formulas, parameters
    (rates/thresholds), and bindings; and revision-level legal reference
    deltas. Each bare filing year resolves to exactly one covering revision;
    an ambiguous or uncovered year is refused naming the modelo's declared
    revisions.
    """
    report = diff_registry_revisions(
        modelo,
        from_year=from_year,
        to_year=to_year,
        registry_root=resolve_optional_root(registry_root, lambda: bundled_path("registry", "aeat")),
        source_root=resolve_optional_root(source_root, bundled_path),
    )
    emit_envelope(
        ctx,
        command="registry.diff_revisions",
        result=strict_round_trip(RegistryDiffRevisionsResult, report),
        lines=_diff_revisions_lines(report),
    )


def _diff_revisions_lines(report: RegistryRevisionDiffReport) -> list[str]:
    lines = [
        _metric_line("modelo", report.modelo),
        _metric_line("from_revision_id", report.from_revision_id),
        _metric_line("to_revision_id", report.to_revision_id),
        _metric_line("same_revision", report.same_revision),
        _metric_line("added_casilla_count", len(report.added_casillas)),
        _metric_line("removed_casilla_count", len(report.removed_casillas)),
        _metric_line("renumbered_casilla_count", len(report.renumbered_casillas)),
        _metric_line("changed_casilla_legal_ref_count", len(report.changed_casilla_legal_refs)),
        _metric_line("added_formula_count", len(report.added_formulas)),
        _metric_line("removed_formula_count", len(report.removed_formulas)),
        _metric_line("changed_formula_count", len(report.changed_formulas)),
        _metric_line("added_parameter_count", len(report.added_parameters)),
        _metric_line("removed_parameter_count", len(report.removed_parameters)),
        _metric_line("changed_parameter_count", len(report.changed_parameters)),
        _metric_line("added_binding_count", len(report.added_bindings)),
        _metric_line("removed_binding_count", len(report.removed_bindings)),
        _metric_line("revision_legal_refs_added", ",".join(report.revision_legal_refs_added)),
        _metric_line("revision_legal_refs_removed", ",".join(report.revision_legal_refs_removed)),
    ]
    for casilla in report.added_casillas:
        lines.append("\t".join(("added_casilla", casilla.id, casilla.number, casilla.label)))
    for casilla in report.removed_casillas:
        lines.append("\t".join(("removed_casilla", casilla.id, casilla.number, casilla.label)))
    for renumbered in report.renumbered_casillas:
        lines.append(
            "\t".join(
                (
                    "renumbered_casilla",
                    renumbered.continuidad_id,
                    f"{renumbered.from_id}({renumbered.from_number})",
                    f"{renumbered.to_id}({renumbered.to_number})",
                ),
            ),
        )
    lines.extend(f"changed_casilla_legal_refs\t{casilla_id}" for casilla_id in report.changed_casilla_legal_refs)
    lines.extend(f"added_formula\t{formula_id}" for formula_id in report.added_formulas)
    lines.extend(f"removed_formula\t{formula_id}" for formula_id in report.removed_formulas)
    for formula in report.changed_formulas:
        lines.append("\t".join(("changed_formula", formula.id, formula.target_casilla_id)))
    lines.extend(f"added_parameter\t{parameter_id}" for parameter_id in report.added_parameters)
    lines.extend(f"removed_parameter\t{parameter_id}" for parameter_id in report.removed_parameters)
    for parameter in report.changed_parameters:
        lines.append("\t".join(("changed_parameter", parameter.id, parameter.data_type)))
    for binding in report.added_bindings:
        lines.append("\t".join(("added_binding", binding.id, binding.source)))
    for binding in report.removed_bindings:
        lines.append("\t".join(("removed_binding", binding.id, binding.source)))
    return lines


__all__ = [
    "diff_revisions_cmd",
    "inspect_registry_cmd",
    "verify_filed_state_cmd",
    "verify_registry_cmd",
]
