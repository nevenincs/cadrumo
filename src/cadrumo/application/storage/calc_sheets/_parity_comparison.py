"""Pure, exact per-casilla comparison of caller-supplied values.

The historical surface names ``local``, ``sheets`` and ``aeat`` remain part
of the report shape. These functions acquire no values, perform no network
operations and persist nothing. They remain usable by synthetic acceptance
and historical report tooling after retirement of the remote parity workflow.

Comparison is exact: filing-reconciliation tolerances do not govern this
axis. Callers must resolve any required numeric scale before comparison.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.schema_input_kind import InputKind
from .casilla_parity import CasillaParity

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ....domain.calculations.registry.schema_surfaces import CasillaDefinition


def _build_casilla_parity_row(
    casilla: CasillaDefinition,
    *,
    local: Decimal | None,
    sheets_v: Decimal | None,
    aeat_v: Decimal | None,
) -> CasillaParity:
    """Build one ``CasillaParity`` row with the three pairwise-equality booleans pre-resolved."""
    sheets_vs_local = sheets_v == local if sheets_v is not None and local is not None else None
    local_vs_aeat = local == aeat_v if aeat_v is not None and local is not None else None
    sheets_vs_aeat = sheets_v == aeat_v if aeat_v is not None and sheets_v is not None else None
    return CasillaParity(
        casilla_id=casilla.id,
        display_number=casilla.number,
        label=casilla.label,
        local=local,
        sheets=sheets_v,
        aeat=aeat_v,
        sheets_vs_local=sheets_vs_local,
        local_vs_aeat=local_vs_aeat,
        sheets_vs_aeat=sheets_vs_aeat,
    )


def _is_parity_divergent(
    row: CasillaParity,
    *,
    sheets_v: Decimal | None,
    local: Decimal | None,
    inputs_by_id: Mapping[CasillaId, Decimal],
) -> bool:
    """A parity row is divergent if any pairwise comparison failed, or Sheets failed to compute.

    The two divergence rules: (a) any pairwise comparison evaluated to
    False; (b) the Sheets cell is blank for a non-input casilla while
    the local engine produced a value (a Sheets formula failure the
    operator must investigate).
    """
    if sheets_v is None and local is not None and row.casilla_id not in inputs_by_id:
        return True
    return False in (row.sheets_vs_local, row.local_vs_aeat, row.sheets_vs_aeat)


def collect_parity_rows(
    *,
    casillas: Sequence[CasillaDefinition],
    local_values: Mapping[CasillaId, Decimal],
    sheets_values: Mapping[CasillaId, Decimal],
    aeat_values: Mapping[CasillaId, Decimal],
    inputs_by_id: Mapping[CasillaId, Decimal],
) -> tuple[tuple[CasillaParity, ...], tuple[CasillaParity, ...]]:
    """Compare every computed casilla across the supplied surfaces.

    Args:
        casillas: The revision's casilla definitions. Only
            :attr:`~domain.calculations.registry.schema_input_kind.InputKind.COMPUTED` members are
            compared; an operator-input cell holds whatever was written into it
            and comparing it against itself proves nothing.
        local_values: What the local Decimal runtime produced, or — on the
            export-preview use — what the plan would write.
        sheets_values: What the spreadsheet holds, read back.
        aeat_values: The AEAT oracle's expected values. Empty when no oracle is
            available, which leaves both AEAT flags ``None`` rather than False.
        inputs_by_id: Operator-supplied inputs, consulted only to decide whether
            a blank Sheets cell is a formula failure or an unfilled input.

    Returns:
        ``(every row, divergent rows)``. The second is a sublist of the first,
        never a re-derivation, so a caller cannot see a divergence that is
        absent from the full set.
    """
    rows: list[CasillaParity] = []
    divergences: list[CasillaParity] = []
    for casilla in casillas:
        if casilla.input_kind != InputKind.COMPUTED:
            continue
        local = local_values.get(casilla.id)
        sheets_v = sheets_values.get(casilla.id)
        aeat_v = aeat_values.get(casilla.id)
        row = _build_casilla_parity_row(casilla, local=local, sheets_v=sheets_v, aeat_v=aeat_v)
        rows.append(row)
        if _is_parity_divergent(row, sheets_v=sheets_v, local=local, inputs_by_id=inputs_by_id):
            divergences.append(row)
    return tuple(rows), tuple(divergences)


def resolve_parity_verdict(
    *,
    divergences: Sequence[CasillaParity],
    aeat_present: bool,
) -> Literal["all_match", "divergence", "inconclusive"]:
    """Resolve the top-level verdict from the divergences list and AEAT-oracle presence.

    ``inconclusive`` rather than ``all_match`` when no oracle was supplied: the
    two local surfaces agreeing says nothing about whether either matches AEAT.
    """
    if divergences:
        return "divergence"
    if aeat_present:
        return "all_match"
    return "inconclusive"


__all__ = [
    "CasillaParity",
    "collect_parity_rows",
    "resolve_parity_verdict",
]
