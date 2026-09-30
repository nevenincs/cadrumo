"""The published coverage of declared form layouts.

Coverage is a number the project states rather than a property that emerges:
which revisions declare a layout and which do not (with the reason), and per
revision how many casillas sit on the form, how many are working figures and
how many are unplaced, by reason.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import FormPlacementKind

__all__ = ["RevisionCoverage", "coverage_rows", "coverage_totals"]


@dataclass(frozen=True, slots=True)
class RevisionCoverage:
    """One revision's layout coverage."""

    modelo_id: str
    revision_id: str
    casillas: int
    declared: bool
    review_state: str | None
    seed_source: str | None
    on_form: int
    working_figure: int
    unplaced: int
    unplaced_reasons: Mapping[str, int]

    def as_json(self) -> dict[str, object]:
        """Return the row as a JSON-compatible mapping."""
        return {
            "modelo": self.modelo_id,
            "revision": self.revision_id,
            "casillas": self.casillas,
            "declared": self.declared,
            "review_state": self.review_state,
            "seed_source": self.seed_source,
            "on_form": self.on_form,
            "working_figure": self.working_figure,
            "unplaced": self.unplaced,
            "unplaced_reasons": dict(sorted(self.unplaced_reasons.items())),
        }


def coverage_rows(modelos: Iterable[ModeloDefinition]) -> tuple[RevisionCoverage, ...]:
    """Return one coverage row per revision, from the layouts the revisions declare."""
    rows: list[RevisionCoverage] = []
    for modelo in sorted(modelos, key=lambda item: str(item.id)):
        for revision_id, revision in sorted(modelo.revisions.items(), key=lambda item: str(item[0])):
            layout = revision.form_layouts[0] if revision.form_layouts else None
            kinds: Counter[FormPlacementKind] = Counter()
            reasons: Counter[str] = Counter()
            if layout is not None:
                kinds.update(placement.kind for placement in layout.placements)
                reasons.update(
                    placement.unplaced_reason.value
                    for placement in layout.placements
                    if placement.unplaced_reason is not None
                )
            rows.append(
                RevisionCoverage(
                    modelo_id=str(modelo.id),
                    revision_id=str(revision_id),
                    casillas=len(revision.casillas),
                    declared=layout is not None,
                    review_state=None if layout is None else layout.review.state.value,
                    seed_source=None if layout is None else layout.seed_source.value,
                    on_form=kinds[FormPlacementKind.ON_FORM],
                    working_figure=kinds[FormPlacementKind.WORKING_FIGURE],
                    unplaced=kinds[FormPlacementKind.UNPLACED],
                    unplaced_reasons=dict(reasons),
                )
            )
    return tuple(rows)


def coverage_totals(rows: Iterable[RevisionCoverage]) -> dict[str, int]:
    """Return the corpus totals the coverage rows add up to."""
    listed = tuple(rows)
    return {
        "revisions": len(listed),
        "declared": sum(1 for row in listed if row.declared),
        "undeclared": sum(1 for row in listed if not row.declared),
        "reviewed": sum(1 for row in listed if row.review_state == "reviewed"),
        "casillas": sum(row.casillas for row in listed),
        "on_form": sum(row.on_form for row in listed),
        "working_figure": sum(row.working_figure for row in listed),
        "unplaced": sum(row.unplaced for row in listed),
    }
