"""Shared M100 verification-chain test support.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_verification_chain_m100_corpus_limited`
        Active M100 engine-verification consumer for the corpus-limited verdict.
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m100`
        Parser boundary corpus sweep that establishes the same extracted
        casilla surface before engine verification consumes it.
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        Public declaration-copy parser used by the shared corpus loader.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla key carried by the expected sets and parsed-value mapping.
    :exc:`~adapters.inbound.declaracion.DeclaracionParseError`
        Parser failure converted into a corpus-specific ``PARSER-GAP`` failure.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._verification_chain_support import FIXTURES_DIR, CasillaId, DeclaracionParseError, parse_declaracion

_M100_INGRESOS_EXPLOTACION_CASILLA: CasillaId = validated_casilla_id("0171")
_M100_BASE_LIQUIDABLE_GENERAL_CASILLA: CasillaId = validated_casilla_id("0505")
_M100_CUOTA_ESTATAL_CASILLA: CasillaId = validated_casilla_id("0545")
_M100_CUOTA_AUTONOMICA_CASILLA: CasillaId = validated_casilla_id("0546")
_EXPECTED_CASILLAS_M100: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v)
    for _v in (
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
        "0604",
        "0610",
        "0670",
    )
)
_M100_COMPUTED_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v)
    for _v in (
        "0180",
        "0218",
        "0223",
        "0224",
        "0226",
        "0231",
        "0235",
        "0432",
        "0500",
        # Casilla 0505 (base liquidable general sometida a gravamen) is computed
        # from 0500 (max(0, 0500)) from the 2020-2023 revisions onward (also
        # matching 2024/2025); it can no longer be supplied as a leaf input and the
        # engine derives it through the base-liquidable chain.
        "0505",
        "0510",
        "0545",
        "0546",
        "0585",
        "0586",
        "0604",
    )
)
_M100_CLOSURE_ASSERTION_CASILLAS: tuple[CasillaId, ...] = (
    _M100_CUOTA_ESTATAL_CASILLA,
    _M100_CUOTA_AUTONOMICA_CASILLA,
    validated_casilla_id("0585"),
    validated_casilla_id("0586"),
)


def _parse_m100_corpus(year: int, label: str) -> dict[CasillaId, object]:
    """Parse one M100 annual corpus specimen for verification-chain consumers.

    See Also:
        :func:`~adapters.inbound.declaracion.parse_declaracion`
            Parser entry point invoked with explicit Modelo 100 annual context.
        :class:`~domain.calculations.registry.CasillaId`
            Mapping key type returned to engine-verification assertions.
    """
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
