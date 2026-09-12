"""Message builders for Modelo 100 mínimo por descendientes diagnostics.

The registry-facing collection seams live in the sibling private module. These
revision-specific message builders have a public module owner so callers do
not reach into that seam for constants or diagnostic construction.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.calculations.registry.schema import ModeloRevision
from ..aggregation.source_mesh import CalculationSourceDiagnostic

__all__ = [
    "MAX_NAMED_DESCENDANTS",
    "_count_desync_advisory",
    "_dependencia_assimilated_advisory",
    "_dependencia_suppressed_advisory",
    "_entry_date_missing_advisory",
    "_prorrata_inferred_advisory",
    "_rentas_undeclared_advisory",
    "_undeclared_advisory",
]

_DESCENDANTS_COUNT_PATH = "renta_family.descendientes_count"
_UNDECLARED_SOURCE_KIND = "minimo_descendientes_undeclared"
_COUNT_DESYNC_SOURCE_KIND = "descendientes_count_desync"
_PRORRATA_INFERRED_SOURCE_KIND = "minimo_descendientes_prorrata_inferred"
_RENTAS_UNDECLARED_SOURCE_KIND = "minimo_descendientes_rentas_undeclared"
_ENTRY_DATE_MISSING_SOURCE_KIND = "minimo_descendientes_entry_date_missing"
_DEPENDENCIA_ASSIMILATED_SOURCE_KIND = "minimo_descendientes_dependencia_assimilated"
_DEPENDENCIA_SUPPRESSED_SOURCE_KIND = "minimo_descendientes_dependencia_suppressed"

# The interpolated descendant list is the only unbounded term in these
# operator-facing messages. Keep the shared cap in this public owner so the
# calculate-input diagnostic renderer uses the same bound.
MAX_NAMED_DESCENDANTS = 3


def _name_indices(indices: list[int]) -> str:
    """Render descendant paths for a message, bounded by household size."""
    shown = ", ".join(f"renta_family.descendiente.{index}" for index in indices[:MAX_NAMED_DESCENDANTS])
    remainder = len(indices) - MAX_NAMED_DESCENDANTS
    return f"{shown} and {remainder} more" if remainder > 0 else shown


def _casilla_legal_refs(revision: ModeloRevision, casilla_id: CasillaId) -> tuple[LegalRefId, ...]:
    """Read one casilla's own legal grounding and its binding grounding."""
    casilla = next((candidate for candidate in revision.casillas if candidate.id == casilla_id), None)
    if casilla is None:
        return ()
    binding = next((candidate for candidate in revision.bindings if candidate.id == casilla.binding), None)
    binding_legal = binding.legal_refs if binding is not None else ()
    return tuple(dict.fromkeys((*casilla.legal_refs, *binding_legal)))


def _undeclared_advisory(revision: ModeloRevision, casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_UNDECLARED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes, parte estatal) resolved to zero "
            "because the active profile declares no renta_family.descendiente facts. If you have "
            "children or other eligible descendants, the Art. 58 LIRPF allowance is being silently "
            "omitted"
        ),
        remedy=("Declare each descendant with `descendiente add --descendiente NACIMIENTO=YYYY-MM-DD`, before filing."),
        casilla_id=casilla_id,
        legal_refs=_casilla_legal_refs(revision, casilla_id),
    )


def _prorrata_inferred_advisory(
    revision: ModeloRevision,
    indices: list[int],
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_PRORRATA_INFERRED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) was HALVED under Art. 61 norma 1ª "
            f"LIRPF for {_name_indices(indices)}: the profile indicates a second entitled "
            "contribuyente (marital status, spouse record or declaration type) and no explicit "
            "answer was given. That is an inference, not a declared fact"
        ),
        remedy=(
            "State it with `descendiente add --descendiente PRORRATA=false` to claim the full "
            "mínimo, or PRORRATA=true to confirm the split."
        ),
        casilla_id=casilla_id,
        legal_refs=_casilla_legal_refs(revision, casilla_id),
    )


def _rentas_undeclared_advisory(
    revision: ModeloRevision,
    indices: list[int],
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_RENTAS_UNDECLARED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) claims a full tranche for "
            f"{_name_indices(indices)} with no annual-rentas figure on record. Art. 58.1 LIRPF "
            "withdraws it above the rentas ceiling, and Art. 61 norma 2ª when the descendant files "
            "their own return above that figure; an absent figure exceeds neither"
        ),
        remedy=(
            "Declare it with `descendiente add --descendiente RENTAS=N`. RENTAS=0 is a valid "
            "answer and silences this advisory."
        ),
        casilla_id=casilla_id,
        asserted_legal_refs=("ley-35-2006:art-58-1", "ley-35-2006:art-61-norma-2"),
    )


def _entry_date_missing_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_ENTRY_DATE_MISSING_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} withholds the Art. 58.2 LIRPF increase for "
            f"{_name_indices(indices)}: the relación is an adopción or entitling acogimiento, "
            "granted regardless of age in the entry period and the two following, but no entry "
            "date is on record so the window cannot be measured"
        ),
        remedy=(
            "Declare INSCRIPCION=YYYY-MM-DD (Registro Civil, or the resolución if none required) "
            "or ACOGIMIENTO=YYYY-MM-DD via `descendiente add`. The missing fact is the entry date, "
            "not the birth date."
        ),
        casilla_id=casilla_id,
    )


def _dependencia_assimilated_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_DEPENDENCIA_ASSIMILATED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) grants the Art. 58 allowance for "
            f"{_name_indices(indices)} on DECLARED economic dependency rather than cohabitation. "
            "The authority allows this for a progenitor without custody who pays no judicial "
            "anualidades and still contributes to the descendant's upkeep"
        ),
        remedy="Confirm the declaration holds for the filing year before filing.",
        casilla_id=casilla_id,
    )


def _dependencia_suppressed_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_DEPENDENCIA_SUPPRESSED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) WITHHOLDS the Art. 58 dependency "
            f"assimilation for {_name_indices(indices)} because the profile declares judicial "
            "anualidades por alimentos. The statutory carve-out is per-child, but this model "
            "cannot yet attribute a payment to one descendant, so a declared amount suppresses "
            "the assimilation for all of them"
        ),
        remedy=(
            "Where the anualidades are paid for a different descendant this under-grants the "
            "mínimo, so check the figure before filing."
        ),
        casilla_id=casilla_id,
    )


def _count_desync_advisory(stored: Decimal, rows: int) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_COUNT_DESYNC_SOURCE_KIND,
        message=(
            f"profile fact {_DESCENDANTS_COUNT_PATH!r} declares {stored} but the profile carries "
            f"{rows} renta_family.descendiente row(s). The count feeds its own Modelo 100 binding "
            "while the mínimo por descendientes casillas are computed from the rows, so the filing "
            "would carry two different answers"
        ),
        remedy=("Re-enter the descendants on the active profile, which rewrites the count and the rows together."),
    )
