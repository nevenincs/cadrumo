"""Read-only Modelo 303 fetcher.

Projects a :class:`aeat.remote.RemoteFiling` for the requested
``(modelo="303", period)`` pair into a typed :class:`FilingDetail303`,
extracting the load-bearing VAT-return casillas the reconciliation
engine will need in Phase 3. The fetcher is deliberately a thin
projection over a :class:`aeat.remote.RemoteFilingFetcher` Protocol-
conforming collaborator — the same seam the ADR locks — so the live
path (backed by a real :class:`aeat.auth.AeatSession`) and the unit
tests (backed by a synthetic Protocol-conforming class) share the
same contract.

No state-changing AEAT interaction appears on any code path in this
module; the Layer 3 grep guard in
:mod:`aeat.remote.test_no_write_surface` enforces that structurally.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...formulas import FiscalPeriod
from ...logging import get_logger
from .._protocols import RemoteFilingFetcher
from .._schema import RemoteCasilla, RemoteFiling
from ._filing_detail_303 import FilingDetail303
from ._period import format_aeat_period

_logger = get_logger(__name__)

_MODELO: str = "303"

# Canonical Modelo 303 casilla identifiers that feed the reconciler.
# The mapping pairs the AEAT casilla id with the :class:`FilingDetail303`
# field it populates; it is the single authoritative source of truth
# inside this module so future additions stay reviewable.
_CASILLA_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("27", "total_devengado"),
    ("45", "total_deducir"),
    ("46", "diferencia"),
    ("69", "resultado_liquidacion"),
    ("71", "a_ingresar"),
    ("73", "a_devolver"),
)


def _index_casillas(casillas: Iterable[RemoteCasilla]) -> dict[str, RemoteCasilla]:
    """Return ``{casilla_id: RemoteCasilla}`` for quick lookup."""
    return {c.casilla_id: c for c in casillas}


def project_filing_detail_303(filing: RemoteFiling) -> FilingDetail303:
    """Project a Modelo 303 :class:`RemoteFiling` into :class:`FilingDetail303`.

    Missing casillas — the happy edge case where a quarter has no
    value to report for one of the tracked rows — fall back to
    :data:`Decimal("0")`, matching the record's default value. A
    non-numeric coerced value surfaces as a warning log and the
    field likewise defaults to zero so downstream reconciliation can
    still produce a coherent report.

    Args:
        filing: A :class:`aeat.remote.RemoteFiling` whose ``modelo``
            is ``"303"``. The caller is responsible for filtering
            down to the correct modelo before calling.

    Returns:
        A strict, frozen :class:`FilingDetail303` wrapping ``filing``.
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
            "casilla %s for modelo 303 carries non-decimal value %r; defaulting %s to 0",
            casilla_id,
            value,
            field_name,
        )
    return FilingDetail303.model_validate(payload)


async def fetch(
    fetcher: RemoteFilingFetcher,
    *,
    period: FiscalPeriod,
    use_cache: bool = True,
) -> tuple[FilingDetail303, ...]:
    """Return every :class:`FilingDetail303` AEAT holds for ``period``.

    Args:
        fetcher: A :class:`aeat.remote.RemoteFilingFetcher`-conforming
            collaborator. Production wiring instantiates this from an
            :class:`aeat.auth.AeatSession`; unit tests provide a
            Protocol-conforming Python class that returns pre-built
            :class:`RemoteFiling` tuples.
        period: Typed :class:`aeat.formulas.FiscalPeriod` identifying
            the quarter (or, exceptionally, the annual period) to
            fetch. Conversion to AEAT's wire representation happens
            via :func:`format_aeat_period`.
        use_cache: Passed through to the fetcher; ``True`` (default)
            honours its read-side TTL cache.

    Returns:
        A tuple of :class:`FilingDetail303`, one per
        :class:`RemoteFiling` AEAT returned. The tuple is empty when
        AEAT has no record for ``(modelo=303, period)`` — the
        reconciler interprets that as ``NOT_YET_FOUND``.
    """
    aeat_period = format_aeat_period(period)
    filings = await fetcher.fetch_filing_detail(_MODELO, aeat_period, use_cache=use_cache)
    return tuple(project_filing_detail_303(filing) for filing in filings)


__all__ = ["fetch", "project_filing_detail_303"]
