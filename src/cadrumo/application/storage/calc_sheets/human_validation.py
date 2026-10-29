"""Human workbook constraint messages and technical-text checks."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_references import LegalReference, SourceReference
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .errors import CalcSheetsEngineError
from .records import (
    SheetCellConstraint,
    SheetExportMetadata,
    SheetExportPlan,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
)


def _constraint_bounds(constraint: SheetCellConstraint) -> str:
    lower, upper = constraint.resolved_bounds()
    bounds = " y ".join(
        part
        for part in (f"mínimo {lower}" if lower is not None else "", f"máximo {upper}" if upper is not None else "")
        if part
    )
    if constraint.allowed_values is not None:
        choices = "valores admitidos: " + ", ".join(constraint.allowed_values)
        bounds = f"{bounds}; {choices}" if bounds else choices
    for length, description in (
        (constraint.min_length, "longitud mínima"),
        (constraint.max_length, "longitud máxima"),
    ):
        if length is not None:
            limit = f"{description}: {length} caracteres"
            bounds = f"{bounds}; {limit}" if bounds else limit
    return bounds


def human_constraints(
    constraints_in: tuple[SheetCellConstraint, ...],
    casillas: dict[str, CasillaDefinition],
    excluded: frozenset[str],
    legal_text: Callable[[tuple[str, ...]], str],
) -> list[SheetCellConstraint]:
    """Replace constraint messages with authored human descriptions."""
    constraints: list[SheetCellConstraint] = []
    for constraint in constraints_in:
        if constraint.casilla_id in excluded:
            continue
        bounds = _constraint_bounds(constraint)
        constraints.append(
            constraint.model_copy(
                update={
                    "presentation_message": (
                        f"{casillas[constraint.casilla_id].label}: {bounds or 'sin límite numérico'}. "
                        f"{legal_text(constraint.legal_refs)}"
                    )
                }
            )
        )
    return constraints


def validate_human_text[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M], revision: ModeloRevision, values: list[SheetValueCell], identity_digest: str
) -> None:
    """Refuse technical identifiers in human-visible labels or notes.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    internal_tokens = (
        {b.id for b in revision.bindings} | {p.id for p in revision.parameters} | {f.id for f in revision.formulas}
    )
    for cell in values:
        for text in (cell.value if cell.role in ("label", "metadata") else None, cell.note):
            if isinstance(text, str) and _technical_text(text, internal_tokens, identity_digest, plan.metadata):
                raise CalcSheetsEngineError(
                    "human workbook contains unresolved technical presentation text",
                    context={"cell": cell.address.qualified()},
                )


def _technical_text(
    text: str,
    internal_tokens: set[str],
    identity_digest: str,
    metadata: SheetExportMetadata | SheetReviewMetadata | SheetTemplatePreviewMetadata,
) -> bool:
    return bool(
        re.search(r"\b[0-9a-f]{64}\b|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", text, re.I)
        or any(token in text for token in internal_tokens)
        or identity_digest in text
        or (
            isinstance(metadata, (SheetExportMetadata, SheetTemplatePreviewMetadata))
            and metadata.engine_version == text
        )
    )


def require_label(labels: dict[str, str], key: str) -> str:
    """Return an authored label or refuse its absence."""
    if key not in labels:
        raise CalcSheetsEngineError(
            "human workbook requires an authored label for a calculation input",
            context={"reference": key},
        )
    return labels[key]


def legal_reference_text(legal_catalogue: Mapping[str, LegalReference], refs: tuple[str, ...]) -> str:
    """Render the declared legal references."""
    parts: list[str] = []
    for key in refs:
        reference = legal_catalogue.get(key)
        if reference is None:
            raise CalcSheetsEngineError("human workbook legal reference is missing")
        parts.append(
            reference.document_id
            + (f", artículo {reference.article}" if (reference.article is not None and reference.article) else "")
            + (f", {reference.section}" if (reference.section is not None and reference.section) else "")
            + f" — {reference.permalink}"
        )
    return "\n".join(dict.fromkeys(parts))


def source_reference_text(source_catalogue: Mapping[str, SourceReference], refs: tuple[str, ...]) -> str:
    """Render the declared official source URLs."""
    parts: list[str] = []
    for key in refs:
        source = source_catalogue.get(key)
        if source is None:
            raise CalcSheetsEngineError("human workbook official source is missing")
        parts.append(source.source_url)
    return "\n".join(dict.fromkeys(parts))
