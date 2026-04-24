"""Read-only Modelo 130 fetcher.

Projects a :class:`aeat.remote.RemoteFiling` for the requested
``(modelo="130", period)`` pair into a typed :class:`FilingDetail130`.
Modelo 130 is the quarterly IRPF direct-estimation pre-payment filing.
The fetcher is a thin projection over a
:class:`aeat.remote.RemoteFilingFetcher` Protocol-conforming
collaborator — no direct Playwright calls and no state-changing AEAT
interaction on any code path.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...formulas import FiscalPeriod
from ...logging import get_logger
from .._protocols import RemoteFilingFetcher
from .._schema import RemoteCasilla, RemoteFiling
from ._filing_detail_130 import FilingDetail130
from ._period import format_aeat_period

_logger = get_logger(__name__)

_MODELO: str = "130"

# Canonical Modelo 130 casilla identifiers feeding the reconciler.
# The IRPF prepayment surface is compact; six numeric casillas cover
# Kent's quarterly filing rhythm. Descriptions live on the record's
# field docstrings so the mapping here stays scannable.
_CASILLA_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("01", "ingresos_computables"),
    ("02", "gastos_deducibles"),
    ("03", "rendimiento_neto"),
    ("06", "pagos_fraccionados_anteriores"),
    ("07", "retenciones_soportadas"),
    ("08", "resultado"),
)


def _index_casillas(casillas: Iterable[RemoteCasilla]) -> dict[str, RemoteCasilla]:
    """Return ``{casilla_id: RemoteCasilla}`` for quick lookup."""
    return {c.casilla_id: c for c in casillas}


def project_filing_detail_130(filing: RemoteFiling) -> FilingDetail130:
    """Project a Modelo 130 :class:`RemoteFiling` into :class:`FilingDetail130`.

    Args:
        filing: A :class:`aeat.remote.RemoteFiling` whose ``modelo``
            is ``"130"``.

    Returns:
        A strict, frozen :class:`FilingDetail130` wrapping ``filing``.
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
            "casilla %s for modelo 130 carries non-decimal value %r; defaulting %s to 0",
            casilla_id,
            value,
            field_name,
        )
    return FilingDetail130.model_validate(payload)


async def fetch(
    fetcher: RemoteFilingFetcher,
    *,
    period: FiscalPeriod,
    use_cache: bool = True,
) -> tuple[FilingDetail130, ...]:
    """Return every :class:`FilingDetail130` AEAT holds for ``period``.

    Args:
        fetcher: A :class:`aeat.remote.RemoteFilingFetcher`-conforming
            collaborator.
        period: Typed :class:`aeat.formulas.FiscalPeriod` identifying
            the quarter. Annual periods are unusual for Modelo 130
            but the formatter handles both shapes.
        use_cache: Passed through to the fetcher; ``True`` (default)
            honours its read-side TTL cache.

    Returns:
        A tuple of :class:`FilingDetail130`, empty when AEAT has no
        record for ``(modelo=130, period)``.
    """
    aeat_period = format_aeat_period(period)
    filings = await fetcher.fetch_filing_detail(_MODELO, aeat_period, use_cache=use_cache)
    return tuple(project_filing_detail_130(filing) for filing in filings)


__all__ = ["fetch", "project_filing_detail_130"]
