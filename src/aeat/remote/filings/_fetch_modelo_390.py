"""Read-only Modelo 390 fetcher.

Projects a :class:`aeat.remote.RemoteFiling` for the requested
``(modelo="390", period)`` pair into a typed :class:`FilingDetail390`.
Modelo 390 is the annual VAT summary filing; AEAT keys it by the bare
year (``"2025"``) rather than by quarter.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...formulas import FiscalPeriod
from ...logging import get_logger
from .._protocols import RemoteFilingFetcher
from .._schema import RemoteCasilla, RemoteFiling
from ._filing_detail_390 import FilingDetail390
from ._period import format_aeat_period

_logger = get_logger(__name__)

_MODELO: str = "390"

# Canonical Modelo 390 casilla identifiers tracked by the reconciler.
# Values are the annual totals the ruleset engine already computes;
# the mapping here mirrors the FilingDetail390 field declarations.
_CASILLA_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("99", "total_bases_devengado"),
    ("108", "total_cuotas_devengadas"),
    ("511", "total_cuotas_deducibles"),
    ("658", "resultado_liquidacion_anual"),
    ("108BIS", "volumen_operaciones"),
)


def _index_casillas(casillas: Iterable[RemoteCasilla]) -> dict[str, RemoteCasilla]:
    """Return ``{casilla_id: RemoteCasilla}`` for quick lookup."""
    return {c.casilla_id: c for c in casillas}


def project_filing_detail_390(filing: RemoteFiling) -> FilingDetail390:
    """Project a Modelo 390 :class:`RemoteFiling` into :class:`FilingDetail390`.

    Args:
        filing: A :class:`aeat.remote.RemoteFiling` whose ``modelo``
            is ``"390"``.

    Returns:
        A strict, frozen :class:`FilingDetail390` wrapping ``filing``.
        Missing casillas fall back to the record's :data:`Decimal("0")`
        default; non-decimal coerced values surface as a warning log
        and likewise default to zero.
    """
    indexed = _index_casillas(filing.casillas)
    payload: dict[str, object] = {"filing": filing}
    for casilla_id, field_name in _CASILLA_FIELD_MAP:
        casilla = indexed.get(casilla_id)
        if casilla is None:
            continue
        value = casilla.coerced_value
        if isinstance(value, Decimal):
            payload[field_name] = value
            continue
        _logger.warning(
            "casilla %s for modelo 390 carries non-decimal value %r; defaulting %s to 0",
            casilla_id,
            value,
            field_name,
        )
    return FilingDetail390.model_validate(payload)


async def fetch(
    fetcher: RemoteFilingFetcher,
    *,
    period: FiscalPeriod,
    use_cache: bool = True,
) -> tuple[FilingDetail390, ...]:
    """Return every :class:`FilingDetail390` AEAT holds for ``period``.

    Args:
        fetcher: A :class:`aeat.remote.RemoteFilingFetcher`-conforming
            collaborator.
        period: Typed :class:`aeat.formulas.FiscalPeriod` identifying
            the exercise year. Callers pass ``FiscalPeriod(year=YYYY,
            quarter=None)`` for the annual summary.
        use_cache: Passed through to the fetcher; ``True`` (default)
            honours its read-side TTL cache.

    Returns:
        A tuple of :class:`FilingDetail390`, empty when AEAT has no
        record for ``(modelo=390, period)``.
    """
    aeat_period = format_aeat_period(period)
    filings = await fetcher.fetch_filing_detail(_MODELO, aeat_period, use_cache=use_cache)
    return tuple(project_filing_detail_390(filing) for filing in filings)


__all__ = ["fetch", "project_filing_detail_390"]
