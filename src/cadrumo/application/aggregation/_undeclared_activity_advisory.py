"""Calculate-path advisory for a casilla emptied by an undeclarable activity.

An aggregation that narrows rows by declared activity produces two zeros that
look identical from the casilla. One is correct: the taxpayer carried on no such
activity, so the box is empty because there is nothing to put in it. The other is
a silence: the taxpayer carried on income in the period, and nobody ever declared
what activity it belonged to, so every row was excluded by a rule the operator
has no way to satisfy.

The exclusion rule itself is CORRECT and this module does not touch it. A row
with no declared activity must not enter an activity-scoped casilla: admitting it
would route a filer's income into a box their activity may not answer to, and
that is the over-declaration error — strictly worse than an under-filled box the
operator can still complete by hand. What was missing is any statement that the
box is empty for that reason, which is what makes the zero a silent one
(``no-silent-under-declaration``).

So the advisory asserts nothing about the excluded income. It does not say the
income is agrarian, or that it belongs in the casilla, because nothing on the
ledger establishes either — that absence IS the finding. It says only what is
measured: this period carries income the casilla did not admit, and no activity
is declared for any of it.

Grounded from the registry rather than from prose. The casilla's own
``legal_refs`` / ``source_refs`` and those of the binding that feeds it ride the
diagnostic as typed data, read off the
:class:`~domain.calculations.registry.ModeloRevision` the resolver already holds.
Restating an article here would mint a second, unversioned copy of grounding the
registry owns, and would silently stop matching the moment a revision re-grounds
the box.

Fires narrowly, and the narrowness is the whole value. Three conditions must hold
together, and each one excludes a population that would otherwise be told
something useless:

* a narrowing actually ran, so the Modelo 130 and Modelo 100 paths are silent;
* the narrowing excluded at least one row, so a filer with NO activity at all in
  the period is never flagged — that filer's zero is the correct one, and an
  advisory on it would fire on every inactive quarter and train the operator to
  ignore the channel on the quarter where it is genuinely right;
* not one excluded row declares an activity, so a filer who HAS declared some
  other activity is silent — they answered the question, and their empty box is
  the correct answer to it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, NamedTuple

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ids import BindingId, LegalRefId, SourceRefId
from ...domain.calculations.registry.schema import ModeloRevision
from ._renta_income_ledger import RentaIncomeLedgerAggregation
from ._source_mesh import CalculationSourceDiagnostic

#: Diagnostic ``source_kind`` for a casilla emptied entirely by an activity
#: narrowing over income whose activity nobody declared.
UNDECLARED_ACTIVITY_INCOME_SOURCE_KIND: Final[str] = "undeclared_activity_income"


class _Grounding(NamedTuple):
    """Registry grounding for one casilla and the binding that feeds it."""

    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    binding_id: BindingId | None


def _casilla_grounding(revision: ModeloRevision, casilla_id: CasillaId) -> _Grounding | None:
    """Read the casilla's and its binding's grounding off ``revision``.

    Returns ``None`` when the revision declares no such casilla: the advisory
    would then be speaking about a box this filing does not have, which is a
    statement about the registry rather than about the taxpayer.

    A casilla present but ungrounded still yields a value. Empty refs are a
    registry defect, and suppressing a real finding because the record that would
    explain it is incomplete hides both problems instead of one.
    """
    casilla = next((candidate for candidate in revision.casillas if candidate.id == casilla_id), None)
    if casilla is None:
        return None
    binding = next(
        (candidate for candidate in revision.bindings if candidate.id == casilla.binding),
        None,
    )
    binding_legal = binding.legal_refs if binding is not None else ()
    binding_source = binding.source_refs if binding is not None else ()
    return _Grounding(
        # Ordered union, casilla first: the casilla is the subject the operator
        # is reading about, and the binding grounds the route the value would
        # have taken. ``dict.fromkeys`` dedupes while preserving that order,
        # matching how the provenance channel merges the same two ref families.
        legal_refs=tuple(dict.fromkeys((*casilla.legal_refs, *binding_legal))),
        source_refs=tuple(dict.fromkeys((*casilla.source_refs, *binding_source))),
        binding_id=casilla.binding,
    )


def undeclared_activity_income_advisory_observations(
    aggregation: RentaIncomeLedgerAggregation,
    revision: ModeloRevision,
    *,
    resolver_id: str | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when an activity narrowing emptied a casilla in silence.

    Args:
        aggregation: The income aggregation whose
            :attr:`~._renta_income_ledger.RentaIncomeLedgerAggregation.unadmitted_activity_income`
            census measures what the narrowing kept out. ``None`` there means no
            narrowing ran and the advisory is silent.
        revision: The :class:`~domain.calculations.registry.ModeloRevision` being
            calculated, read for the casilla and binding grounding the advisory
            carries. Never for a legal figure — the refs are identifiers, and the
            provisions behind them stay in the legal catalogue.
        resolver_id: Identifier of the resolver emitting the diagnostic, stamped
            on so an operator can attribute the advisory to the source that
            raised it.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple whenever the
        casilla's zero is an answer rather than a silence.
    """
    census = aggregation.unadmitted_activity_income
    if census is None:
        # No narrowing ran on this projection, so no row was excluded for want of
        # a declared activity and there is nothing to disclose.
        return ()
    if census.row_count == 0:
        # The load-bearing negative. A filer with no income the narrowing had to
        # exclude is a filer whose empty box is simply correct, and firing here
        # would put an advisory on every inactive period.
        return ()
    if census.any_activity_declared:
        # At least one excluded row states an activity, so the question this
        # advisory exists to raise has been answered: the rows were excluded for
        # declaring a DIFFERENT activity, not for declaring none.
        return ()
    if _admitted_total(aggregation, census.target_casilla_id) != Decimal("0"):
        # The casilla is populated. Income reaching it means the narrowing is
        # working as intended on a filer who declared the activity for some rows;
        # a partially-filled box is not the silence this reports.
        return ()
    grounding = _casilla_grounding(revision, census.target_casilla_id)
    if grounding is None:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="aggregation_activity_undeclared",
            source_kind=UNDECLARED_ACTIVITY_INCOME_SOURCE_KIND,
            resolver_id=resolver_id,
            casilla_id=census.target_casilla_id,
            binding_id=grounding.binding_id,
            legal_refs=grounding.legal_refs,
            source_refs=grounding.source_refs,
            message=(
                f"casilla {census.target_casilla_id!r} on modelo {aggregation.modelo} resolved to zero "
                f"while this period carries {census.row_count} income row(s) totalling "
                f"{census.income_total} EUR that it did not admit. Not one of them declares a tipo de "
                f"actividad, and a row declaring none is excluded by design, because silence about an "
                f"activity cannot be read as a declaration of one. Whether any of this income belongs "
                f"in the casilla is not established here: the ledger records no activity to decide it"
            ),
            remedy=(
                "Confirm before filing whether any of this income belongs in this casilla. No activity "
                "is recorded against these rows, so it cannot be populated from the ledger."
            ),
        ),
    )


def _admitted_total(aggregation: RentaIncomeLedgerAggregation, casilla_id: CasillaId) -> Decimal:
    """Return what the narrowed casilla actually folded, zero when it folded nothing."""
    return aggregation.casilla_aggregation.casilla_values.get(casilla_id, Decimal("0"))


__all__ = [
    "UNDECLARED_ACTIVITY_INCOME_SOURCE_KIND",
    "undeclared_activity_income_advisory_observations",
]
