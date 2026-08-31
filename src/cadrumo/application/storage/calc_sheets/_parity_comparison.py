"""Pure per-casilla comparison across the calculation surfaces.

Extracted from the parity harness so the comparison can be reached without the
harness's write path. That separation is load-bearing rather than tidy:
:func:`~application.storage.calc_sheets.verify_modelo_parity` acquires its
spreadsheet side by CREATING or updating the workbook, seeding operator inputs
into ``Entradas`` and relations into ``Tarifas``, and reading ``Cálculos`` back —
so any caller that must not write cannot go through it. The export preview is
exactly that caller, and the decision record requires it to reuse this
comparison rather than grow a second differ.

The functions here take mappings and casilla definitions only. They deliberately
do NOT take a snapshot or a scenario: the export preview holds neither, and a
comparison that demanded them would have to be reimplemented for it, which is
the duplication this module exists to prevent.

The three surfaces are named from the parity use — ``local``, ``sheets``,
``aeat`` — and the preview use reads them as "what the plan would write",
"what the spreadsheet currently holds", and "absent". A divergent row is then
precisely a cell whose value would change.

COMPARISON IS EXACT, AND THAT IS THE CONTRACT RATHER THAN AN OVERSIGHT. The
reconcile surfaces compare filed against computed at the tolerance the registry
publishes per verification expectation, and it would be natural to assume this
module simply forgot to. It did not, for three reasons, and the first is
decisive: THE REGISTRY PUBLISHES NO TOLERANCE FOR THIS AXIS. Its tolerance is
declared on verification expectations, which govern filed-versus-computed
reconciliation — a legal question about whether a taxpayer's return agrees with
the authority. Engine-versus-spreadsheet is not that question, so adopting that
tolerance here would apply a legal allowance to an axis no law governs.

Second, the preview consumer asks "would this cell's value change", and any
difference is a write. A tolerance would make the preview UNDER-report cells the
apply would overwrite, which is the one error a dry run must not make. Third,
the parity consumer asks whether the spreadsheet reproduces the engine, and a
cent of slack there would hide exactly the formula transcription error the
harness exists to catch.

So a future reader reconciling this module against the reconcile surfaces should
not fold it onto ``verification_policy().tolerance``. If a real rounding
difference is ever observed between the Decimal runtime and a spreadsheet
formula, the fix is to quantize both sides to the modelo's money scale before
comparison, not to widen the comparison.

See Also:
    :func:`~application.storage.calc_sheets.verify_modelo_parity`
        The three-way harness that acquires the values and calls this.
    :class:`~domain.calculations.registry.RegistrySnapshot`
        Authority the caller resolves casilla definitions from.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....domain.calculations.registry.schema_input_kind import InputKind

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ....domain.calculations.registry.schema_surfaces import CasillaDefinition


class CasillaParity(BaseModel):
    """Per-casilla parity verdict across three calculation surfaces.

    Each ``*_vs_*`` flag is ``None`` exactly when one of its two sides carried
    no value, so "not compared" stays distinguishable from "compared and
    disagreed" — collapsing them to ``False`` would report a missing oracle as
    a divergence.

    ``Decimal`` is imported at module scope rather than under ``TYPE_CHECKING``
    because pydantic resolves this model's field annotations at RUNTIME, and
    ``from __future__ import annotations`` has already turned them into strings.
    A type-checking-only import leaves the class undefined and fails on first
    instantiation — while the module still imports, still collects, and still
    satisfies the linter that recommends the narrower form. Only the fields
    below need this; the type-checking block keeps everything used solely in
    function signatures.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    display_number: str
    label: str
    local: Decimal | None = None
    sheets: Decimal | None = None
    aeat: Decimal | None = None
    sheets_vs_local: bool | None = None
    local_vs_aeat: bool | None = None
    sheets_vs_aeat: bool | None = None


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
            :attr:`~domain.calculations.registry.InputKind.COMPUTED` members are
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
