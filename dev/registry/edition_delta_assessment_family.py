"""Measure authored payload and restatement for one registry family."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.keyed_families import FamilyInheritanceMode

from . import edition_delta_assessment_family_baseline as family_baseline
from . import edition_delta_assessment_family_counts as family_counts
from . import edition_delta_assessment_family_members as family_members
from . import edition_delta_assessment_family_overrides as family_overrides
from . import edition_delta_source as source
from .edition_delta_assessment_state import FamilyBaseline, FamilyRun


def assess_family(family: FamilyRun) -> FamilyRun:
    """Measure one family's authored payload and, where it inherits, its restatement against the baseline."""
    baseline = family_baseline._baseline(family)
    family.row["physical_bytes"] = family_counts._family_bytes(family)
    authored = source._members(family.raw, family.spec.section, singleton=family.spec.singleton)
    if authored is None:
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "authored_shape_unsupported"}
        )
        return family
    family_counts._count_authored_payload(family, authored)
    if family.spec.inheritance is FamilyInheritanceMode.PER_EDITION:
        return family
    if baseline.candidate_id is not None:
        _compare_with_baseline(family, baseline, authored)
    return family


def _compare_with_baseline(
    family: FamilyRun,
    baseline: FamilyBaseline,
    authored: tuple[Mapping[str, object], ...],
) -> None:
    predecessor = family.run.definition.revisions.get(baseline.candidate_id or "")
    if predecessor is None:
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "baseline_missing"}
        )
        return
    inherited_members = family_baseline._typed_family_members(family, predecessor)
    if inherited_members is None:
        family.include_row = False
        return
    current_members = family_baseline._current_family_members(family)
    inherited_by_id = family_baseline._family_index(inherited_members, family)
    current_by_id = family_baseline._family_index(current_members, family) if current_members is not None else {}
    authored_ids = family_members._compare_authored_members(family, baseline, authored, inherited_by_id, current_by_id)
    family_members._count_inherited_payload(family, current_members, inherited_by_id, authored_ids)
    family_overrides._compare_family_override_operations(family, inherited_by_id, current_by_id)
    _record_missing_support(family, authored)
    if family.spec.section == "casillas" and baseline.baseline_id is not None:
        family_overrides._compare_casilla_overrides(family, predecessor)


def _record_missing_support(family: FamilyRun, authored: tuple[Mapping[str, object], ...]) -> None:
    if authored and not family.spec.inherited:
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "delta_support_missing"}
        )


__all__ = ("assess_family",)
