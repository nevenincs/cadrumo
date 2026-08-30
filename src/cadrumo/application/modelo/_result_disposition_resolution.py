"""Single determined-fact resolution of a modelo's fichero result disposition.

The AEAT fichero "Tipo de declaración" encodes the *result disposition* of an
autoliquidación (a ingresar / a compensar / a devolver / negativa). For Modelo
303 a negative result is, by default, a credit carried forward (compensación,
``C``). Inscription in the Registro de devolución mensual (REDEME) is treated
as the standing monthly-devolución disposition policy for eligible negative
periods; a non-REDEME taxpayer may explicitly request devolución (``D``) only
in the last filing period of the year.

This module is the ONE place that determination is made. The export header
composer and the cross-period carry persistence both read the disposition from
:func:`resolve_modelo_result_disposition`, so the fichero ``D`` the operator
submits and the cross-period carry the next period reads can never disagree (a
period requested as devolución is excluded from compensación carry - never
both). It reuses the per-modelo result→code derivation
(:func:`~core.derive_result_disposition`) and the REDEME/last-period
eligibility gate (:func:`~domain.iva.refund_disposition_available`); it does
not duplicate either.

Before resolving the result, the persisted :class:`CalculationRevision` value map
is checked through the parent :class:`WorkUnit` against the law-determined
registry :class:`ModeloRevision`, so printed numbers, export refs, and ambiguous
metadata tokens fail before they can influence the disposition.

Legal basis (Modelo 303 refund election): RD 1624/1992 (RIVA) art. 30 (Registro
de devolución mensual); Ley 37/1992 (LIVA) art. 116 (the monthly-refund right).

See Also:
    :func:`core.derive_result_disposition`
        Diseño-grounded result-to-code derivation used before Modelo 303 refund
        election handling.
    :func:`domain.iva.refund_disposition_available`
        Law-determined REDEME/last-period eligibility gate layered on a carried
        Modelo 303 credit.
    :func:`application.modelo.file_modelo_revision`
        Filing transition that reads the same refund fact before persisting
        cross-period carry-forward observations.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import (
    CasillaId,
    Modelo,
    PaymentElection,
    Period,
    RefundElection,
    ResultDisposition,
    derive_result_disposition,
    result_disposition_casilla_ids,
    result_disposition_is_refund,
)
from ...core.errors import CoreValidationError
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_targets,
    declared_casilla_ids,
    format_noncanonical_casilla_reference,
)
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year, refund_disposition_available
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.calculation_revision import CalculationRevision
from ._action_errors import (
    CalculationRegistryUnavailableError,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloProfileReadinessError,
    ModeloRefundElectionNotEligibleError,
)
from ._calculation_helpers import assert_snapshot_matches_work_unit_revision
from ._registry_resources import registry_root

#: Provisional fallback "Tipo de declaración" disposition for a modelo that
#: declares the header but has no diseño-grounded result-disposition
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
    payment_election: PaymentElection = PaymentElection.INGRESO,
) -> ResultDisposition:
    """Resolve the single fichero "Tipo de declaración" result disposition.

    The boundary resolves a persisted :class:`CalculationRevision` through its
    parent :class:`WorkUnit` for a :class:`TaxpayerProfile`, using the supplied
    :class:`~core.Period` to decide whether a Modelo 303 refund election is
    lawful. The work unit fixes the modelo, filing year, and registry revision
    against which the revision's ``casilla_values`` are validated.

    Computes the modelo's base disposition from its final-result casilla via
    :func:`~core.derive_result_disposition`, then — for a Modelo 303
    credit (``C``) — applies the refund election: a taxpayer inscribed in the
    Registro de devolución mensual (REDEME) is treated as
    requesting devolución (``D``) for eligible negative periods under a standing
    monthly-devolución disposition policy; a non-REDEME taxpayer who explicitly
    elects ``DEVOLVER`` requests devolución for the negative *last* period of the
    year (Ley 37/1992 art. 116). The eligibility gate
    (:func:`~domain.iva.refund_disposition_available`) confirms the refund is
    lawful for the period. Every other disposition is returned unchanged.

    ``refund_election`` is the operator's per-filing opt-in (default
    :attr:`~core.RefundElection`, the non-regressive
    carry-forward). It is orthogonal to the standing REDEME inscription: REDEME
    is treated as the standing policy that resolves eligible
    negative periods to devolución regardless of this flag, while a non-REDEME
    taxpayer resolves to devolución only when both the period is eligible AND the
    operator elects ``DEVOLVER``. An election of ``DEVOLVER`` for an ineligible
    period is refused — never silently carried, never silently requested as
    devolución.

    Returns the one :class:`~core.ResultDisposition` both the export header
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
    base_disposition = base or DECLARATION_TYPE_FALLBACK
    return _resolve_elected_disposition(
        base_disposition,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        period=period,
        refund_election=refund_election,
        payment_election=payment_election,
    )


def _resolve_elected_disposition(
    base_disposition: ResultDisposition,
    *,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    period: Period,
    refund_election: RefundElection,
    payment_election: PaymentElection,
) -> ResultDisposition:
    """Apply the one election axis that the computed result makes applicable."""
    if base_disposition is ResultDisposition.INGRESO:
        if refund_election is not RefundElection.COMPENSAR:
            raise ModeloRefundElectionNotEligibleError(
                translated_message="errors.error.error_modelos",
                context={
                    "modelo": str(work_unit.modelo),
                    "base_disposition": base_disposition.value,
                    "refund_election": refund_election.value,
                },
            )
        return _apply_payment_election(work_unit=work_unit, payment_election=payment_election)

    if payment_election is not PaymentElection.INGRESO:
        raise ModeloPaymentElectionIncompatibleError(
            translated_message="errors.error.error_modelos",
            context={
                "modelo": str(work_unit.modelo),
                "base_disposition": base_disposition.value,
                "payment_election": payment_election.value,
            },
        )
    if refund_election is RefundElection.DEVOLVER and base_disposition is not ResultDisposition.COMPENSACION:
        raise ModeloRefundElectionNotEligibleError(
            translated_message="errors.error.error_modelos",
            context={
                "modelo": str(work_unit.modelo),
                "base_disposition": base_disposition.value,
                "refund_election": refund_election.value,
            },
        )
    return _apply_modelo_303_refund_election(
        base_disposition,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        period=period,
        refund_election=refund_election,
    )


