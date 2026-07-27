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

_M100_EXPECTED_VALUES_BY_STEM: dict[str, dict[str, str]] = {
    "2021-0A": {
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
    },
    "2022-0A": {
        "0171": "63518.92",
        "0180": "66204.17",
        "0218": "13877.41",
        "0223": "16093.26",
        "0224": "50110.91",
        "0226": "48762.35",
        "0231": "47398.04",
        "0235": "46031.79",
        "0432": "44675.53",
        "0500": "40744.68",
        "0505": "39377.25",
        "0510": "2318.47",
        "0545": "5934.26",
        "0546": "6213.57",
        "0585": "5320.18",
        "0586": "5599.49",
        "0587": "10919.67",
        "0595": "10433.85",
        "0604": "4318.03",
        "0610": "3054.75",
        "0670": "2765.17",
    },
    "2023-0A": {
        "0171": "71603.48",
        "0180": "74288.73",
        "0218": "15961.97",
        "0223": "18177.82",
        "0224": "56195.47",
        "0226": "54846.91",
        "0231": "53482.60",
        "0235": "52116.35",
        "0432": "50760.09",
        "0500": "46829.24",
        "0505": "45461.81",
        "0510": "3402.53",
        "0545": "7018.82",
        "0546": "7298.13",
        "0585": "6404.74",
        "0586": "6684.05",
        "0587": "13088.79",
        "0595": "12602.97",
        "0604": "5402.59",
        "0610": "4139.31",
        "0670": "3849.73",
    },
}
"""What each committed M100 render prints, per casilla, per ejercicio.

Every value is distinct from every other in the SAME specimen and from the same
casilla in the OTHER two, so a target that drifted onto a neighbouring line --
or a test that read the wrong year's fixture -- names itself. The renders these
replace printed one redaction constant into every box of all three files, which
is why this map could not exist before: there was nothing for it to distinguish.

Mirrored from the stamped amounts in
``tests/fixtures/justificantes/_generate_modelo_100_corpus.py``, the same
arrangement the 2024/2025 current-year fixtures use. The generator is not the
code under test -- the parser is -- so this is the printed document's own
authority, and the assertion fails if extraction reads a neighbouring token.
"""
