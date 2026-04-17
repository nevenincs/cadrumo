"""Detail-page parser for AEAT modelo 390 filings (#168).

Modelo 390 is the annual VAT summary return. The detail page is
layout-compatible with modelo 303 but covers the full calendar year
and always surfaces ``Resultado a compensar`` alongside the main
totals. Because 390 is informational (no payment at submission), the
``Total a ingresar`` / ``Total a devolver`` fields are often absent;
the parser tolerates their absence via
:attr:`FiledModelo.parse_warnings`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl

from ...status import Expediente
from .._models import FiledModelo
from ._common import _RESULTADO_COMPENSAR_RE, build_filed_modelo, soup_of


def parse_modelo_390_detail(
    raw_html: str,
    *,
    expediente: Expediente,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> FiledModelo:
    """Parse a modelo-390 detail page into a :class:`FiledModelo`.

    Args:
        raw_html: Raw detail-page HTML.
        expediente: Upstream :class:`aeat.status.Expediente`.
        source_url: Resolved detail-page URL.
        fetched_at: UTC timestamp the HTML was captured.

    Returns:
        A :class:`FiledModelo` carrying every casilla plus any of
        the three headline totals AEAT prints.

    Raises:
        HistoryParseError: If the HTML shape is unrecognisable.
    """
    soup = soup_of(raw_html)
    return build_filed_modelo(
        expediente=expediente,
        soup=soup,
        source_url=source_url,
        fetched_at=fetched_at,
        resultado_a_compensar_pattern=_RESULTADO_COMPENSAR_RE,
    )
