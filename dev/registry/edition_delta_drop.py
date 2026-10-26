"""Stage, prove, and optionally publish restatement drops."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from . import edition_delta_assessment as _edition_delta_assessment
from . import edition_delta_drop_scope as _edition_delta_drop_scope
from . import edition_delta_equivalence as _edition_delta_equivalence
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_order_restoration as _edition_delta_order_restoration
from . import edition_delta_workdir as _edition_delta_workdir
from .edition_delta_drop_planning import plan_drop
from .edition_delta_drop_types import DropOutcome, DropPlan
from .edition_delta_drop_writer import _write_drop
from .edition_delta_source_publication import (
    _apply_proven_modelo,
    _assert_proof_inputs_unchanged,
    _validate_staged_modelo,
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
    families: Sequence[_edition_delta_drop_scope._DroppableFamily],
    restorations: tuple[_edition_delta_order_restoration.OrderRestoration, ...],
) -> tuple[Path, tuple[tuple[str, str], ...], DropPlan]:
    declared, reordered = _edition_delta_order_restoration._stage_declared_order(
        registry_root=registry_root,
        modelo_id=modelo_id,
        work_dir=work_dir,
        reference=reference,
        restorations=restorations,
    )
    if restorations:
        declared_modelo = declared / _edition_delta_fields._MODELOS / modelo_id
        definition = _edition_delta_workdir._load(declared, modelo_id)
        plan = plan_drop(declared_modelo, definition, families=families)
    else:
        plan = plan_drop(modelo_dir, definition, families=families)
    return declared, reordered, plan


def _write_staged_drops(
    declared: Path,
    work_dir: Path,
    modelo_id: str,
    plan: DropPlan,
    families: Sequence[_edition_delta_drop_scope._DroppableFamily],
) -> Path:
    staged = copy_registry_tree(
        declared,
        _edition_delta_workdir._scratch_path(work_dir, "dropped", "registry", "aeat"),
        modelo_id=modelo_id,
    )
    by_section = {family.section: family for family in families}
    modelo_stage = _edition_delta_workdir._scratch_path(
        work_dir, "dropped", "registry", "aeat", _edition_delta_fields._MODELOS, modelo_id
    )
    for edition in plan.editions:
        _write_drop(modelo_stage, edition, by_section)
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
    return _edition_delta_equivalence._prove_chain(
        reference_modelo_dir=declared / _edition_delta_fields._MODELOS / modelo_id,
        staged_modelo_dir=staged / _edition_delta_fields._MODELOS / modelo_id,
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
    has_source_findings = any(_edition_delta_assessment._is_source_finding(finding) for finding in report.findings)
    if not apply or has_source_findings:
        return False
    _validate_staged_modelo(staged_root=staged, modelo_id=modelo_id)
    _assert_proof_inputs_unchanged(live_root=registry_root, captured_root=reference, modelo_id=modelo_id)
    _apply_proven_modelo(
        target=modelo_dir.resolve(),
        staged=staged / _edition_delta_fields._MODELOS / modelo_id,
        original=reference / _edition_delta_fields._MODELOS / modelo_id,
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
    registry_root, work_dir = _edition_delta_workdir._resolve_work_directory(registry_root, work_dir)
    modelo_dir = registry_root / _edition_delta_fields._MODELOS / modelo_id
    if not modelo_dir.is_dir() or not _edition_delta_workdir._inside(modelo_dir, registry_root):
        raise _edition_delta_errors.MigrationRefusedError(f"{registry_root} holds no modelo {modelo_id!r}")
    families = _selected_families(sections)
    definition = _edition_delta_workdir._load(registry_root, modelo_id)
    restorations = _edition_delta_order_restoration.declared_order_restorations(modelo_dir)
    plan = plan_drop(modelo_dir, definition, families=families)
    if not plan.dropped and not restorations:
        return DropOutcome(plan=plan, staged_registry=None, report=None, applied=False, changed=False)
    reference = copy_registry_tree(
        registry_root,
        _edition_delta_workdir._scratch_path(work_dir, "reference", "registry", "aeat"),
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


def _selected_families(sections: Sequence[str] | None) -> tuple[_edition_delta_drop_scope._DroppableFamily, ...]:
    """Resolve ``--family`` names against the accepted set, refusing a held-back family by name and reason."""
    if sections is None:
        return _edition_delta_drop_scope._DROPPABLE_FAMILIES
    accepted = {family.section: family for family in _edition_delta_drop_scope._DROPPABLE_FAMILIES}
    selected: list[_edition_delta_drop_scope._DroppableFamily] = []
    for section in sections:
        if section in accepted:
            selected.append(accepted[section])
            continue
        if section in _edition_delta_drop_scope._HELD_BACK_FAMILIES:
            reason = _edition_delta_drop_scope._HELD_BACK_FAMILIES[section]
            raise _edition_delta_errors.MigrationRefusedError(
                f"family {section!r} is held back from dropping: {reason}",
            )
        held_back = ", ".join(sorted(_edition_delta_drop_scope._HELD_BACK_FAMILIES))
        raise _edition_delta_errors.MigrationRefusedError(
            f"family {section!r} is not a family this tool drops; it accepts "
            f"{', '.join(sorted(accepted))} and holds back {held_back}",
        )
    return tuple(selected)