def _apply_payment_election(
    *,
    work_unit: WorkUnit,
    payment_election: PaymentElection,
) -> ResultDisposition:
    """Resolve a positive-result settlement without changing refund/carry policy."""
    if payment_election is PaymentElection.INGRESO:
        return ResultDisposition.INGRESO
    if payment_election is PaymentElection.CUENTA_CORRIENTE:
        raise ModeloPaymentElectionCapabilityRefusedError(
            translated_message="errors.error.error_modelos",
            context={"modelo": str(work_unit.modelo), "payment_election": payment_election.value},
        )
    if work_unit.modelo != Modelo.M303.value:
        raise ModeloPaymentElectionCapabilityRefusedError(
            translated_message="errors.error.error_modelos",
            context={"modelo": str(work_unit.modelo), "payment_election": payment_election.value},
        )
    return ResultDisposition.DOMICILIACION


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
    # This deliberately resolves its own snapshot rather than calling
    # resolve_registry_snapshot_for_work_unit directly: that helper resolves on
    # ``work_unit.period``, while this boundary resolves on the
    # caller-supplied ``period``, which the export path threads down for the
    # Modelo 303 refund-election decision. The two are expected to agree and
    # nothing here proves they cannot diverge, so the resolution axis is left
    # as it stands rather than changed silently. The divergence assertion
    # itself (message + exception type) is shared via
    # assert_snapshot_matches_work_unit_revision so the two resolution sites
    # cannot drift in wording or refusal type.
    try:
        snapshot = bundled_authority().snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=period.registry_token,
        )
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_root_missing",
            context={"registry_root": registry_root()},
        ) from exc
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_snapshot_unresolved",
            context={
                "modelo": str(work_unit.modelo),
                "filing_year": work_unit.filing_year,
                "period": period.registry_token,
            },
        ) from exc
    assert_snapshot_matches_work_unit_revision(work_unit, snapshot, period=period)
    _reject_non_revision_casilla_values(
        modelo=str(work_unit.modelo),
        revision_id=snapshot.revision.id,
        casilla_values=revision.casilla_values,
        declared_ids=declared_casilla_ids(snapshot.revision),
        registry_revision=snapshot.revision,
    )
    result_ids = result_disposition_casilla_ids(str(work_unit.modelo))
    if result_ids is None:
        empty_result: dict[CasillaId, Decimal] = {}
        return empty_result
    result_values: dict[CasillaId, Decimal] = {}
    for casilla_id in result_ids:
        if casilla_id not in revision.casilla_values:
            continue
        value: Decimal = revision.casilla_values[casilla_id]
        result_values[casilla_id] = value
    return result_values


def _reject_non_revision_casilla_values(
    *,
    modelo: str,
    revision_id: RevisionId,
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
            noncanonical_details.append(format_noncanonical_casilla_reference(casilla_id, noncanonical_targets))
            continue
        unknown_ids.append(casilla_id)

    if noncanonical_details:
        details = "; ".join(noncanonical_details)
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={"modelo": modelo, "revision_id": revision_id, "casilla_refs": details},
        )
    if unknown_ids:
        unknown = ", ".join(repr(casilla_id) for casilla_id in unknown_ids)
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={"modelo": modelo, "revision_id": revision_id, "casilla_ids": unknown},
        )


def revision_is_refund_disposition(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
) -> bool:
    """Return whether the revision's resolved disposition is a refund (devolución).

    Resolves the supplied :class:`CalculationRevision` for a
    :class:`TaxpayerProfile`, with the same :class:`~core.Period` refund
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
        payment_election=payment_election,
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

    Two independent paths resolve to devolución (Tipo de declaración ``D``; Ley
    37/1992 art. 116):

    * **Standing REDEME election** — a taxpayer
      inscribed in the Registro de devolución mensual (art. 30 RD 1624/1992) is
      treated as
      requesting devolución for each eligible negative period. The inscription is
      the standing monthly-devolución disposition policy; this flag does not gate
      it.
    * **Per-filing opt-in** — a non-REDEME taxpayer who explicitly elects
      ``DEVOLVER`` requests devolución for the negative *last* filing period of
      the year (the annual liquidación). Outside the last period the only lawful
      disposition is compensación, so an election of ``DEVOLVER`` there is refused
      rather than silently downgraded or silently filed.

    A non-REDEME taxpayer who does not elect ``DEVOLVER`` keeps the carry-forward
    ``C``; every disposition other than a Modelo 303 ``COMPENSACION`` is untouched.
    """
    if work_unit.modelo != Modelo.M303.value or declaration_type is not ResultDisposition.COMPENSACION:
        return declaration_type

    iva_profile = workflow_profile.iva
    if iva_profile is None:
        raise ModeloProfileReadinessError(
            translated_message="application.modelo.errors.profile_readiness_missing",
            context={
                "modelo": Modelo.M303.value,
                "period": period.registry_token,
                "iva_profile_present": False,
            },
        )
    redeme = iva_profile.redeme_enrolled
    # Standing REDEME election: resolve eligible negative periods to devolución,
    # independent of the per-filing flag.
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
