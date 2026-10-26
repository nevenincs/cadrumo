"""Aggregate family and scalar measurements for one authored revision."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from cadrumo.domain.calculations.registry.keyed_families import CANONICAL_FAMILY_SPECS
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from . import edition_delta_payload as payload
from .edition_delta_assessment_family import assess_family
from .edition_delta_assessment_state import AssessmentRun, FamilyRun


def assess_revision(
    run: AssessmentRun,
    revision: ModeloRevision,
    raw: Mapping[str, object],
    previous: str | None,
) -> None:
    """Measure every canonical family and the scalar fields of one revision into the run."""
    revision_id = str(revision.id)
    _assess_families(run, revision, raw, revision_id, previous)
    _assess_scalars(run, raw, revision_id)


def _assess_families(
    run: AssessmentRun,
    revision: ModeloRevision,
    raw: Mapping[str, object],
    revision_id: str,
    previous: str | None,
) -> None:
    for spec in CANONICAL_FAMILY_SPECS:
        family = assess_family(FamilyRun(run, revision, revision_id, raw, previous, spec))
        run.blocked.extend(family.blocked)
        run.unresolved.extend(family.unresolved)
        if family.include_row:
            run.rows.append({"revision": revision_id, "family": spec.section, **dict(family.row)})
            run.totals.update(family.row)


def _assess_scalars(run: AssessmentRun, raw: Mapping[str, object], revision_id: str) -> None:
    scalar_row = _scalar_fields(raw, revision_id, run.blocked)
    family_bytes = _family_byte_total(run, revision_id)
    revision_bytes = _revision_byte_total(run, revision_id)
    run.rows.append(
        {
            "revision": revision_id,
            "family": "$scalars",
            "physical_bytes": revision_bytes - family_bytes,
            **dict(scalar_row),
        }
    )
    run.totals.update(scalar_row)


def _scalar_fields(
    raw: Mapping[str, object],
    revision_id: str,
    blocked: list[Mapping[str, object]],
) -> Counter[str]:
    known = {spec.section for spec in CANONICAL_FAMILY_SPECS}
    scalar_row = Counter[str]()
    for key, value in raw.items():
        if _skip_scalar_key(key, known):
            continue
        if key not in ModeloRevision.model_fields:
            blocked.append({"revision": revision_id, "family": key, "reason": "scope_field_unsupported"})
            continue
        if key in {"cleared_families", "family_overrides", "family_removals", "family_positions"}:
            continue
        payload_count, overhead = payload._field_count({key: value}, structural=key in payload._STRUCTURAL_FIELDS)
        scalar_row["authored_payload_fields"] += payload_count
        scalar_row["structural_overhead"] += overhead
    return scalar_row


def _skip_scalar_key(key: object, known: set[str]) -> bool:
    return key in known or key in {"casilla_overrides", "casilla_removals", "casilla_positions"}


def _family_byte_total(run: AssessmentRun, revision_id: str) -> int:
    return sum(
        value
        for row in run.rows
        if row.get("revision") == revision_id and row.get("family") != "$scalars"
        if isinstance(value := row.get("physical_bytes", 0), int)
    )


def _revision_byte_total(run: AssessmentRun, revision_id: str) -> int:
    revision_dir = run.modelo_dir / "revisions" / revision_id
    return sum(path.stat().st_size for path in revision_dir.rglob("*") if path.is_file())


__all__ = ("assess_revision",)
