"""Stand in for the preceding-período turnover reader where a test isolates the Modelo 202 producer's own logic.

The reader itself, against real stores, is proven by
``entrypoints/tests/profile_persistence/test_incn_periodo_anterior_reader.py``.
These stand-ins return what it returns for a profile in a stated situation: one
holding no preceding Modelo 200 and stating no figure for it, one holding it, and
one whose held return disagrees with the stated twelve-month turnover. Whether
the ejercicio's Modelo 200 edition reads the figure at all is taken from the
published registry, as the reader takes it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...modelo.incn_periodo_anterior import (
    INCN_PERIODO_ANTERIOR_BINDING_ID,
    IncnPeriodoAnterior,
    IncnPeriodoAnteriorGap,
    IncnPeriodoAnteriorOrigin,
    IncnPeriodoAnteriorReader,
)

_MODELO_200: Final = "200"
_ANNUAL: Final = "0A"


def _edition(operation: PinnedAuthorityOperation, filing_year: int) -> tuple[str, bool]:
    snapshot = operation.snapshot(
        _MODELO_200, filing_year=filing_year, period=_ANNUAL, grade=RegistryAuthorityGrade.CALCULATION
    )
    return snapshot.revision.id, any(
        binding.id == INCN_PERIODO_ANTERIOR_BINDING_ID for binding in snapshot.revision.bindings
    )


def _located(
    filing_year: int,
    revision_id: str,
    origin: IncnPeriodoAnteriorOrigin,
    *,
    value: Decimal | None = None,
    gap: IncnPeriodoAnteriorGap | None = None,
    held_value: Decimal | None = None,
    twelve_month_statement: Decimal | None = None,
) -> IncnPeriodoAnterior:
    return IncnPeriodoAnterior(
        filing_year=filing_year,
        binding_id=INCN_PERIODO_ANTERIOR_BINDING_ID,
        origin=origin,
        value=value,
        source_modelo=_MODELO_200,
        source_filing_year=filing_year - 1,
        source_period=_ANNUAL,
        revision_id=revision_id,
        gap=gap,
        held_value=held_value,
        twelve_month_statement=twelve_month_statement,
    )


def _not_read(filing_year: int, revision_id: str) -> IncnPeriodoAnterior:
    return IncnPeriodoAnterior(
        filing_year=filing_year,
        binding_id=INCN_PERIODO_ANTERIOR_BINDING_ID,
        origin=IncnPeriodoAnteriorOrigin.UNRESOLVED,
        revision_id=revision_id,
        gap=IncnPeriodoAnteriorGap.NOT_READ_BY_EDITION,
    )


def nothing_held(operation: PinnedAuthorityOperation, filing_year: int) -> IncnPeriodoAnteriorReader:
    """No preceding return held and no figure stated: only a twelve-month turnover can stand."""
    revision_id, reads = _edition(operation, filing_year)

    def read(twelve_month_statement: Decimal | None) -> IncnPeriodoAnterior:
        if not reads:
            return _not_read(filing_year, revision_id)
        if twelve_month_statement is not None:
            return _located(
                filing_year,
                revision_id,
                IncnPeriodoAnteriorOrigin.TWELVE_MONTH_STATEMENT,
                value=twelve_month_statement,
                twelve_month_statement=twelve_month_statement,
            )
        return _located(
            filing_year, revision_id, IncnPeriodoAnteriorOrigin.UNRESOLVED, gap=IncnPeriodoAnteriorGap.NO_RETURN_HELD
        )

    return read


def held_return(operation: PinnedAuthorityOperation, filing_year: int, held: Decimal) -> IncnPeriodoAnteriorReader:
    """The preceding return is held and shows ``held``; a different twelve-month turnover disagrees with it."""
    revision_id, reads = _edition(operation, filing_year)

    def read(twelve_month_statement: Decimal | None) -> IncnPeriodoAnterior:
        if not reads:
            return _not_read(filing_year, revision_id)
        if twelve_month_statement is not None and twelve_month_statement != held:
            return _located(
                filing_year,
                revision_id,
                IncnPeriodoAnteriorOrigin.UNRESOLVED,
                gap=IncnPeriodoAnteriorGap.TWELVE_MONTH_STATEMENT_DISAGREES,
                held_value=held,
                twelve_month_statement=twelve_month_statement,
            )
        return _located(
            filing_year,
            revision_id,
            IncnPeriodoAnteriorOrigin.HELD_RETURN,
            value=held,
            twelve_month_statement=twelve_month_statement,
        )

    return read


def reads_preceding_turnover(operation: PinnedAuthorityOperation, filing_year: int) -> bool:
    """Whether the ejercicio's Modelo 200 edition selects a rate by the preceding período's turnover."""
    return _edition(operation, filing_year)[1]


__all__ = ["held_return", "nothing_held", "reads_preceding_turnover"]
