"""Detail-page parser for AEAT modelo 130 filings (#168).

Modelo 130 is the quarterly IRPF payment-on-account return filed by
Spanish autónomos. The detail page renders:

- A header block with the NIF, period, and presentation date.
- A casillas table listing every input and computed casilla.
- A ``Total a ingresar`` / ``Total a devolver`` footer.

See [[2026-04-16-aeat-history-fetch-adr]] decisions D3 (values as
strings) and D5 (parsers are pure).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl

from ...status import Expediente
from .._models import FiledModelo
from ._common import build_filed_modelo, soup_of


def parse_modelo_130_detail(
    raw_html: str,
    *,
    expediente: Expediente,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> FiledModelo:
    """Parse a modelo-130 detail page into a :class:`FiledModelo`.

    Args:
        raw_html: Raw detail-page HTML.
        expediente: Upstream :class:`aeat.status.Expediente`.
        source_url: Resolved detail-page URL.
        fetched_at: UTC timestamp the HTML was captured.

    Returns:
        A :class:`FiledModelo` with the extracted casillas and the
        two headline totals (``total_a_ingresar``,
        ``total_a_devolver``). ``resultado_a_compensar`` is ``None``
        for modelo 130 — the form does not expose one.

    Raises:
        HistoryParseError: If the HTML shape is unrecognisable.
    """
    soup = soup_of(raw_html)
    return build_filed_modelo(
        expediente=expediente,
        soup=soup,
        source_url=source_url,
        fetched_at=fetched_at,
    )
