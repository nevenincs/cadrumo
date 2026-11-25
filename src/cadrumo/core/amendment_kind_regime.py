"""Period-aware amendment mechanics driven by a registry policy projection.

The registry projection owns the dated procedure vocabulary and adoption
boundaries. This core module only compares a period with a supplied policy and
returns the corresponding regime; it deliberately contains no legal catalogue
or model-specific boundary defaults.

See Also:
    :mod:`cadrumo.domain.calculations.registry.amendment_regime_policy`:
        Typed resolver for the selected governed policy fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # ``Period`` is used only as a type annotation. Keeping the import out of
    # runtime avoids loading its transitive validation dependencies here.
    from _typeshed import SupportsAllComparisons

    from .period import Period


class AmendmentLiabilityDirection(StrEnum):
    """Direction of an amendment's effect on the taxpayer's declared liability.

    Under the pre-rectificativa dual regime, the direction determines which
    of the two legally-distinct procedures applies: an ``INCREASE`` (the
    corrected resultado raises the tax due, or lowers a requested devolución)
    is a ``complementaria`` (LGT art. 122.2); a ``DECREASE`` (the corrected
    resultado lowers the tax due, or raises a requested devolución) requires
    the ``solicitud de rectificación`` procedure (LGT art. 120.3) rather than
    a self-filed complementaria. Post-rectificativa, the direction no longer
    selects a different legal mechanism (both raise and lower route through
    the unified rectificativa), so this classification is only load-bearing
    for pre-rectificativa periods.
    """

    INCREASE = "increase"
    DECREASE = "decrease"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class AmendmentKindRestriction:
    """Dated intersection supplied by the validated registry policy."""

    effective_from: date
    permitted_kinds: frozenset[str]


@dataclass(frozen=True)
class AmendmentRegimePolicy:
    """Registry-projected amendment policy consumed by core mechanics.

    The core layer deliberately owns only the date comparison and regime
    selection mechanics.  Procedure vocabulary and adoption boundaries are
    supplied by the selected, validated registry fact through this typed
    projection; an absent or malformed projection therefore fails closed at
    the registry boundary instead of falling back to a Python catalogue.
    """

    rectificativa_effective_from: Mapping[str, date]
    pre_rectificativa_kinds: frozenset[str]
    post_rectificativa_kinds: frozenset[str]
    later_period_adjustment_from: Mapping[str, date] = field(default_factory=dict[str, date])
    """Modelos whose filed return can never be amended, from the date their adjustment rule applies.

    Their corrections belong to a later period's return, so no amendment kind exists.
    """
    kind_restrictions: Mapping[str, AmendmentKindRestriction] = field(
        default_factory=dict[str, AmendmentKindRestriction]
    )


@dataclass(frozen=True)
class AmendmentKindRegime:
    """The codified amendment-kind regime resolved for one (modelo, period).

    Attributes:
        permitted_kinds: The closed set of
            :class:`~FilingDeclarationKind`
            string values legally available for this modelo and period.
            Empty when the modelo adjusts a filed period only through a later
            period's return. Otherwise the registry's pre/post vocabulary is
            intersected with any effective restriction for this modelo.
            A restriction can remove kinds but cannot grant a procedure
            absent from the selected regime.
        rectificativa_effective: Whether the resolved period is within the
            modelo's rectificativa-supported window (``True``) or the
            pre-rectificativa dual regime still applies (``False``).
    """

    permitted_kinds: frozenset[str]
    rectificativa_effective: bool


def resolve_amendment_kind_regime(
    modelo: str,
    period: Period,
    *,
    policy: AmendmentRegimePolicy,
    rectificativa_effective_from: Mapping[str, date] | None = None,
) -> AmendmentKindRegime:
    """Resolve the codified amendment-kind regime for ``modelo`` at ``period``.

    Returns an :class:`AmendmentKindRegime` naming the legally-permitted
    :class:`~FilingDeclarationKind` string
    values for this ``(modelo, period)`` pair. A modelo with no registry-
    declared boundary selects the projected pre-rectificativa vocabulary.
    Effective restrictions only narrow the selected vocabulary; the core
    never invents procedure support.

    For a period with no calendar date span (an instalment clave or an
    extended/ad-hoc form), the resolution falls back to
    ``filing_year >= <the modelo's boundary year>`` using the boundary
    date's year, since no calendar comparison is possible for those forms.

    ``policy`` is the typed projection of the selected amendment-regime fact.
    ``rectificativa_effective_from`` is an explicit mechanics seam for a
    caller that has already projected an alternate boundary mapping; it does
    not provide a default policy or a fallback vocabulary.
    """
    adjustment_boundary = policy.later_period_adjustment_from.get(modelo)
    if adjustment_boundary is not None and _period_reaches(period, adjustment_boundary):
        return AmendmentKindRegime(permitted_kinds=frozenset(), rectificativa_effective=False)
    table = (
        policy.rectificativa_effective_from if rectificativa_effective_from is None else rectificativa_effective_from
    )
    boundary = table.get(modelo)
    rectificativa_effective = boundary is not None and _period_reaches(period, boundary)
    permitted_kinds = policy.post_rectificativa_kinds if rectificativa_effective else policy.pre_rectificativa_kinds
    restriction = policy.kind_restrictions.get(modelo)
    if restriction is not None and _period_reaches(period, restriction.effective_from):
        permitted_kinds = permitted_kinds & restriction.permitted_kinds
    return AmendmentKindRegime(
        permitted_kinds=permitted_kinds,
        rectificativa_effective=rectificativa_effective,
    )


def _period_reaches(period: Period, boundary: date) -> bool:
    if period.has_date_span():
        return period.end_date >= boundary
    return period.filing_year >= boundary.year


def classify_amendment_liability_direction(
    *,
    baseline_result: SupportsAllComparisons,
    corrected_result: SupportsAllComparisons,
) -> str:
    """Classify whether a correction increases, decreases, or leaves liability unchanged.

    ``baseline_result`` and ``corrected_result`` are the modelo's signed final
    result casilla value (a positive value means "a ingresar" tax due; a
    negative value means a credit or refund position, modelo-dependent) before
    and after the operator's overrides. An increase in the signed result (a
    higher amount to pay, or a lower credit/refund) is
    :attr:`~core.amendment_kind_regime.AmendmentLiabilityDirection.INCREASE` (LGT art. 122.2,
    complementaria territory); a decrease is
    :attr:`~core.amendment_kind_regime.AmendmentLiabilityDirection.DECREASE` (LGT art. 120.3, solicitud de
    rectificación territory pre-unification). Equal values are
    :attr:`~core.amendment_kind_regime.AmendmentLiabilityDirection.UNCHANGED`.

    Accepts any ``Decimal``-comparable numeric type so callers do not need to
    import :mod:`decimal` solely to call this classifier.
    """
    if corrected_result > baseline_result:
        return AmendmentLiabilityDirection.INCREASE
    if corrected_result < baseline_result:
        return AmendmentLiabilityDirection.DECREASE
    return AmendmentLiabilityDirection.UNCHANGED


__all__ = [
    "AmendmentKindRegime",
    "AmendmentKindRestriction",
    "AmendmentLiabilityDirection",
    "AmendmentRegimePolicy",
    "classify_amendment_liability_direction",
    "resolve_amendment_kind_regime",
]
