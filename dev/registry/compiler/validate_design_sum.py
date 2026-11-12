"""Ground a formula's source citations, admitting layout authority only for a printed design sum.

Every formula needs official-source-guidance citations, with one exception. A formula
may be grounded by layout-authority citations when it restates sums the official
design itself prints. That holds when all of the following are true:

- the formula decodes as a selected design sum (:func:`.design_sum.decode_selected_sum`);
- each layout citation quotes exactly one whole row of the cited dictionary, so it
  names the dictionary edition, the row and, through that one line, its position;
- each term restates exactly one cited row, and each cited row exactly one term.

A term restates a row when every box it adds is named by the row with the printed sign;
every box it guards is named by the row; and every named box the edition declares as a
number is either added or guarded. A box behind an unreadable sign can only be guarded.
Guards refuse a value and add no arithmetic, so the formula computes nothing the rows do
not print. The check reads the formula's structure; it keeps no list of formulas.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.schema import FormulaDefinition
from cadrumo.domain.calculations.registry.schema_base import SourceCitation

from .design_sum import (
    DesignSumError,
    DictionaryRow,
    SelectedTerm,
    decode_selected_sum,
    parse_dictionary_row,
    printed_signs,
)
from .validate_evidence import EvidenceValidator

__all__ = ["GUIDANCE_TIER", "LAYOUT_TIER", "formula_citation_failures"]

GUIDANCE_TIER: Final = "official_source_guidance"
LAYOUT_TIER: Final = "layout_authority"


@dataclass(frozen=True, slots=True)
class _CitedRow:
    source_ref: str
    row: DictionaryRow
    signs: dict[str, int]


def _cited_row(citation: SourceCitation, evidence: EvidenceValidator) -> _CitedRow | None:
    """The one dictionary row a layout citation quotes; ``None`` when no evidence root is bound."""
    if len(citation.required_text) != 1:
        raise DesignSumError(f"layout citation {citation.source_ref!r} must quote exactly one dictionary row")
    lines = evidence.dictionary_lines(citation.source_ref)
    if lines is None:
        return None
    quote = citation.required_text[0]
    found = [number for number, text in enumerate(lines, start=1) if text.rstrip() == quote]
    if len(found) != 1:
        raise DesignSumError(f"layout citation {citation.source_ref!r} quotes {len(found)} whole rows, not one")
    row = parse_dictionary_row(quote, found[0])
    if row is None:
        raise DesignSumError(f"layout citation {citation.source_ref!r} line {found[0]} maps no box")
    return _CitedRow(citation.source_ref, row, printed_signs(row))


def _restates(term: SelectedTerm, cited: _CitedRow, numeric: Collection[str]) -> bool:
    signs = cited.signs
    used = {operand.box for operand in term.operands} | set(term.guards)
    return (
        used <= signs.keys()
        and all(signs[operand.box] == operand.sign for operand in term.operands)
        and {box for box in signs if box in numeric} <= used
    )


def _pairing_problems(terms: Sequence[SelectedTerm], rows: Sequence[_CitedRow], numeric: Collection[str]) -> list[str]:
    problems = [
        f"term {term.selector!r} restates {count} cited rows, not one"
        for term in terms
        if (count := sum(_restates(term, cited, numeric) for cited in rows)) != 1
    ]
    return problems + [
        f"cited row {cited.source_ref}:{cited.row.line} {cited.row.field} is restated by {count} terms, not one"
        for cited in rows
        if (count := sum(_restates(term, cited, numeric) for term in terms)) != 1
    ]


def _design_sum_problems(
    formula: FormulaDefinition,
    citations: Sequence[SourceCitation],
    numeric: Collection[str],
    evidence: EvidenceValidator,
) -> list[str]:
    try:
        terms = decode_selected_sum(formula.expression)
        rows = [_cited_row(citation, evidence) for citation in citations]
    except (DesignSumError, OSError) as exc:
        return [f"cites layout authority but does not restate a printed design sum: {exc}"]
    read = [cited for cited in rows if cited is not None]
    if len(read) != len(rows):
        return []
    return _pairing_problems(terms, read, numeric)


def formula_citation_failures(
    scope: str,
    formula: FormulaDefinition,
    *,
    numeric_casillas: Collection[str],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return the source-tier and citation failures of one formula.

    ``numeric_casillas`` are the ids of the edition's casillas that hold an amount.
    """
    owner = f"formula {formula.id}"
    layout = tuple(
        citation for citation in formula.source_citations if evidence.source_tier(citation.source_ref) == LAYOUT_TIER
    )
    if not layout:
        return [
            *evidence.require_source_tier(scope, owner, formula.source_refs, GUIDANCE_TIER),
            *evidence.validate_source_citations(
                scope, owner, formula.source_refs, formula.source_citations, GUIDANCE_TIER
            ),
        ]
    problems = _design_sum_problems(formula, layout, numeric_casillas, evidence)
    if problems:
        return [f"{scope}: {owner} {problem}" for problem in problems]
    guidance = tuple(citation for citation in formula.source_citations if citation not in layout)
    failures = evidence.require_any_source_tier(scope, owner, formula.source_refs, (GUIDANCE_TIER, LAYOUT_TIER))
    failures += evidence.validate_source_citations(scope, owner, formula.source_refs, layout, LAYOUT_TIER)
    if guidance:
        failures += evidence.validate_source_citations(scope, owner, formula.source_refs, guidance, GUIDANCE_TIER)
    return failures
