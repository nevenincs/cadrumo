"""The legal limits on the two work-income expenses a filer states, read from the pinned registry.

LIRPF art. 19.2 lets the filer deduct the professional-association dues where membership is a
condition of the job, up to 500 euros a year (RIRPF art. 10), and the legal-defence costs of a
dispute with the employer, up to 300 euros a year. Both limits are dated registry parameters of the
Modelo 100 edition, so verification compares the stated box against the limit in force.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from .formula_runtime_ops import read_parameter

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation
    from .ids import RevisionId
    from .schema import ModeloRevision

__all__ = ["TrabajoExpenseLimits", "trabajo_expense_limits"]


class TrabajoExpenseLimits:
    """The two limits in force on a date, or ``None`` where the edition declares no such limit."""

    __slots__ = ("colegio_profesional", "defensa_juridica")

    def __init__(self, *, colegio_profesional: Decimal | None, defensa_juridica: Decimal | None) -> None:
        """Hold the two limits."""
        self.colegio_profesional = colegio_profesional
        self.defensa_juridica = defensa_juridica


def trabajo_expense_limits(
    modelo_id: str, revision: ModeloRevision, *, operation: PinnedAuthorityOperation, effective_date: date
) -> TrabajoExpenseLimits:
    """Read both limits of ``revision`` of ``modelo_id`` from the pinned ``operation`` on ``effective_date``."""
    declared = {parameter.id for parameter in revision.parameters}
    revision_id: RevisionId = revision.id
    date_context = {"filing_period": effective_date}
    return TrabajoExpenseLimits(
        colegio_profesional=read_parameter(
            modelo_id,
            revision_id,
            "renta-trabajo-colegio-profesional-limite",
            date_context=date_context,
            operation=operation,
        )
        if "renta-trabajo-colegio-profesional-limite" in declared
        else None,
        defensa_juridica=read_parameter(
            modelo_id,
            revision_id,
            "renta-trabajo-defensa-juridica-limite",
            date_context=date_context,
            operation=operation,
        )
        if "renta-trabajo-defensa-juridica-limite" in declared
        else None,
    )
