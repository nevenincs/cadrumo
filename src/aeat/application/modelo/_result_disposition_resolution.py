"""Single determined-fact resolution of a modelo's fichero result disposition.

The AEAT fichero "Tipo de declaración" encodes the *result disposition* of an
autoliquidación (a ingresar / a compensar / a devolver / negativa). For Modelo
303 a negative result is, by default, a credit carried forward (compensación,
``C``); a taxpayer inscribed in the Registro de devolución mensual (REDEME) — or
filing the last period of the year — may instead request the credit back
(devolución, ``D``).

This module is the ONE place that determination is made. The export header
composer and the cross-period carry persistence both read the disposition from
:func:`resolve_modelo_result_disposition`, so the fichero ``D`` the operator
submits and the cross-period carry the next period reads can never disagree (a
refunded period requests the money back AND carries nothing — never both). It
reuses the codified per-modelo result→code derivation
(:func:`~aeat.core.derive_result_disposition`) and the REDEME/last-period
eligibility gate (:func:`~aeat.domain.iva.refund_disposition_available`); it does
not duplicate either.

Before resolving the result, the persisted :class:`CalculationRevision` value map
is checked through the parent :class:`WorkUnit` against the law-determined
registry :class:`ModeloRevision`, so printed numbers, export refs, and ambiguous
metadata tokens fail before they can influence the disposition.

Legal basis (Modelo 303 refund election): RD 1624/1992 (RIVA) art. 30 (Registro
de devolución mensual); Ley 37/1992 (LIVA) art. 116 (the monthly-refund right).

See Also:
    :func:`aeat.core.derive_result_disposition`
        Diseño-grounded result-to-code derivation used before Modelo 303 refund
        election handling.
    :func:`aeat.domain.iva.refund_disposition_available`
        Law-determined REDEME/last-period eligibility gate layered on a carried
        Modelo 303 credit.
    :func:`aeat.application.modelo.file_modelo_revision`
        Filing transition that reads the same refund fact before persisting
        cross-period carry-forward observations.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import (
    CasillaId,
    Modelo,
    Period,
    RefundElection,
    ResultDisposition,
    derive_result_disposition,
    result_disposition_casilla_ids,
    result_disposition_is_refund,
)
from ...core.errors import CoreValidationError
from ...core.resources import resources
from ...domain.calculations.registry import (
    ModeloRevision,
    casilla_noncanonical_reference_targets,
    declared_casilla_ids,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.iva import (
    is_last_filing_period_of_year,
    refund_disposition_available,
)
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit
from ._action_errors import ModeloRefundElectionNotEligibleError

#: Provisional fallback "Tipo de declaración" disposition for a modelo that
#: declares the header but has no codified, diseño-grounded result-disposition
#: spec. ``INGRESO`` ("I") is wrong for a credit/zero result, so a new modelo
#: MUST be added to the spec rather than relying on it. Mirrors the export
#: fallback constant — kept here because the resolver is the disposition authority.
DECLARATION_TYPE_FALLBACK: ResultDisposition = ResultDisposition.INGRESO


def resolve_modelo_result_disposition(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
    refund_election: RefundElection = RefundElection.COMPENSAR,
) -> ResultDisposition:
    """Resolve the single fichero "Tipo de declaración" result disposition.

    The boundary resolves a persisted :class:`CalculationRevision` through its
    parent :class:`WorkUnit` for a :class:`TaxpayerProfile`, using the supplied
    :class:`~aeat.core.Period` to decide whether a Modelo 303 refund election is
    lawful. The work unit fixes the modelo, filing year, and registry revision
    against which the revision's ``casilla_values`` are validated.

    Computes the modelo's base disposition from its final-result casilla via the
    codified :func:`~aeat.core.derive_result_disposition`, then — for a Modelo 303
    credit (``C``) — applies the refund election: a taxpayer inscribed in the
    Registro de devolución mensual (REDEME) files the negative period as a refund
    (``D``) every period under its standing election; a non-REDEME taxpayer who
    explicitly elects ``DEVOLVER`` files the negative *last* period of the year as
    a refund (Ley 37/1992 art. 116). The eligibility gate
    (:func:`~aeat.domain.iva.refund_disposition_available`) confirms the refund is
    lawful for the period. Every other disposition is returned unchanged.

    ``refund_election`` is the operator's per-filing opt-in (default
    :attr:`~aeat.domain.iva.RefundElection.COMPENSAR`, the non-regressive
    carry-forward). It is orthogonal to the standing REDEME inscription: a REDEME
    taxpayer refunds every eligible period regardless of this flag, while a
    non-REDEME taxpayer refunds only when both the period is eligible AND the
    operator elects ``DEVOLVER``. An election of ``DEVOLVER`` for an ineligible
    period is refused — never silently carried, never silently refunded.

    Returns the one :class:`~aeat.core.ResultDisposition` both the export header
    composer and the cross-period carry persistence read, so the fichero
    disposition and the carry can never disagree.

    Raises:
        ModeloRefundElectionNotEligibleError: When ``refund_election`` is
            ``DEVOLVER`` but the period is not a lawful refund period for a
            non-REDEME taxpayer.
    """
    base = derive_result_disposition(
        work_unit.modelo,
        _result_disposition_values_for_revision(work_unit=work_unit, revision=revision, period=period),
    )
    if base is None:
        return DECLARATION_TYPE_FALLBACK
    return _apply_modelo_303_refund_election(
        base,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        period=period,
        refund_election=refund_election,
    )


def _result_disposition_values_for_revision(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    period: Period,
) -> Mapping[CasillaId, Decimal]:
    """Validate a full :class:`CalculationRevision` value map and return result casillas.

    The :class:`WorkUnit` selects the registry snapshot whose
    :class:`ModeloRevision` declares the canonical casilla ids accepted here.
    """
    snapshot = resources().modelos.authority.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=period.registry_token,
    )
    if snapshot.revision.id != work_unit.revision_id:
        raise CoreValidationError(
            f"result disposition for work unit {work_unit.work_unit_id!r} resolved registry revision "
            f"{snapshot.revision.id!r}, but the work unit was created against {work_unit.revision_id!r}",
            context={
                "modelo": str(work_unit.modelo),
                "filing_year": str(work_unit.filing_year),
                "period": period.registry_token,
                "work_unit_revision_id": work_unit.revision_id,
                "resolved_revision_id": snapshot.revision.id,
            },
        )
    _reject_non_revision_casilla_values(
        modelo=str(work_unit.modelo),
        revision_id=snapshot.revision.id,
        casilla_values=revision.casilla_values,
        declared_ids=declared_casilla_ids(snapshot.revision),
        registry_revision=snapshot.revision,
    )
    result_ids = result_disposition_casilla_ids(str(work_unit.modelo))
    if result_ids is None:
        return {}
    return {
        casilla_id: revision.casilla_values[casilla_id]
        for casilla_id in result_ids
        if casilla_id in revision.casilla_values
    }


def _reject_non_revision_casilla_values(
    *,
    modelo: str,
    revision_id: str,
    casilla_values: Mapping[CasillaId, Decimal],
    declared_ids: frozenset[CasillaId],
    registry_revision: ModeloRevision,
) -> None:
    noncanonical_details: list[str] = []
    unknown_ids: list[CasillaId] = []
    for casilla_id in sorted(casilla_values):
        if casilla_id in declared_ids:
            continue
        noncanonical_targets = casilla_noncanonical_reference_targets(registry_revision, casilla_id)
        if noncanonical_targets:
            noncanonical_details.append(_format_noncanonical_casilla_reference(casilla_id, noncanonical_targets))
            continue
        unknown_ids.append(casilla_id)

    if noncanonical_details:
        details = "; ".join(noncanonical_details)
        raise CoreValidationError(
            f"result disposition for modelo {modelo!r} revision {revision_id!r} received "
            f"non-canonical casilla reference tokens, not canonical casilla.id values: {details}",
            context={"modelo": modelo, "revision_id": revision_id, "casilla_refs": details},
        )
    if unknown_ids:
        unknown = ", ".join(repr(casilla_id) for casilla_id in unknown_ids)
        raise CoreValidationError(
            f"result disposition for modelo {modelo!r} revision {revision_id!r} received "
            f"unknown casilla.id values: {unknown}",
            context={"modelo": modelo, "revision_id": revision_id, "casilla_ids": unknown},
        )


def _format_noncanonical_casilla_reference(token: str, targets: tuple[CasillaId, ...]) -> str:
    rendered_targets = ", ".join(repr(target) for target in targets)
    if len(targets) > 1:
        return f"{token!r} is ambiguous; candidate casilla.id values: {rendered_targets}"
    return f"{token!r} -> {rendered_targets}"


def revision_is_refund_disposition(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
    refund_election: RefundElection = RefundElection.COMPENSAR,
) -> bool:
    """Return whether the revision's resolved disposition is a refund (devolución).

    Resolves the supplied :class:`CalculationRevision` for a
    :class:`TaxpayerProfile`, with the same :class:`~aeat.core.Period` refund
    eligibility context used by export.

    Convenience wrapper used by the cross-period carry path: a refunded Modelo 303
    period generates zero compensación carry-forward. Reads the SAME resolved
    disposition the export emits via :func:`resolve_modelo_result_disposition`,
    threading the same ``refund_election`` so the carry and the fichero agree.
    """
    disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=period,
        refund_election=refund_election,
    )
    return result_disposition_is_refund(disposition)


def _apply_modelo_303_refund_election(
    declaration_type: ResultDisposition,
    *,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    period: Period,
    refund_election: RefundElection,
) -> ResultDisposition:
    """Upgrade a Modelo 303 carry-forward (``C``) to a refund (``D``) per the refund election.

    Two independent paths produce a refund (devolución, Tipo de declaración ``D``;
    Ley 37/1992 art. 116):

    * **Standing REDEME election** — a taxpayer inscribed in the Registro de
      devolución mensual (art. 30 RD 1624/1992) refunds *every* eligible period.
      The inscription is the always-on election; this flag does not gate it.
    * **Per-filing opt-in** — a non-REDEME taxpayer who explicitly elects
      ``DEVOLVER`` refunds the negative *last* filing period of the year (the
      annual liquidación). Outside the last period the only lawful disposition is
      compensación, so an election of ``DEVOLVER`` there is refused rather than
      silently downgraded or silently filed.

    A non-REDEME taxpayer who does not elect ``DEVOLVER`` keeps the carry-forward
    ``C``; every disposition other than a Modelo 303 ``COMPENSACION`` is untouched.
    """
    if work_unit.modelo != Modelo.M303.value or declaration_type is not ResultDisposition.COMPENSACION:
        return declaration_type

    redeme = workflow_profile.iva.redeme_enrolled
    # Standing REDEME election: refund every eligible period, independent of the
    # per-filing flag.
    if redeme and refund_disposition_available(redeme_enrolled=redeme, period=period):
        return ResultDisposition.DEVOLUCION

    if refund_election is not RefundElection.DEVOLVER:
        return declaration_type

    # Per-filing opt-in for a non-REDEME taxpayer: only lawful in the last filing
    # period of the year. Refuse an out-of-window election instead of silently
    # discarding the refund request or silently filing an unlawful refund.
    if not is_last_filing_period_of_year(period):
        raise ModeloRefundElectionNotEligibleError(
            translated_message="application.modelo.errors.refund_election_not_eligible",
            context={
                "modelo": Modelo.M303.value,
                "filing_year": str(period.filing_year),
                "period": period.registry_token,
            },
        )
    return ResultDisposition.DEVOLUCION


__all__ = [
    "DECLARATION_TYPE_FALLBACK",
    "resolve_modelo_result_disposition",
    "revision_is_refund_disposition",
]
