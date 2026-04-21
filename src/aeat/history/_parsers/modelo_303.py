"""Detail-page parser for AEAT modelo 303 filings (#168).

Modelo 303 is the quarterly VAT return. In addition to the standard
``Total a ingresar`` / ``Total a devolver`` totals, modelo 303
surfaces a ``Resultado a compensar`` total when the quarter's input
VAT exceeds output VAT and the taxpayer elects to carry forward.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl

from ...status import Expediente
from .._models import FiledModelo
from ._common import _RESULTADO_COMPENSAR_RE, build_filed_modelo, soup_of


def parse_modelo_303_detail(
    raw_html: str,
    *,
    expediente: Expediente,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> FiledModelo:
    """Parse a modelo-303 detail page into a :class:`FiledModelo`.

    Args:
        raw_html: Raw detail-page HTML.
        expediente: Upstream :class:`aeat.status.Expediente`.
        source_url: Resolved detail-page URL.
        fetched_at: UTC timestamp the HTML was captured.

    Returns:
        A :class:`FiledModelo` carrying the casillas plus all three
        headline totals (``total_a_ingresar``, ``total_a_devolver``,
        ``resultado_a_compensar``) where present.

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
