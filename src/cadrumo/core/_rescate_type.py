"""The operator's plan-de-pensiones capital-rescate type classification.

A plan-de-pensiones capital rescate under LIRPF Disposición Transitoria 12ª is
either *total* (the whole accumulated capital drawn at once) or *parcial*
(staged partial withdrawals of the same contingency). The distinction is a
guidance and provenance signal, NOT an arithmetic fork: the 40% DT 12ª reducción
applies to the pre-2007 share of whatever amount is percibida regardless of type
(the type does not change
:func:`~domain.modelos.compute_dt12_reduccion_plan_pensiones`). It changes
the advisory the app can phrase — a total rescate is a single apartado-3 window
check, while a parcial rescate warns that every partial cobro of one contingency
shares the single window (measured once from the contingencia year) and that a
mixed capital/renta rescate may forfeit the régimen.

The exported :class:`RescateType` closed value set is declared as a
:class:`enum.StrEnum` in ``core`` per the core-authority discipline (closed axes
live in ``core/``, hydrated at boundaries, asserted as members in tests). It is
the operator-input sibling of the DT 12ª pension shortcut amounts consumed by
:func:`application.modelo.apply_calculation_shortcut_inputs`.
"""

from __future__ import annotations

from enum import StrEnum


class RescateType(StrEnum):
    """The plan-de-pensiones capital-rescate type (LIRPF DT 12ª guidance axis).

    Attributes:
        TOTAL: The whole accumulated capital is rescued at once — a single
            apartado-3 time-window eligibility check applies.
        PARCIAL: Staged partial withdrawals of the same contingency. Every
            partial cobro shares the single apartado-3 window measured once from
            the contingencia year (it does not restart per withdrawal), and a
            mixed capital/renta rescate may forfeit the transitional régimen.
    """

    TOTAL = "total"
    PARCIAL = "parcial"


__all__ = ["RescateType"]
