"""Period-aware amendment-kind resolution and the liability-increase guard.

AEAT's amendment mechanism for a self-assessment changed over time (see
:mod:`~core._amendment_kind_regime` for the full grounding). Before the
``autoliquidación rectificativa`` unification, a correction that raised the
tax due filed as a ``complementaria`` (LGT art. 122.2) while a correction
that lowered it required the separate ``solicitud de rectificación``
procedure (LGT art. 120.3) — a self-filed complementaria cannot lawfully
lower a taxpayer's own declared liability. This module is the single place
that:

* refuses an operator-requested
  :class:`~domain.modelos.CalculationRevisionAmendmentKind` that the
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
    :func:`~core.resolve_amendment_kind_regime`:
        Declared per-modelo, period-aware permitted-kind table this module
        binds to :class:`~domain.modelos.CalculationRevisionAmendmentKind`.
    :func:`~application.modelo.amend_modelo_revision`:
        The composition path that calls this module's guard before building
        the amendment revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import (
    AmendmentLiabilityDirection,
    CasillaId,
    Period,
    classify_amendment_liability_direction,
    resolve_amendment_kind_regime,
    result_disposition_casilla_ids,
)
from ...domain.modelos.calculation_revision import CalculationRevisionAmendmentKind
from ._action_errors import AmendmentComplementariaLiabilityDecreaseError, AmendmentKindNotPermittedError

__all__ = [
    "assert_amendment_kind_permitted",
    "assert_complementaria_liability_direction_permitted",
    "liability_direction_for_amendment",
]


def assert_amendment_kind_permitted(
    *,
    modelo: str,
    period: Period,
    amendment_kind: CalculationRevisionAmendmentKind,
) -> None:
    """Refuse ``amendment_kind`` unless the resolved period legally permits it.

    Reads the declared regime from
    :func:`~core.resolve_amendment_kind_regime` for ``modelo`` and
    ``period`` and checks ``amendment_kind`` against the permitted set. A
    modelo with no declared rectificativa-adoption boundary (e.g. M130/M131,
    which carry no bundled rectificativa grounding) always resolves to the
    pre-rectificativa complementaria/sustitutiva pair, so requesting
    ``rectificativa`` for such a modelo is refused at every period until a
    bundled AEAT source grounds an effective date.

    Raises:
        AmendmentKindNotPermittedError: When ``amendment_kind`` is outside the
            resolved period's permitted set. The refusal names both the
            requested kind and the full accepted set.
    """
    regime = resolve_amendment_kind_regime(modelo, period)
    if amendment_kind.value in regime.permitted_kinds:
        return
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
    :func:`~core.classify_amendment_liability_direction` for callers
    inside the modelo application layer. ``baseline_result`` and
    ``corrected_result`` are the modelo's signed final-result casilla value
    before and after the operator's overrides.

    The classification is load-bearing only for pre-rectificativa periods:
    :attr:`~core.AmendmentLiabilityDirection.INCREASE` is
    ``complementaria`` territory (LGT art. 122.2); ``DECREASE`` is
    ``solicitud de rectificación`` territory (LGT art. 120.3) that a
    self-filed complementaria cannot lawfully carry — see
    :func:`~application.modelo.amend_modelo_revision`'s pre-rectificativa
    complementaria-direction guard.
    """
    return AmendmentLiabilityDirection(
        classify_amendment_liability_direction(baseline_result=baseline_result, corrected_result=corrected_result),
    )


def _summed_result(modelo: str, casilla_values: Mapping[CasillaId, Decimal]) -> Decimal | None:
    """Sum the modelo's declared final-result casilla(s) from a casilla-value map.

    Returns ``None`` when the modelo has no declared result-disposition spec
    (:func:`~core.result_disposition_casilla_ids`); callers must then skip
    the liability-direction guard rather than compare against a fabricated
    zero baseline.
    """
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is None:
        return None
    return sum((casilla_values.get(casilla_id, Decimal("0")) for casilla_id in result_ids), Decimal("0"))


def assert_complementaria_liability_direction_permitted(
    *,
    modelo: str,
    period: Period,
    amendment_kind: CalculationRevisionAmendmentKind,
    baseline_casilla_values: Mapping[CasillaId, Decimal],
    corrected_casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    """Refuse a pre-rectificativa ``complementaria`` that decreases liability.

    Only load-bearing for a pre-rectificativa period (see
    :func:`~core.resolve_amendment_kind_regime`): once rectificativa
    applies, both directions route through the unified mechanism and this
    guard is a no-op. For a pre-rectificativa period requesting
    ``COMPLEMENTARIA``, sums the modelo's declared final-result casilla(s)
    (:func:`~core.result_disposition_casilla_ids`) before and after the
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
    if amendment_kind is not CalculationRevisionAmendmentKind.COMPLEMENTARIA:
        return
    if resolve_amendment_kind_regime(modelo, period).rectificativa_effective:
        return

    baseline_result = _summed_result(modelo, baseline_casilla_values)
    corrected_result = _summed_result(modelo, corrected_casilla_values)
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
