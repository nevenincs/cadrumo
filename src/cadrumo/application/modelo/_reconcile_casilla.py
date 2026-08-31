"""Casilla-level divergence detection between a computed revision and a filed declaration.

``detect_casilla_divergences`` is the typed, pure comparison primitive this
module contributes to :mod:`~application.modelo.reconciliation`: given the
canonical ``revision.casilla_values`` a work unit already persisted (the same
values the calculate path, the result summary, and the export surface render,
per ``aeat-calculation-aggregation``) and the per-casilla values a
filed declaration printed, it classifies every disagreement into one of three
closed :class:`CasillaDivergenceKind` categories — ``value_mismatch`` (both
sides declare the casilla but the amounts disagree beyond tolerance),
``missing_in_filed`` (the computed revision declares the casilla but the filed
declaration omitted it), and ``extra_in_filed`` (the filed declaration prints a
casilla the computed revision never resolved a value for). The comparison is
scoped to the registry's own reconciliation policy
(:meth:`~domain.calculations.registry.RegistrySnapshot.verification_policy`)
so the compared set is declared registry data, never an ad hoc casilla list.
The canonical after-filing reconcile flow owns this comparison.

This module is intentionally free of any PDF-parsing, work-unit, or
bucket-event dependency: it is a pure function over two ``{casilla_id: Decimal}``
mappings plus a tolerance, so it can be tested and reused without a persisted
work unit, a registry snapshot, or a parsed declaración.

See Also:
    :mod:`~application.modelo.reconciliation`
        Reconciliation workflow that loads work-unit state and delegates
        casilla comparison to this pure primitive.
    :class:`~CalculationRevision`
        Persisted computed revision whose ``casilla_values`` are compared.
    :class:`~domain.calculations.registry.RegistryVerificationPolicy`
        Registry-declared scope and tolerance used before divergences are
        surfaced.
    :class:`~adapters.inbound.pdf.ExtractedCasilla`
        Parsed declaration row shape that feeds the filed-value mapping.
    :class:`CasillaDivergence`
        Typed row returned for each surfaced disagreement.
    :class:`CasillaDivergenceKind`
        Closed divergence taxonomy emitted by the comparison.
    :func:`detect_casilla_divergences`
        Pure comparison entry point exported by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class CasillaDivergenceKind(StrEnum):
    """Closed category for one :class:`CasillaDivergence`.

    ``VALUE_MISMATCH`` — both the computed revision and the filed declaration
    declare the casilla but the printed amount diverges from the computed
    amount beyond tolerance. ``MISSING_IN_FILED`` — the computed revision
    resolved a value for the casilla but the filed declaration did not print it.
    ``EXTRA_IN_FILED`` — the filed declaration printed a casilla the computed
    revision never resolved a value for.
    """

    VALUE_MISMATCH = "value_mismatch"
    MISSING_IN_FILED = "missing_in_filed"
    EXTRA_IN_FILED = "extra_in_filed"


class CasillaDivergence(BaseModel):
    """One disagreement between a computed revision and a filed declaration.

    The canonical per-casilla divergence carrier. A surface needing to say
    "this casilla changed" reuses this rather than declaring its own record --
    a weaker carrier holding only ids, without the values or the kind, was
    added and reverted once already.

    ``computed_value`` / ``filed_value`` are ``None`` exactly when the
    corresponding side did not carry a value for ``casilla_id`` (a
    ``MISSING_IN_FILED`` divergence carries ``filed_value=None``; an
    ``EXTRA_IN_FILED`` divergence carries ``computed_value=None``). ``delta`` is
    the signed ``filed_value - computed_value`` when both sides carry a value,
    otherwise ``None`` — there is no meaningful delta when one side is absent.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    kind: CasillaDivergenceKind
    computed_value: Decimal | None = None
    filed_value: Decimal | None = None
    delta: Decimal | None = None


def detect_casilla_divergences(
    *,
    computed: Mapping[CasillaId, Decimal],
    filed: Mapping[CasillaId, Decimal],
    scope: Mapping[CasillaId, object] | None = None,
    tolerance: Decimal = Decimal("0"),
) -> tuple[CasillaDivergence, ...]:
    """Classify every casilla-level disagreement between ``computed`` and ``filed``.

    Args:
        computed: Canonical ``{casilla_id: value}`` read from the persisted
            :class:`~CalculationRevision`
            (``revision.casilla_values``).
        filed: ``{casilla_id: value}`` printed on the filed declaration, decoded
            from the declaration parser's
            :class:`~adapters.inbound.pdf.ExtractedCasilla` rows.
        scope: Optional casilla-id-to-anything mapping restricting comparison to
            its keys (typically the registry's ``verification_policy()``
            ``computed_casilla_ids``). When supplied, both ``computed`` and
            ``filed`` are filtered to this key set before comparison, so a
            casilla the registry does not reconcile never surfaces a divergence.
            When omitted, every casilla id present on either side is compared
            (the union of both key sets).
        tolerance: Maximum absolute delta (in the modelo's currency, typically
            EUR) that does not surface a ``VALUE_MISMATCH``. THE REGISTRY IS THE
            AUTHORITY FOR THIS VALUE and publishes it per revision: resolve it
            with ``snapshot.verification_policy().tolerance`` and pass it. The
            default is exact equality rather than a cent because the registry's
            own schema default is ``0.00`` and its policy fold takes the
            STRICTEST tolerance across a revision's expectations — so a caller
            that omits this argument gets the strictest reading rather than a
            more permissive one it never chose. A revision genuinely rounding to
            the cent declares that, and passing its published value is what
            honours it.

    Returns:
        A tuple of :class:`CasillaDivergence` rows, one per casilla id that
        diverges, ordered by ascending ``casilla_id`` for deterministic output.
        Empty when every compared casilla agrees within tolerance.
    """
    ids = set(scope) if scope is not None else set(computed) | set(filed)
    divergences: list[CasillaDivergence] = []
    for casilla_id in sorted(ids):
        computed_value = computed.get(casilla_id)
        filed_value = filed.get(casilla_id)
        if computed_value is None and filed_value is None:
            continue
        if computed_value is None:
            divergences.append(
                CasillaDivergence(
                    casilla_id=casilla_id,
                    kind=CasillaDivergenceKind.EXTRA_IN_FILED,
                    computed_value=None,
                    filed_value=filed_value,
                    delta=None,
                ),
            )
            continue
        if filed_value is None:
            divergences.append(
                CasillaDivergence(
                    casilla_id=casilla_id,
                    kind=CasillaDivergenceKind.MISSING_IN_FILED,
                    computed_value=computed_value,
                    filed_value=None,
                    delta=None,
                ),
            )
            continue
        delta = filed_value - computed_value
        if abs(delta) <= tolerance:
            continue
        divergences.append(
            CasillaDivergence(
                casilla_id=casilla_id,
                kind=CasillaDivergenceKind.VALUE_MISMATCH,
                computed_value=computed_value,
                filed_value=filed_value,
                delta=delta,
            ),
        )
    return tuple(divergences)


__all__ = [
    "CasillaDivergence",
    "CasillaDivergenceKind",
    "detect_casilla_divergences",
]
