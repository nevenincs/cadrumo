"""Per-modelo, period-aware autoliquidación amendment-kind regime.

AEAT's amendment mechanism for a self-assessment (autoliquidación) changed
over time. Before the reform, a correction that raised the tax due filed as
a ``complementaria`` (LGT art. 122.2, ``ley-58-2003:art-122``) while a
correction that lowered it required a separate ``solicitud de rectificación``
procedure (LGT art. 120.3, ``ley-58-2003:art-120``). RD-ley 13/2023 plus each
tax's implementing orden unified both into a single ``autoliquidación
rectificativa`` (LGT art. 120.4) that may raise OR lower the resultado — but
only from the period each modelo's own orden establishes; earlier periods are
still governed by the dual complementaria/rectificación regime.

This module codifies, per modelo, the filing period from which the
rectificativa mechanism applies, grounded in the bundled AEAT Diseño de
Registros and manual corpus:

- **M303** (IVA autoliquidación): the rectificativa casillas (fichero-BOE
  position 392 ``autoliq_rectificativa`` onward) appear starting with the
  diseño "ejercicio 2024 a partir de periodos 09 y 3T y siguientes"; the
  prior diseño "ejercicio 2024 hasta periodos 08 y 2T" carries no rectificativa
  fields. The boundary is therefore filing_year 2024, period 09 (monthly) or
  3T (quarterly) onward — every subsequent period and year uses rectificativa.
- **M100** (IRPF Renta): the Manual Práctico de Renta states the rectificativa
  became the general correction mechanism "para los períodos impositivos 2024
  y siguientes", with effective application from Orden HAC/242/2025 (14 March
  2025); the registry casilla ``0669`` (2024 revision, "discrepancia de
  criterio administrativo... autoliquidación rectificativa") corroborates M100
  carries rectificativa support from filing_year 2024.
- **M200** (Impuesto sobre Sociedades): the ejercicio-2024 registry
  revision carries rectificativa casillas (``0497``/``0499``/``0508``/``0509``/
  ``0513``/``0519``/etc.), so M200 supports rectificativa from filing_year
  2024 onward.
- **M130/M131** (IRPF pagos fraccionados): the bundled diseño de registros
  for M130 stops at "ejercicios 2019 y siguientes" with no rectificativa
  fields at all, and the registry carries only that single revision. No
  bundled AEAT source grounds a specific rectificativa-adoption period for
  M130/M131, so this module conservatively reports them as NOT YET
  supporting rectificativa — every period continues to route through the
  dual complementaria/solicitud-de-rectificación regime — until a bundled
  AEAT diseño or orden grounds an effective period
  (`aeat-calculation-grounding`).

A modelo absent from :data:`_RECTIFICATIVA_EFFECTIVE_FROM` has no codified
regime at all: :func:`permitted_amendment_kind_values` falls back to the
complementaria/sustitutiva pair for every period, never asserting rectificativa
support that no bundled source confirms.

See Also:
    :func:`~application.modelo._amendment_kind_resolution.assert_amendment_kind_permitted`:
        Application-layer guard that binds this table to
        :class:`~CalculationRevisionAmendmentKind` and
        refuses an operator-requested kind the period does not permit.
    :class:`~CalculationRevisionAmendmentKind`:
        The domain enum this module's string values back.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from ._modelo import Modelo

if TYPE_CHECKING:
    # Deferred: ``._period`` transitively imports ``.errors``, which imports
    # ``core.classification``, which imports ``STRICT_FROZEN_CONFIG`` back from
    # the ``core`` package facade (``._models``). Importing ``Period`` eagerly
    # here would run that chain before ``core/__init__.py`` has bound
    # ``STRICT_FROZEN_CONFIG`` (this module sorts alphabetically before
    # ``._models`` in the facade's import block), reproducing the partial-
    # initialization ``ImportError`` the facade's ordering otherwise avoids.
    # ``Period`` is used only as a type annotation here, so the deferred import
    # is sufficient and the module needs no runtime binding of the name.
    from _typeshed import SupportsAllComparisons

    from ._period import Period


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
class AmendmentKindRegime:
    """The codified amendment-kind regime resolved for one (modelo, period).

    Attributes:
        permitted_kinds: The closed set of
            :class:`~CalculationRevisionAmendmentKind`
            string values legally available for this modelo and period.
            ``"sustitutiva"`` is always permitted (a material restatement is
            never barred by the rectificativa timeline); ``"rectificativa"``
            is permitted only once the modelo's own effective period is
            reached; ``"complementaria"`` is permitted only before that
            point (once rectificativa applies, it *replaces* complementaria
            for the modelo's ordinary corrective filings — see
            ``CalculationRevisionAmendmentKind.RECTIFICATIVA``'s docstring).
        rectificativa_effective: Whether the resolved period is within the
            modelo's rectificativa-supported window (``True``) or the
            pre-rectificativa dual regime still applies (``False``).
    """

    permitted_kinds: frozenset[str]
    rectificativa_effective: bool


_COMPLEMENTARIA: str = "complementaria"
_SUSTITUTIVA: str = "sustitutiva"
_RECTIFICATIVA: str = "rectificativa"

#: Pre-rectificativa regime: only the dual complementaria/sustitutiva pair.
_PRE_RECTIFICATIVA_KINDS: frozenset[str] = frozenset({_COMPLEMENTARIA, _SUSTITUTIVA})

#: Post-rectificativa regime: rectificativa replaces complementaria as the
#: modelo's unified ordinary-correction mechanism; sustitutiva remains for
#: material restatements.
_POST_RECTIFICATIVA_KINDS: frozenset[str] = frozenset({_RECTIFICATIVA, _SUSTITUTIVA})


#: Per-modelo rectificativa effective-period boundary, grounded in the
#: bundled AEAT Diseño de Registros / manual corpus (see module docstring).
#: The boundary is expressed as the earliest *period end date* (inclusive)
#: from which the modelo's rectificativa mechanism applies; every period
#: whose ``Period.end_date`` falls on or after this date is post-rectificativa.
#: A modelo absent from this table has no codified rectificativa-adoption
#: date and is therefore never treated as rectificativa-effective by
#: :func:`permitted_amendment_kind_values`.
_RECTIFICATIVA_EFFECTIVE_FROM: dict[str, date] = {
    # M303: diseño "ejercicio 2024 a partir de periodos 09 y 3T y siguientes"
    # introduces the rectificativa fields; period 09 and 3T both end on
    # 2024-09-30 (monthly September / calendar Q3), the shared boundary date.
    Modelo.M303: date(2024, 9, 30),
    # M100: Manual Práctico de Renta 2025 — rectificativa is the general IRPF
    # correction mechanism "para los períodos impositivos 2024 y siguientes"
    # (effective application from Orden HAC/242/2025, 14 March 2025); the
    # registry's 2024 revision carries the rectificativa discrepancia-de-
    # criterio casilla (0669). M100's revisions are single filing years, so
    # the boundary is simply the close of filing_year 2024 (annual, 0A).
    Modelo.M100: date(2024, 12, 31),
    # M200 (Impuesto sobre Sociedades): the ejercicio-2024 registry
    # revision carries rectificativa casillas throughout its "liquidacion_iv"
    # / "rectificativa" sections. M200's revision windows are annual.
    Modelo.M200: date(2024, 12, 31),
}


def modelo_has_codified_amendment_regime(modelo: str) -> bool:
    """Return whether ``modelo`` has a bundled-source-grounded rectificativa boundary.

    A modelo without a codified boundary (e.g. M130/M131, whose bundled
    diseño de registros carries no rectificativa fields) is never reported as
    rectificativa-effective; :func:`permitted_amendment_kind_values` returns
    the pre-rectificativa complementaria/sustitutiva pair for every period.
    """
    return modelo in _RECTIFICATIVA_EFFECTIVE_FROM


def resolve_amendment_kind_regime(
    modelo: str,
    period: Period,
    *,
    rectificativa_effective_from: Mapping[str, date] | None = None,
) -> AmendmentKindRegime:
    """Resolve the codified amendment-kind regime for ``modelo`` at ``period``.

    Returns an :class:`AmendmentKindRegime` naming the legally-permitted
    :class:`~CalculationRevisionAmendmentKind` string
    values for this ``(modelo, period)`` pair. A modelo with no codified
    boundary (:func:`modelo_has_codified_amendment_regime` is ``False``)
    always resolves to the pre-rectificativa pair, never asserting
    rectificativa support no bundled source confirms.

    For a period with no calendar date span (an instalment clave or an
    extended/ad-hoc form), the resolution falls back to
    ``filing_year >= <the modelo's boundary year>`` using the boundary
    date's year, since no calendar comparison is possible for those forms.

    ``rectificativa_effective_from`` overrides the boundary table, so a caller
    holding boundaries from a better authority can supply them without this
    module reaching for one. ``core`` cannot read the registry itself: the
    registry is built on ``core``, so the derivation would have to live outside
    and be injected here.

    That derivation does not exist yet, and the reason is a registry gap rather
    than a layering one. The registry does not declare rectificativa adoption as
    a first-class fact; it is only inferable from three unrelated incidental
    spellings -- a ``rectificativa`` section token on Modelo 200, an
    ``amendment_evidence.is_rectificativa`` export producer key on Modelo 303,
    and the ``irpf_discrepancia_criterio_administrativo`` semantic role on
    Modelo 100 casilla 0669. A detector spanning all three would encode that
    mapping in Python, which is the transcription this table already is. Until a
    revision can DECLARE its amendment regime, the table below stays, and its
    per-entry comments are its grounding.
    """
    table = _RECTIFICATIVA_EFFECTIVE_FROM if rectificativa_effective_from is None else rectificativa_effective_from
    boundary = table.get(modelo)
    if boundary is None:
        return AmendmentKindRegime(permitted_kinds=_PRE_RECTIFICATIVA_KINDS, rectificativa_effective=False)

    if period.has_date_span():
        rectificativa_effective = period.end_date >= boundary
    else:
        rectificativa_effective = period.filing_year >= boundary.year

    if rectificativa_effective:
        return AmendmentKindRegime(permitted_kinds=_POST_RECTIFICATIVA_KINDS, rectificativa_effective=True)
    return AmendmentKindRegime(permitted_kinds=_PRE_RECTIFICATIVA_KINDS, rectificativa_effective=False)


def permitted_amendment_kind_values(modelo: str, period: Period) -> frozenset[str]:
    """Return the closed set of legally-permitted amendment-kind string values.

    Thin convenience wrapper over :func:`resolve_amendment_kind_regime` for
    callers that only need the permitted set (e.g. rendering an accepted-value
    list in a refusal message).
    """
    return resolve_amendment_kind_regime(modelo, period).permitted_kinds


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
    :attr:`~core.AmendmentLiabilityDirection.INCREASE` (LGT art. 122.2,
    complementaria territory); a decrease is
    :attr:`~core.AmendmentLiabilityDirection.DECREASE` (LGT art. 120.3, solicitud de
    rectificación territory pre-unification). Equal values are
    :attr:`~core.AmendmentLiabilityDirection.UNCHANGED`.

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
    "AmendmentLiabilityDirection",
    "classify_amendment_liability_direction",
    "modelo_has_codified_amendment_regime",
    "permitted_amendment_kind_values",
    "resolve_amendment_kind_regime",
]
