"""Shared M100 verification-chain test support."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    CasillaId,
    DeclaracionParseError,
    _casilla_id,
    _casilla_ids,
    parse_declaracion,
)

_M100_INGRESOS_EXPLOTACION_CASILLA: CasillaId = _casilla_id("0171")
_M100_BASE_LIQUIDABLE_GENERAL_CASILLA: CasillaId = _casilla_id("0505")
_M100_CUOTA_ESTATAL_CASILLA: CasillaId = _casilla_id("0545")
_M100_CUOTA_AUTONOMICA_CASILLA: CasillaId = _casilla_id("0546")
_EXPECTED_CASILLAS_M100: frozenset[CasillaId] = _casilla_ids(
    "0171",
    "0180",
    "0218",
    "0223",
    "0224",
    "0226",
    "0231",
    "0235",
    "0432",
    "0500",
    "0505",
    "0510",
    "0545",
    "0546",
    "0585",
    "0586",
    "0587",
    "0595",
    "0610",
    "0670",
)
_M100_COMPUTED_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "0180",
    "0218",
    "0223",
    "0224",
    "0226",
    "0231",
    "0235",
    "0432",
    "0500",
    "0510",
    "0545",
    "0546",
    "0585",
    "0586",
)
_M100_CLOSURE_ASSERTION_CASILLAS: tuple[CasillaId, ...] = (
    _M100_CUOTA_ESTATAL_CASILLA,
    _M100_CUOTA_AUTONOMICA_CASILLA,
    _casilla_id("0585"),
    _casilla_id("0586"),
)
_M100_CORPUS_YEARS: tuple[int, ...] = (2021, 2022, 2023)
_M100_CORPUS_YEAR_IDS: tuple[str, ...] = tuple(f"{year}-0A" for year in _M100_CORPUS_YEARS)


def _parse_m100_corpus(year: int, label: str) -> dict[CasillaId, object]:
    pdf_path = FIXTURES_DIR / "justificantes" / "100" / f"{year}-0A.pdf"
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="100",
            año_override=year,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{label}]: parse_declaracion raised.\n  error: {exc}")
    return {v.casilla_id: v.printed_value for v in filing.values}
