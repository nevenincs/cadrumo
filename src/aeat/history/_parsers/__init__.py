"""Per-modelo detail-page parsers for the filing-history reader (#168).

Every parser is a **pure function** with signature::

    parse_<modelo>_detail(
        raw_html: str,
        *,
        expediente: Expediente,
        source_url: AnyHttpUrl,
        fetched_at: datetime,
    ) -> FiledModelo

Parsers perform zero I/O, never touch the browser, and are exercised
entirely against fixture HTML under
``tests/fixtures/aeat-pages/filing-history/``. See
[[2026-04-16-aeat-history-fetch-adr]] decision D5.

Dispatch goes through :func:`parse_filing_detail`, which routes to
the registered parser via :data:`PARSER_REGISTRY`. Any modelo
without a registered parser raises
:class:`HistoryUnsupportedModeloError` — never silently returns an
empty payload. See ADR D6.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from pydantic import AnyHttpUrl

from ...status import Expediente
from .._errors import HistoryUnsupportedModeloError
from .._models import FiledModelo, HistoryModelo
from .modelo_130 import parse_modelo_130_detail
from .modelo_303 import parse_modelo_303_detail
from .modelo_390 import parse_modelo_390_detail

__all__ = [
    "PARSER_REGISTRY",
    "coerce_modelo",
    "parse_filing_detail",
    "parse_modelo_130_detail",
    "parse_modelo_303_detail",
    "parse_modelo_390_detail",
]


PARSER_REGISTRY: Mapping[
    HistoryModelo,
    Callable[..., FiledModelo],
] = {
    HistoryModelo.MODELO_130: parse_modelo_130_detail,
    HistoryModelo.MODELO_303: parse_modelo_303_detail,
    HistoryModelo.MODELO_390: parse_modelo_390_detail,
}


def coerce_modelo(raw: HistoryModelo | str) -> HistoryModelo:
    """Return the :class:`HistoryModelo` member for ``raw``.

    Accepts either a :class:`HistoryModelo` member (returned as-is)
    or a raw string matching a member value (``"130"``, ``"303"``,
    ``"390"``).

    Raises:
        HistoryUnsupportedModeloError: If ``raw`` does not map to a
            supported modelo. The message lists the supported set.
    """
    if isinstance(raw, HistoryModelo):
        return raw
    try:
        return HistoryModelo(raw)
    except ValueError as exc:
        supported = sorted(member.value for member in HistoryModelo)
        raise HistoryUnsupportedModeloError(
            f"modelo {raw!r} is not supported in v1 (supported: {supported!r})"
        ) from exc


def parse_filing_detail(
    modelo: HistoryModelo | str,
    raw_html: str,
    *,
    expediente: Expediente,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> FiledModelo:
    """Dispatch to the registered parser for ``modelo``.

    Args:
        modelo: The :class:`HistoryModelo` or raw modelo string.
        raw_html: The captured detail-page HTML.
        expediente: The upstream :class:`aeat.status.Expediente` the
            page belongs to. Parsers rely on this for header fields
            not always duplicated on the detail page (e.g. CSV).
        source_url: Resolved detail-page URL.
        fetched_at: UTC timestamp the HTML was captured.

    Returns:
        A :class:`FiledModelo` carrying metadata + calculations.

    Raises:
        HistoryUnsupportedModeloError: If ``modelo`` has no parser.
        HistoryParseError: If the parser cannot interpret the HTML.
    """
    key = coerce_modelo(modelo)
    parser = PARSER_REGISTRY[key]
    return parser(
        raw_html,
        expediente=expediente,
        source_url=source_url,
        fetched_at=fetched_at,
    )
