"""What the calculation itself noticed, placed on the filer's attention scale and worded from the catalogue.

A calculation raises diagnostics while it resolves its sources: an amount from
the records that reached no box, a box whose source produced nothing, a value
the filer typed that differs from the worked-out one. Each reason has one
place on the scale the findings list uses, one sentence for what happened and
one for what to do, in every language.

The reasons that block filing are exactly those the application refuses
(:data:`BLOCKING_REASONS`), by one of three routes: the calculation-note gate
refuses checking, exporting and recording (:data:`GATE_REFUSED_REASONS`), a
check step refuses on its own evidence (:data:`CHECK_REFUSED_REASONS`), or the
export refuses the file (:data:`EXPORT_REFUSED_REASONS`). The editor withholds
filing on the same set, so the two can never disagree. A reason a check step
decides waits for that check: until the current calculation is checked the
editor offers the check next, and once it is, the check's own finding of the
same cause stands in the note's place.

A printed box that could not be worked out, a source with no route and a source
store not ready are refused by the gate: their producers report only sources
that apply to the filer. A box that could not be worked out blocks only when the
form prints it (:data:`PRINTED_BOX_REASONS`, as :mod:`.printed_boxes` reads the
form); a working figure is worth checking. A value arriving by an undeclared
route is worth checking and persists with the calculation: it still fires for a
route kept without a terminal origin by design, so refusing on it would refuse
declarations calculated through that route. Every diagnostic that does not persist is held in this process only until
the next calculation of the declaration (:class:`CalculationNoteStore`), and a
declaration opened afresh says to calculate again to see them.
"""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from types import MappingProxyType
from typing import Final, get_args

from ...core.aggregation import BindingSourceKind
from ..aggregation.source_mesh import CalculationSourceDiagnostic, CalculationSourceDiagnosticReason
from .work_form_models import ModeloFormAttention

_B = ModeloFormAttention.BLOCKS
_M = ModeloFormAttention.MISSING
_C = ModeloFormAttention.CHECK
_I = ModeloFormAttention.INFO

GATE_REFUSED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "invoice_reverse_charge_cuota_not_derivable",
        "unresolved_binding",
        "unhandled_binding_source",
        "source_domain_not_ready",
    }
)
"""Reasons the calculation-note gate refuses checking, exporting and recording on: a figure left out or unworked."""
CHECK_REFUSED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
    }
)
"""Reasons a check step refuses on its own evidence, which may also admit them (an attested empty detail)."""
EXPORT_REFUSED_REASONS: Final[frozenset[str]] = frozenset({"rate_boxes_underaccount_total"})
"""Reasons the export refuses the file on: an IVA total its rate boxes do not account for."""
BLOCKING_REASONS: Final[frozenset[str]] = GATE_REFUSED_REASONS | CHECK_REFUSED_REASONS | EXPORT_REFUSED_REASONS
"""Every reason the application refuses filing on, and so the editor too."""

CALCULATION_NOTE_ATTENTION: Final[Mapping[str, ModeloFormAttention]] = MappingProxyType(
    {
        **dict.fromkeys(BLOCKING_REASONS, _B),
        # Persisted and shown, not refused: the route it reports may lack a terminal origin by design.
        "terminal_origin_mismatch": _C,
        "unresolved_derived_binding": _C,
        # Something only the filer can supply.
        "source_issue": _M,
        "prior_payment_not_deducted": _M,
        "prior_payment_minoracion_not_captured": _M,
        "official_box_unpopulated": _M,
        "settlement_not_computed": _M,
        "prorrata_especial_check_unavailable": _M,
        "missing_transaction_evidence": _M,
        "unclassified_declarant_role_fact": _M,
        "unconverted_foreign_currency": _M,
        "aggregation_activity_undeclared": _M,
        # Worth checking. A value Cadrumo inferred or kept is among them: no box
        # lists it as assumed, so nothing in the editor can confirm it, and the
        # filer checks it against their records instead.
        "operator_override_diverges_from_computed": _C,
        "orphaned_override": _C,
        "devengo_date_proxy_attribution": _C,
        "m349_clave_inferred_from_category": _C,
        "inferred_retencion_rate_unmatched": _C,
        "inferred_retencion_sectoral_rate_unconfirmed": _C,
        "invoice_category_counterparty_mismatch": _C,
        "invoice_recargo_departs_from_published_rate": _C,
        "invoice_recargo_not_attributable_to_a_tier": _C,
        "administrador_retencion_rate_mismatch": _C,
        "prorrata_especial_obligatoria": _C,
        "ungrounded_income_substrate": _C,
        "unusable_sales_invoice_evidence": _C,
        "structurally_unroutable_base_category": _C,
        "storage_degraded": _C,
        "duplicate_binding_owner": _C,
        "duplicate_bound_casilla_owner": _C,
        "duplicate_relation_owner": _C,
        "m193_settled_row_amounts_unresolved_authority": _C,
        "inferred_retencion_excluded_from_credit": _C,
        "unresolved_retencion_substrate": _C,
        "advisory_retencion_credit_grade": _C,
        # For the filer's information.
        "deferred_binding_source": _I,
        "oss_no_live_source": _I,
        "register_owned_capital_acquisition": _I,
        "dt12_regime_window_closed": _I,
        "dt12_regime_window_unverified": _I,
        "dt12_parcial_rescate_guidance": _I,
    }
)
"""The one place on the filer's scale of every reason a calculation diagnostic can carry."""

PRINTED_BOX_REASONS: Final[frozenset[str]] = frozenset({"unresolved_binding"})
"""Blocking reasons that withhold filing only on a printed box: a working figure they name is worth checking."""

