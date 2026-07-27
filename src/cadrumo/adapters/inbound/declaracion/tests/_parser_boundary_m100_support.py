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
        "0604",
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

_M100_2021_EXPECTED_VALUES: dict[str, str] = {
    "0171": "58412.37",
    "0180": "61907.44",
    "0218": "12430.55",
    "0223": "14664.74",
    "0224": "47242.70",
    "0226": "45881.19",
    "0231": "44517.88",
    "0235": "43156.02",
    "0432": "41803.66",
    "0500": "37869.21",
    "0505": "36502.88",
    "0510": "1204.38",
    "0545": "4827.13",
    "0546": "5106.44",
    "0585": "4213.07",
    "0586": "4492.38",
    "0587": "8705.45",
    "0595": "8219.63",
    "0604": "3211.90",
    "0610": "1947.62",
    "0670": "1658.04",
}
"""What ``100/2021-0A.pdf`` prints, per casilla.

Only the 2021 specimen has these. It is a generated file whose amounts are all
DISTINCT, so each target's value identifies the line it was read from; the 2022
and 2023 specimens are sanitised real renders carrying one constant in every
box, where an exact-value assertion distinguishes nothing and a label pattern
that drifted one line up would satisfy it.

Mirrored from the stamped amounts in
``tests/fixtures/justificantes/_generate_modelo_100_2021.py``, the same
arrangement the 2024/2025 current-year fixtures use. The generator is not the
code under test -- the parser is -- so this is the printed document's own
authority, and the assertion fails if extraction reads a neighbouring token.
"""
