"""Render restatement-drop plans and proof outcomes for human and CLI review."""

from __future__ import annotations

from . import edition_delta_order_restoration as _edition_delta_order_restoration
from .edition_delta_drop_types import DropOutcome

__all__ = ("render_drop_outcome",)


def render_drop_outcome(outcome: DropOutcome) -> str:
    """Return one greppable line per edition family, one per gate finding, and a closing summary."""
    lines: list[str] = []
    for edition in outcome.plan.editions:
        if edition.skipped is not None:
            lines.append(
                f"edition modelo={outcome.plan.modelo_id} revision={edition.revision_id} skipped={edition.skipped}"
            )
            continue
        for family in edition.families:
            lines.append(
                f"edition modelo={outcome.plan.modelo_id} revision={edition.revision_id} "
                f"predecessor={edition.predecessor} family={family.section} stated={family.stated} "
                f"dropped={len(family.dropped)} kept_new={len(family.kept_new)} "
                f"kept_differs={len(family.kept_differs)} kept_pinned={len(family.kept_pinned)} "
                f"kept_no_identity={family.kept_no_identity}"
            )
    lines.extend(
        _edition_delta_order_restoration._order_lines(
            outcome.plan.modelo_id, outcome.order_restorations, outcome.reordered_families
        )
    )
    for finding in outcome.report.findings if outcome.report is not None else ():
        lines.append(f"finding kind={finding.kind} {finding}")
    lines.append(
        f"summary modelo={outcome.plan.modelo_id} dropped={outcome.plan.dropped} "
        f"changed={outcome.changed} applied={outcome.applied} "
        f"findings={len(outcome.report.findings) if outcome.report is not None else 0} "
        f"source_status={outcome.source_status} "
        f"publication_readiness_status={outcome.publication_readiness_status} "
        f"publication_execution_status={outcome.publication_execution_status}"
    )
    return "\n".join(lines) + "\n"