UNWORKED_BOX_REASONS: Final[frozenset[str]] = frozenset({"unresolved_binding", "unresolved_derived_binding"})
"""Reasons that name a box that could not be worked out: it never reads as a zero."""

RECORDS_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "structurally_unroutable_base_category",
        "withholding_detail_absent",
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "missing_transaction_evidence",
        "devengo_date_proxy_attribution",
        "m349_clave_inferred_from_category",
        "inferred_retencion_rate_unmatched",
        "inferred_retencion_sectoral_rate_unconfirmed",
        "administrador_retencion_rate_mismatch",
        "unconverted_foreign_currency",
        "unclassified_declarant_role_fact",
        "invoice_category_counterparty_mismatch",
        "invoice_reverse_charge_cuota_not_derivable",
        "invoice_recargo_departs_from_published_rate",
        "invoice_recargo_not_attributable_to_a_tier",
        "ungrounded_income_substrate",
        "unusable_sales_invoice_evidence",
        "aggregation_activity_undeclared",
    }
)
"""Reasons whose cause is an entry in the filer's records, where the note sits and is put right."""

_KEY_ROOT: Final[str] = "application.modelo.calc_diagnostic"
STALE_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic.stale"
REOPEN_HINT_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic.reopen_hint"


def note_attention(reason: str, *, box: str | None) -> ModeloFormAttention:
    """Place one diagnostic reason on the filer's scale; ``box`` is the number the form prints for the box it names.

    ``box`` is ``None`` when the reason names no box or a working figure the
    form does not print (:mod:`.printed_boxes`).
    """
    if reason in PRINTED_BOX_REASONS and box is None:
        return _C
    return CALCULATION_NOTE_ATTENTION[reason]


def what_locale_key(reason: str) -> str:
    """The catalogue key of the sentence saying what the calculation noticed."""
    return f"{_KEY_ROOT}.{reason}.what"


def what_to_do_locale_key(reason: str) -> str:
    """The catalogue key of the sentence saying what to do about it."""
    return f"{_KEY_ROOT}.{reason}.what_to_do"


def durable_binding_source(diagnostic: CalculationSourceDiagnostic) -> BindingSourceKind | None:
    """The binding source kind a diagnostic names, read from its typed field or its source kind."""
    if diagnostic.binding_source is not None:
        return diagnostic.binding_source
    try:
        return BindingSourceKind(diagnostic.source_kind)
    except ValueError:
        return None


class CalculationNoteStore:
    """The diagnostics of each declaration's latest calculation in this process, by calculation revision.

    A calculation's diagnostics other than the blocking ones are not stored
    with it: they belong to the calculation that raised them, so they are held
    here until the next calculation of the same work unit replaces them, and
    are gone when the application closes.
    """

    def __init__(self) -> None:
        """Start with nothing held."""
        self._lock = Lock()
        self._by_work_unit: dict[str, tuple[str, tuple[CalculationSourceDiagnostic, ...]]] = {}

    def record(
        self, work_unit_id: str, calculation_revision_id: str, diagnostics: tuple[CalculationSourceDiagnostic, ...]
    ) -> None:
        """Hold one calculation's diagnostics, replacing the work unit's earlier ones."""
        with self._lock:
            self._by_work_unit[work_unit_id] = (calculation_revision_id, diagnostics)

    def diagnostics_for(
        self, work_unit_id: str, calculation_revision_id: str | None
    ) -> tuple[CalculationSourceDiagnostic, ...] | None:
        """The diagnostics of that calculation, or ``None`` when this process did not run it."""
        with self._lock:
            held = self._by_work_unit.get(work_unit_id)
        if held is None or calculation_revision_id is None or held[0] != calculation_revision_id:
            return None
        return held[1]


CALCULATION_NOTES: Final[CalculationNoteStore] = CalculationNoteStore()
"""The process's one holder of the latest calculation's diagnostics per declaration."""


def _require_total_levels() -> None:
    """Refuse a diagnostic reason with no place on the scale, or a place for a reason that no longer exists."""
    reasons = set(get_args(CalculationSourceDiagnosticReason))
    if set(CALCULATION_NOTE_ATTENTION) != reasons:
        missing = sorted(reasons - set(CALCULATION_NOTE_ATTENTION))
        extra = sorted(set(CALCULATION_NOTE_ATTENTION) - reasons)
        raise ValueError(f"calculation note levels must cover every reason; missing={missing} extra={extra}")
    blocking_level = frozenset(reason for reason, level in CALCULATION_NOTE_ATTENTION.items() if level is _B)
    if blocking_level.symmetric_difference(BLOCKING_REASONS):
        raise ValueError("the blocking level holds exactly the reasons the application refuses filing on")
    if ModeloFormAttention.CONFIRM in CALCULATION_NOTE_ATTENTION.values():
        raise ValueError("only an assumed box is confirmed; no calculation note waits for a confirmation")
    if not PRINTED_BOX_REASONS <= GATE_REFUSED_REASONS:
        raise ValueError("a reason that blocks only on a printed box must be one the gate refuses")


_require_total_levels()


__all__ = [
    "BLOCKING_REASONS",
    "CALCULATION_NOTES",
    "CALCULATION_NOTE_ATTENTION",
    "CHECK_REFUSED_REASONS",
    "EXPORT_REFUSED_REASONS",
    "GATE_REFUSED_REASONS",
    "PRINTED_BOX_REASONS",
    "RECORDS_REASONS",
    "REOPEN_HINT_LOCALE_KEY",
    "STALE_LOCALE_KEY",
    "UNWORKED_BOX_REASONS",
    "CalculationNoteStore",
    "durable_binding_source",
    "note_attention",
    "what_locale_key",
    "what_to_do_locale_key",
]
