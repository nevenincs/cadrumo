"""Compare hydrated casilla order between an accepted source and a candidate.

This read-only review is deliberately narrower than source equivalence: it
compares only casilla identity order in revisions represented by both trees.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .compiler.loader import load_modelo_directory

CasillaOrderStatus = Literal["pass", "drift", "incomplete"]
_CLI_PREVIEW_LIMIT = 12
_CLI_DRIFT_LIMIT = 5


@dataclass(frozen=True, slots=True)
class RevisionCasillaOrder:
    """Order-only comparison for one revision present in both loaded trees."""

    revision_id: str
    reference_ids: tuple[str, ...]
    mapped_reference_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    retained_reference_ids: tuple[str, ...]
    retained_candidate_ids: tuple[str, ...]
    additions: tuple[str, ...]
    removals: tuple[str, ...]
    applied_renames: tuple[tuple[str, str], ...]
    order_matches: bool
    coverage_complete: bool
    coverage_note: str | None


@dataclass(frozen=True, slots=True)
class CasillaOrderReport:
    """Machine-readable order review; it makes no content or legal claim."""

    reference_modelo_id: str
    candidate_modelo_id: str
    reference_directory: str
    candidate_directory: str
    scope: str
    renames: tuple[tuple[str, str], ...]
    common_revisions: tuple[str, ...]
    missing_candidate_revisions: tuple[str, ...]
    candidate_only_revisions: tuple[str, ...]
    comparisons: tuple[RevisionCasillaOrder, ...]
    status: CasillaOrderStatus

    @property
    def passed(self) -> bool:
        """Return whether the retained order and comparison coverage both pass."""
        return self.status == "pass"


def _normalise_renames(renames: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    for pair in renames:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError(f"rename must be an (old_id, new_id) pair; got {pair!r}")
        old_id, new_id = pair
        if not isinstance(old_id, str) or not isinstance(new_id, str):
            raise ValueError(f"rename ids must be strings; got {pair!r}")
        if not old_id or not new_id or old_id.strip() != old_id or new_id.strip() != new_id:
            raise ValueError(f"rename ids must be non-empty and have no surrounding whitespace: {pair!r}")
        if old_id == new_id:
            raise ValueError(f"rename {old_id!r} -> {new_id!r} does not change an id")
        if old_id in seen_sources:
            raise ValueError(f"rename source {old_id!r} is repeated")
        if new_id in seen_targets:
            raise ValueError(f"rename target {new_id!r} is repeated; rename targets must be one-to-one")
        seen_sources.add(old_id)
        seen_targets.add(new_id)
        pairs.append((old_id, new_id))
    if seen_sources & seen_targets:
        overlap = ", ".join(sorted(seen_sources & seen_targets))
        raise ValueError(f"rename chains or cycles are ambiguous at id(s): {overlap}")
    return tuple(pairs)


def _all_casilla_ids(modelo: ModeloDefinition) -> frozenset[str]:
    return frozenset(str(casilla.id) for revision in modelo.revisions.values() for casilla in revision.casillas)


def _revision_ids(modelo: ModeloDefinition, revision_id: str) -> tuple[str, ...]:
    return tuple(str(casilla.id) for casilla in modelo.revisions[revision_id].casillas)


def _validate_renames(
    pairs: tuple[tuple[str, str], ...],
    *,
    reference_ids: frozenset[str],
    candidate_ids: frozenset[str],
) -> None:
    for old_id, new_id in pairs:
        if old_id not in reference_ids:
            raise ValueError(f"rename source {old_id!r} does not occur in the reference modelo")
        if new_id not in candidate_ids:
            raise ValueError(f"rename target {new_id!r} does not occur in the candidate modelo")


def review_casilla_order(
    reference_modelo_dir: Path,
    candidate_modelo_dir: Path,
    *,
    renames: Iterable[tuple[str, str]] = (),
) -> CasillaOrderReport:
    """Compare retained casilla order after loading each directory canonically.

    Casilla rows are compared by ID only. Changed row content is outside this
    report's scope. New and removed IDs are reported separately, and only the
    relative order of members present on both sides is judged.
    """
    reference_path = Path(reference_modelo_dir).resolve()
    candidate_path = Path(candidate_modelo_dir).resolve()
    reference = load_modelo_directory(reference_path)
    candidate = load_modelo_directory(candidate_path)
    reference_modelo_id = str(reference.id)
    candidate_modelo_id = str(candidate.id)
    if reference_modelo_id != candidate_modelo_id:
        raise ValueError(
            f"reference modelo {reference_modelo_id!r} does not match candidate modelo {candidate_modelo_id!r}"
        )

    pairs = _normalise_renames(renames)
    reference_ids = _all_casilla_ids(reference)
    candidate_ids = _all_casilla_ids(candidate)
    _validate_renames(pairs, reference_ids=reference_ids, candidate_ids=candidate_ids)

    common_revisions = tuple(sorted(set(reference.revisions) & set(candidate.revisions)))
    missing_candidate_revisions = tuple(sorted(set(reference.revisions) - set(candidate.revisions)))
    candidate_only_revisions = tuple(sorted(set(candidate.revisions) - set(reference.revisions)))
    used_renames: set[tuple[str, str]] = set()
    comparisons: list[RevisionCasillaOrder] = []

    for revision_id in common_revisions:
        old_order = _revision_ids(reference, revision_id)
        new_order = _revision_ids(candidate, revision_id)
        old_set = set(old_order)
        new_set = set(new_order)
        revision_renames: dict[str, str] = {}
        applied_pairs: list[tuple[str, str]] = []
        for old_id, new_id in pairs:
            if old_id in old_set and new_id in old_set:
                raise ValueError(f"rename {old_id!r} -> {new_id!r} collides in reference revision {revision_id!r}")
            if old_id in new_set and new_id in new_set:
                raise ValueError(f"rename {old_id!r} -> {new_id!r} is ambiguous in candidate revision {revision_id!r}")
            if old_id in old_set and old_id not in new_set and new_id in new_set:
                revision_renames[old_id] = new_id
                applied_pairs.append((old_id, new_id))
                used_renames.add((old_id, new_id))

        mapped_old_order = tuple(revision_renames.get(casilla_id, casilla_id) for casilla_id in old_order)
        if len(set(mapped_old_order)) != len(mapped_old_order):
            raise ValueError(f"rename mapping collides in revision {revision_id!r}")
        mapped_old_set = set(mapped_old_order)
        retained_old = tuple(casilla_id for casilla_id in mapped_old_order if casilla_id in new_set)
        retained_new = tuple(casilla_id for casilla_id in new_order if casilla_id in mapped_old_set)
        additions = tuple(casilla_id for casilla_id in new_order if casilla_id not in mapped_old_set)
        removals = tuple(casilla_id for casilla_id in mapped_old_order if casilla_id not in new_set)
        coverage_complete = not old_order or bool(retained_old)
        coverage_note = (
            "previously non-empty revision has no retained casillas to compare"
            if old_order and not retained_old
            else None
        )
        comparisons.append(
            RevisionCasillaOrder(
                revision_id=revision_id,
                reference_ids=old_order,
                mapped_reference_ids=mapped_old_order,
                candidate_ids=new_order,
                retained_reference_ids=retained_old,
                retained_candidate_ids=retained_new,
                additions=additions,
                removals=removals,
                applied_renames=tuple(applied_pairs),
                order_matches=retained_old == retained_new,
                coverage_complete=coverage_complete,
                coverage_note=coverage_note,
            )
        )

    unused_renames = set(pairs) - used_renames
    if unused_renames:
        values = ", ".join(f"{old!r}={new!r}" for old, new in sorted(unused_renames))
        raise ValueError(f"rename mapping does not match an old-to-new member in any common revision: {values}")

    order_drift = any(not comparison.order_matches for comparison in comparisons)
    incomplete = (
        not common_revisions
        or bool(missing_candidate_revisions)
        or bool(candidate_only_revisions)
        or any(not comparison.coverage_complete for comparison in comparisons)
        or not any(comparison.retained_reference_ids for comparison in comparisons)
    )
    status: CasillaOrderStatus = "drift" if order_drift else "incomplete" if incomplete else "pass"
    return CasillaOrderReport(
        reference_modelo_id=reference_modelo_id,
        candidate_modelo_id=candidate_modelo_id,
        reference_directory=str(reference_path),
        candidate_directory=str(candidate_path),
        scope="casilla-id-order-only",
        renames=pairs,
        common_revisions=common_revisions,
        missing_candidate_revisions=missing_candidate_revisions,
        candidate_only_revisions=candidate_only_revisions,
        comparisons=tuple(comparisons),
        status=status,
    )


def _parse_rename(value: str) -> tuple[str, str]:
    parts = value.split("=")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError("rename must be written OLD=NEW with both ids present")
    return parts[0], parts[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare retained casilla order in accepted and candidate modelo source directories."
    )
    parser.add_argument("--reference", type=Path, required=True, help="Accepted modelo source directory")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate modelo source directory")
    parser.add_argument(
        "--rename",
        action="append",
        type=_parse_rename,
        default=[],
        metavar="OLD=NEW",
        help="Explicit one-to-one casilla ID rename; may be repeated",
    )
    return parser


def render_report(report: CasillaOrderReport) -> str:
    """Render a concise stable CLI report."""

    def preview(values: tuple[str, ...]) -> str:
        shown = values[:_CLI_PREVIEW_LIMIT]
        suffix = f", ... (+{len(values) - len(shown)} more)" if len(values) > len(shown) else ""
        return f"count={len(values)} ids={list(shown)!r}{suffix}"

    def order_differences(comparison: RevisionCasillaOrder) -> tuple[int, list[str]]:
        differences: list[str] = []
        mismatch_count = 0
        paired_length = min(len(comparison.retained_reference_ids), len(comparison.retained_candidate_ids))
        for index in range(paired_length):
            reference_id = comparison.retained_reference_ids[index]
            candidate_id = comparison.retained_candidate_ids[index]
            if reference_id != candidate_id:
                mismatch_count += 1
                if len(differences) < _CLI_DRIFT_LIMIT:
                    differences.append(f"position={index} reference={reference_id!r} candidate={candidate_id!r}")
        length_delta = abs(len(comparison.retained_reference_ids) - len(comparison.retained_candidate_ids))
        mismatch_count += length_delta
        if length_delta and len(differences) < _CLI_DRIFT_LIMIT:
            index = paired_length
            reference_id = (
                comparison.retained_reference_ids[index] if index < len(comparison.retained_reference_ids) else "<end>"
            )
            candidate_id = (
                comparison.retained_candidate_ids[index] if index < len(comparison.retained_candidate_ids) else "<end>"
            )
            differences.append(f"position={index} reference={reference_id!r} candidate={candidate_id!r}")
        if mismatch_count > len(differences):
            differences.append(f"... (+{mismatch_count - len(differences)} mismatches)")
        return mismatch_count, differences

    lines = [
        f"casilla-order status={report.status} modelo={report.reference_modelo_id}",
        f"scope={report.scope}",
        f"common_revisions={','.join(report.common_revisions) or '(none)'}",
        f"reference_revisions_missing_from_candidate={','.join(report.missing_candidate_revisions) or '(none)'}",
        f"candidate_revisions_without_reference={','.join(report.candidate_only_revisions) or '(none)'}",
    ]
    for comparison in report.comparisons:
        lines.append(
            f"revision={comparison.revision_id} retained={len(comparison.retained_reference_ids)} "
            f"order_matches={comparison.order_matches} additions=({preview(comparison.additions)}) "
            f"removals=({preview(comparison.removals)}) coverage_complete={comparison.coverage_complete}"
        )
        if comparison.coverage_note is not None:
            lines.append(f"  coverage_note={comparison.coverage_note}")
        if not comparison.order_matches:
            mismatch_count, differences = order_differences(comparison)
            lines.append(f"  order_mismatches={mismatch_count} first_differences={'; '.join(differences)}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Review source directories without mutation; refuse drift or incomplete coverage."""
    args = _parser().parse_args(argv)
    try:
        report = review_casilla_order(args.reference, args.candidate, renames=args.rename)
    except (ValueError, RegistryError) as error:
        print(f"casilla-order refused: {error}", file=sys.stderr)
        return 2
    print(render_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
