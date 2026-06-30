"""Shared Modelo 100 parser boundary corpus expectations."""

from __future__ import annotations

_M100_EXPECTED_CASILLAS: frozenset[str] = frozenset(
    {
        # First chunk: cuota-chain closure.
        "0545",
        "0546",
        "0505",
        "0585",
        "0586",
        "0587",
        "0595",
        "0610",
        "0670",
        # Second chunk: apartado-summary bases.
        "0235",
        "0432",
        "0500",
        "0510",
        # Third chunk: actividades-economicas ED detail.
        "0180",
        "0218",
        "0223",
        "0224",
        "0226",
        "0231",
        # Fourth chunk: ED leaf input for the formula chain.
        "0171",
    },
)
_M100_CORPUS_PARAMS: tuple[tuple[str, int], ...] = (
    ("2021-0A", 2021),
    ("2022-0A", 2022),
    ("2023-0A", 2023),
)
_M100_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year in _M100_CORPUS_PARAMS)
