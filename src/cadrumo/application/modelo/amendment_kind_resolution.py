"""Period-aware amendment-kind resolution and the liability-increase guard.

AEAT's amendment mechanism for a self-assessment changed over time (see
:mod:`~core.amendment_kind_regime` for the full grounding). Before the
``autoliquidación rectificativa`` unification, a correction that raised the
tax due filed as a ``complementaria`` (LGT art. 122.2) while a correction
that lowered it required the separate ``solicitud de rectificación``
procedure (LGT art. 120.3) — a self-filed complementaria cannot lawfully
lower a taxpayer's own declared liability. This module is the single place
that:

* refuses an operator-requested
  :class:`~FilingDeclarationKind` that the
  resolved ``(modelo, period)`` does not legally permit, naming the accepted
  kind set in the refusal (never a bare "invalid" message); and
* classifies, for a pre-rectificativa period, whether the requested
  correction increases or decreases the taxpayer's declared liability, so a
  ``complementaria`` requested for a liability-decreasing correction is
  refused with guidance toward the ``solicitud de rectificación`` procedure
  instead of being silently accepted as if it were lawful.

:func:`amend_modelo_revision` calls
:func:`assert_amendment_kind_permitted` before it persists anything, so an
illegal kind can never reach the catalogue.

See Also:
    :func:`~domain.calculations.registry.amendment_regime_policy.resolve_amendment_kind_regime_for_period`:
        Registry-projected per-modelo, period-aware permitted-kind policy this
        module binds to :class:`~FilingDeclarationKind`.
    :func:`~application.modelo.amendment_actions.amend_modelo_revision`:
        The composition path that calls this module's guard before building
        the amendment revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.amendment_kind_regime import (
    AmendmentLiabilityDirection,
    classify_amendment_liability_direction,
)
from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...domain.calculations.registry.amendment_regime_policy import resolve_amendment_kind_regime_for_period
from ...domain.calculations.registry.result_casillas import canonical_result_amount, result_disposition_casilla_ids
from ...domain.modelos.filing_record import FilingDeclarationKind
from .action_errors import AmendmentComplementariaLiabilityDecreaseError, AmendmentKindNotPermittedError

__all__ = [
    "assert_amendment_kind_permitted",
    "assert_complementaria_liability_direction_permitted",
    "liability_direction_for_amendment",
]


def assert_amendment_kind_permitted(
    *,
    modelo: str,
    period: Period,
    amendment_kind: FilingDeclarationKind,
) -> None:
    """Refuse ``amendment_kind`` unless the resolved period legally permits it.

    Reads the declared regime from
    :func:`~domain.calculations.registry.amendment_regime_policy.resolve_amendment_kind_regime_for_period`
    for ``modelo`` and ``period`` and checks ``amendment_kind`` against the permitted set. A
    modelo with no declared rectificativa-adoption boundary selects the
    pre-rectificativa vocabulary, narrowed by any dated registry restriction.
    M130/M131 permit only complementaria from their evidenced 2019 editions;
    neither sustitutiva nor rectificativa is admitted for those periods.

    Raises:
        AmendmentKindNotPermittedError: When ``amendment_kind`` is outside the
            resolved period's permitted set. The refusal names both the
            requested kind and the full accepted set.
    """
    regime = resolve_amendment_kind_regime_for_period(modelo, period)
    if amendment_kind.value in regime.permitted_kinds:
        return
    if not regime.permitted_kinds:
        raise AmendmentKindNotPermittedError(
            translated_message="application.modelo.errors.amendment_later_period_only",
            context={
                "modelo": modelo,
                "filing_year": str(period.filing_year),
                "period": period.registry_token,
                "requested_kind": amendment_kind.value,
            },
        )
    accepted = ", ".join(sorted(regime.permitted_kinds))
    raise AmendmentKindNotPermittedError(
        translated_message="application.modelo.errors.amendment_kind_not_permitted",
        context={
            "modelo": modelo,
            "filing_year": str(period.filing_year),
            "period": period.registry_token,
            "requested_kind": amendment_kind.value,
            "accepted_kinds": accepted,
        },
    )


def liability_direction_for_amendment(
    *,
    baseline_result: Decimal,
    corrected_result: Decimal,
) -> AmendmentLiabilityDirection:
    """Classify whether a correction increases, decreases, or leaves liability unchanged.

    Thin, typed wrapper over
    :func:`~core.amendment_kind_regime.classify_amendment_liability_direction` for callers
    inside the modelo application layer. ``baseline_result`` and
    ``corrected_result`` are the modelo's signed final-result casilla value
    before and after the operator's overrides.

    The classification is load-bearing only for pre-rectificativa periods:
    :attr:`~core.amendment_kind_regime.AmendmentLiabilityDirection.INCREASE` is
    ``complementaria`` territory (LGT art. 122.2); ``DECREASE`` is
    ``solicitud de rectificación`` territory (LGT art. 120.3) that a
    self-filed complementaria cannot lawfully carry — see
    :func:`~application.modelo.amendment_actions.amend_modelo_revision`'s pre-rectificativa
    complementaria-direction guard.
    """
    return AmendmentLiabilityDirection(
        classify_amendment_liability_direction(baseline_result=baseline_result, corrected_result=corrected_result),
    )


def _summed_result(
    modelo: str,
    casilla_values: Mapping[CasillaId, Decimal],
    prior_paid_casilla_ids: tuple[CasillaId, ...],
) -> Decimal | None:
    """Sum the modelo's declared final-result casilla(s) from a casilla-value map.

    Returns ``None`` when the modelo has no declared result-disposition spec
    (:func:`result_disposition_casilla_ids`); callers must then skip
    the liability-direction guard rather than compare against a fabricated
    zero baseline.
    """
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is None:
        return None
    result = canonical_result_amount(
        modelo,
        {casilla_id: casilla_values[casilla_id] for casilla_id in result_ids if casilla_id in casilla_values},
    )
    if result is None:
        return None
    if modelo != "130":
        return result
    return result + sum((casilla_values.get(key, Decimal("0")) for key in prior_paid_casilla_ids), Decimal("0"))


def assert_complementaria_liability_direction_permitted(
    *,
    modelo: str,
    period: Period,
    amendment_kind: FilingDeclarationKind,
    baseline_casilla_values: Mapping[CasillaId, Decimal],
    corrected_casilla_values: Mapping[CasillaId, Decimal],
    prior_paid_casilla_ids: tuple[CasillaId, ...] = (),
) -> None:
    """Refuse a pre-rectificativa ``complementaria`` that decreases liability.

    Only load-bearing for a pre-rectificativa period (see
    :func:`~domain.calculations.registry.amendment_regime_policy.resolve_amendment_kind_regime_for_period`):
    once rectificativa
    applies, both directions route through the unified mechanism and this
    guard is a no-op. For a pre-rectificativa period requesting
    ``COMPLEMENTARIA``, sums the modelo's declared final-result casilla(s)
    (:func:`result_disposition_casilla_ids`) before and after the
    operator's overrides and refuses when the correction lowers the declared
    liability — that correction is legally a ``solicitud de rectificación``
    (LGT art. 120.3), not a complementaria (LGT art. 122.2).

    A modelo with no declared result-disposition spec, or a correction that
    does not touch the result casilla(s), is not refused: there is no basis to
    classify a direction, so the guard degrades to a no-op rather than
    fabricating a comparison.

    Raises:
        AmendmentComplementariaLiabilityDecreaseError: When a pre-rectificativa
            complementaria would lower the taxpayer's declared liability.
    """
    if amendment_kind is not FilingDeclarationKind.COMPLEMENTARIA:
        return
    if resolve_amendment_kind_regime_for_period(modelo, period).rectificativa_effective:
        return

    # A complementaria's result is the additional payment. Compare total
    # liability, including the registry-declared earlier same-period payments.
    baseline_result = _summed_result(modelo, baseline_casilla_values, prior_paid_casilla_ids)
    corrected_result = _summed_result(modelo, corrected_casilla_values, prior_paid_casilla_ids)
    if baseline_result is None or corrected_result is None:
        return

    direction = liability_direction_for_amendment(baseline_result=baseline_result, corrected_result=corrected_result)
    if direction is not AmendmentLiabilityDirection.DECREASE:
        return

    raise AmendmentComplementariaLiabilityDecreaseError(
        translated_message="application.modelo.errors.amendment_complementaria_liability_decrease",
        context={
            "modelo": modelo,
            "filing_year": str(period.filing_year),
            "period": period.registry_token,
            "baseline_result": str(baseline_result),
            "corrected_result": str(corrected_result),
        },
    )
