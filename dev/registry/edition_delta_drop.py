"""Stage, prove, and optionally publish restatement drops."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from . import (
    edition_delta_assessment,
    edition_delta_drop_scope,
    edition_delta_equivalence,
    edition_delta_errors,
    edition_delta_fields,
    edition_delta_order_restoration,
    edition_delta_workdir,
)
from .edition_delta_drop_planning import plan_drop
from .edition_delta_drop_types import DropOutcome, DropPlan
from .edition_delta_drop_writer import write_drop
from .edition_delta_source_publication import (
    apply_proven_modelo,
    assert_proof_inputs_unchanged,
    validate_staged_modelo,
)
from .edition_round_trip import EditionExportScenario, RoundTripReport, copy_registry_tree, edition_round_trip_report

__all__ = ("drop_restatement",)


def _plan_declared_order_tree(
    registry_root: Path,
    modelo_id: str,
    work_dir: Path,
    reference: Path,
    modelo_dir: Path,
    definition: ModeloDefinition,
    families: Sequence[edition_delta_drop_scope.DroppableFamily],
    restorations: tuple[edition_delta_order_restoration.OrderRestoration, ...],
) -> tuple[Path, tuple[tuple[str, str], ...], DropPlan]:
    declared, reordered = edition_delta_order_restoration.stage_declared_order(
        registry_root=registry_root,
        modelo_id=modelo_id,
        work_dir=work_dir,
        reference=reference,
        restorations=restorations,
    )
    if restorations:
        declared_modelo = declared / edition_delta_fields.MODELOS / modelo_id
        definition = edition_delta_workdir.load(declared, modelo_id)
        plan = plan_drop(declared_modelo, definition, families=families)
    else:
        plan = plan_drop(modelo_dir, definition, families=families)
    return declared, reordered, plan


def _write_staged_drops(
    declared: Path,
    work_dir: Path,
    modelo_id: str,
    plan: DropPlan,
    families: Sequence[edition_delta_drop_scope.DroppableFamily],
) -> Path:
    staged = copy_registry_tree(
        declared,
        edition_delta_workdir.scratch_path(work_dir, "dropped", "registry", "aeat"),
        modelo_id=modelo_id,
    )
    by_section = {family.section: family for family in families}
    modelo_stage = edition_delta_workdir.scratch_path(
        work_dir, "dropped", "registry", "aeat", edition_delta_fields.MODELOS, modelo_id
    )
    for edition in plan.editions:
        write_drop(modelo_stage, edition, by_section)
    return staged


def _prove_staged_drops(
    declared: Path,
    staged: Path,
    modelo_id: str,
    plan: DropPlan,
    export_scenarios: Mapping[str, EditionExportScenario] | None,
) -> RoundTripReport:
    report = edition_round_trip_report(
        live_registry_root=staged,
        reference_registry_root=declared,
        modelo_id=modelo_id,
        export_scenarios=export_scenarios or {},
    )
    return edition_delta_equivalence.prove_chain(
        reference_modelo_dir=declared / edition_delta_fields.MODELOS / modelo_id,
        staged_modelo_dir=staged / edition_delta_fields.MODELOS / modelo_id,
        revision_ids=tuple(edition.revision_id for edition in plan.editions),
        report=report,
    )


def _publish_clean_drop(
    apply: bool,
    report: RoundTripReport,
    registry_root: Path,
    modelo_dir: Path,
    staged: Path,
    reference: Path,
    modelo_id: str,
) -> bool:
    has_source_findings = any(edition_delta_assessment.is_source_finding(finding) for finding in report.findings)
    if not apply or has_source_findings:
        return False
    validate_staged_modelo(staged_root=staged, modelo_id=modelo_id)
    assert_proof_inputs_unchanged(live_root=registry_root, captured_root=reference, modelo_id=modelo_id)
    apply_proven_modelo(
        target=modelo_dir.resolve(),
        staged=staged / edition_delta_fields.MODELOS / modelo_id,
        original=reference / edition_delta_fields.MODELOS / modelo_id,
    )
    return True


def drop_restatement(
    *,
    registry_root: Path,
    modelo_id: str,
    work_dir: Path,
    sections: Sequence[str] | None = None,
    export_scenarios: Mapping[str, EditionExportScenario] | None = None,
    apply: bool = False,
) -> DropOutcome:
    """Plan, stage and prove one modelo's restatement drop; publish it only when the gate reports nothing.

    The proof is the chain proof, unchanged and unweakened. A dropped member is
    a member the edition materialises identically without stating it, so a
    correct drop leaves every edition's member identity, member order and
    materialised bytes exactly as they were. That is why the existing guard is
    the right authority for this operation rather than an obstacle to it: it
    passes precisely when the drop was a restatement, and refuses the moment it
    was not.

    Raises:
        MigrationRefusedError: When a family is not one the drop accepts, or the
            staged tree does not materialise identically to the tree it was
            planned from.
    """
    registry_root, work_dir = edition_delta_workdir.resolve_work_directory(registry_root, work_dir)
    modelo_dir = registry_root / edition_delta_fields.MODELOS / modelo_id
    if not modelo_dir.is_dir() or not edition_delta_workdir.inside(modelo_dir, registry_root):
        raise edition_delta_errors.MigrationRefusedError(f"{registry_root} holds no modelo {modelo_id!r}")
    families = _selected_families(sections)
    definition = edition_delta_workdir.load(registry_root, modelo_id)
    restorations = edition_delta_order_restoration.declared_order_restorations(modelo_dir)
    plan = plan_drop(modelo_dir, definition, families=families)
    if not plan.dropped and not restorations:
        return DropOutcome(plan=plan, staged_registry=None, report=None, applied=False, changed=False)
    reference = copy_registry_tree(
        registry_root,
        edition_delta_workdir.scratch_path(work_dir, "reference", "registry", "aeat"),
        modelo_id=modelo_id,
    )
    declared, reordered, plan = _plan_declared_order_tree(
        registry_root, modelo_id, work_dir, reference, modelo_dir, definition, families, restorations
    )
    staged = _write_staged_drops(declared, work_dir, modelo_id, plan, families)
    report = _prove_staged_drops(declared, staged, modelo_id, plan, export_scenarios)
    applied = _publish_clean_drop(apply, report, registry_root, modelo_dir, staged, reference, modelo_id)
    return DropOutcome(
        plan=plan,
        staged_registry=staged,
        report=report,
        applied=applied,
        changed=True,
        order_restorations=restorations,
        reordered_families=reordered,
    )


def _selected_families(sections: Sequence[str] | None) -> tuple[edition_delta_drop_scope.DroppableFamily, ...]:
    """Resolve ``--family`` names against the accepted set, refusing a held-back family by name and reason."""
    if sections is None:
        return edition_delta_drop_scope.DROPPABLE_FAMILIES
    accepted = {family.section: family for family in edition_delta_drop_scope.DROPPABLE_FAMILIES}
    selected: list[edition_delta_drop_scope.DroppableFamily] = []
    for section in sections:
        if section in accepted:
            selected.append(accepted[section])
            continue
        if section in edition_delta_drop_scope.HELD_BACK_FAMILIES:
            reason = edition_delta_drop_scope.HELD_BACK_FAMILIES[section]
            raise edition_delta_errors.MigrationRefusedError(
                f"family {section!r} is held back from dropping: {reason}",
            )
        held_back = ", ".join(sorted(edition_delta_drop_scope.HELD_BACK_FAMILIES))
        raise edition_delta_errors.MigrationRefusedError(
            f"family {section!r} is not a family this tool drops; it accepts "
            f"{', '.join(sorted(accepted))} and holds back {held_back}",
        )
    return tuple(selected)
