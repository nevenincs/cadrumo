"""Unit tests for the codified per-modelo result-disposition mapping.

Expected disposition codes are taken from the bundled official AEAT Diseños de
Registros "Tipo de declaración" notes (an external authority, not a re-run of the
function under test):

- M303: C/D/G/I/N/V/U/X — credit → C.
- M130/M131: I/U/G/N/B — credit → B (resultado a deducir).
- M111/M115/M123: I/U/G/N — no credit code; non-positive → N.
- M200: I/U/N/D/R/G/V/X — credit → D by canonical DP200014B:00599.
- M202: I/U/G/N — active modality result casilla → I/N.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest

from .. import (
    CasillaId,
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
    validated_casilla_id,
)
from ..errors import CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test result-disposition casilla id")
    except ValueError as exc:
        raise AssertionError(f"result-disposition fixture casilla key {value!r} is not a CasillaId") from exc


_M303_RESULT_CASILLA: Final[CasillaId] = _casilla_id("71")
_M130_RESULT_CASILLA: Final[CasillaId] = _casilla_id("19")
_M131_RESULT_CASILLA: Final[CasillaId] = _casilla_id("15")
_M111_RESULT_CASILLA: Final[CasillaId] = _casilla_id("30")
_M115_RESULT_CASILLA: Final[CasillaId] = _casilla_id("05")
_M123_RESULT_CASILLA: Final[CasillaId] = _casilla_id("14")
_M123_2019_2023_RESULT_CASILLA: Final[CasillaId] = _casilla_id("08")
_M200_RESULT_CASILLA: Final[CasillaId] = _casilla_id("DP200014B:00599")
_M202_402_RESULT_CASILLA: Final[CasillaId] = _casilla_id("03")
_M202_403_RESULT_CASILLA: Final[CasillaId] = _casilla_id("34")


def _values(casilla_id: CasillaId, amount: str) -> dict[CasillaId, Decimal]:
    return {casilla_id: Decimal(amount)}


@pytest.mark.parametrize(
    ("disposition", "expected_code"),
    (
        pytest.param(ResultDisposition.COMPENSACION, "C", id="compensacion"),
        pytest.param(ResultDisposition.DEVOLUCION, "D", id="devolucion"),
        pytest.param(ResultDisposition.CUENTA_CORRIENTE_INGRESO, "G", id="cuenta-corriente-ingreso"),
        pytest.param(ResultDisposition.INGRESO, "I", id="ingreso"),
        pytest.param(ResultDisposition.NEGATIVA, "N", id="negativa"),
        pytest.param(ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION, "V", id="cuenta-corriente-devolucion"),
        pytest.param(ResultDisposition.DOMICILIACION, "U", id="domiciliacion"),
        pytest.param(ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO, "X", id="devolucion-extranjero"),
        pytest.param(ResultDisposition.RESULTADO_A_DEDUCIR, "B", id="resultado-a-deducir"),
        pytest.param(ResultDisposition.RENUNCIA_DEVOLUCION, "R", id="renuncia-devolucion"),
    ),
)
def test_disposition_codes_match_the_official_diseno_letters(
    disposition: ResultDisposition,
    expected_code: str,
) -> None:
    """Each member value is the single-character code AEAT's fichero expects."""
    assert disposition.value == expected_code


def test_m303_credit_is_compensacion_not_ingreso() -> None:
    """The headline regression: an IVA credit must map to C, never silently I."""
    disp = derive_result_disposition("303", _values(_M303_RESULT_CASILLA, "-210.00"))
    assert disp is ResultDisposition.COMPENSACION
    assert disp is not ResultDisposition.INGRESO


@pytest.mark.parametrize(
    ("modelo", "values", "expected"),
    (
        pytest.param("303", _values(_M303_RESULT_CASILLA, "357.00"), ResultDisposition.INGRESO, id="m303-positive"),
        pytest.param("303", _values(_M303_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA, id="m303-zero"),
        pytest.param(
            "130",
            _values(_M130_RESULT_CASILLA, "-50.00"),
            ResultDisposition.RESULTADO_A_DEDUCIR,
            id="m130-credit",
        ),
        pytest.param("130", _values(_M130_RESULT_CASILLA, "120.00"), ResultDisposition.INGRESO, id="m130-positive"),
        pytest.param("130", _values(_M130_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA, id="m130-zero"),
        pytest.param(
            "131",
            _values(_M131_RESULT_CASILLA, "-50.00"),
            ResultDisposition.RESULTADO_A_DEDUCIR,
            id="m131-credit",
        ),
        pytest.param("111", _values(_M111_RESULT_CASILLA, "500.00"), ResultDisposition.INGRESO, id="m111-positive"),
        pytest.param("111", _values(_M111_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA, id="m111-zero"),
        pytest.param("115", _values(_M115_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA, id="m115-zero"),
        pytest.param("123", _values(_M123_RESULT_CASILLA, "12.00"), ResultDisposition.INGRESO, id="m123-current"),
        pytest.param(
            "123",
            _values(_M123_2019_2023_RESULT_CASILLA, "12.00"),
            ResultDisposition.INGRESO,
            id="m123-2019-2023",
        ),
        pytest.param("200", _values(_M200_RESULT_CASILLA, "-1000.00"), ResultDisposition.DEVOLUCION, id="m200-credit"),
        pytest.param("200", _values(_M200_RESULT_CASILLA, "5000.00"), ResultDisposition.INGRESO, id="m200-positive"),
        pytest.param("200", _values(_M200_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA, id="m200-zero"),
        pytest.param("202", _values(_M202_403_RESULT_CASILLA, "900.00"), ResultDisposition.INGRESO, id="m202-403"),
        pytest.param("202", _values(_M202_402_RESULT_CASILLA, "750.00"), ResultDisposition.INGRESO, id="m202-402"),
        pytest.param(
            "202",
            {
                _M202_402_RESULT_CASILLA: Decimal("0"),
                _M202_403_RESULT_CASILLA: Decimal("0"),
            },
            ResultDisposition.NEGATIVA,
            id="m202-zero",
        ),
    ),
)
def test_codified_result_disposition_cases(
    modelo: str,
    values: dict[CasillaId, Decimal],
    expected: ResultDisposition,
) -> None:
    """Codified modelo cases pin the official disposition letter semantics."""
    assert derive_result_disposition(modelo, values) is expected


def test_missing_result_casilla_defaults_to_negativa() -> None:
    """An absent result casilla is treated as zero → N (never silently ingreso)."""
    assert derive_result_disposition("303", {}) is ResultDisposition.NEGATIVA


def test_disposition_rejects_non_result_casilla_values() -> None:
    """The core disposition helper only accepts its declared result casilla ids."""
    with pytest.raises(CoreValidationError, match=r"non-result casilla\.id values '19'"):
        derive_result_disposition("303", {_M303_RESULT_CASILLA: Decimal("1"), _M130_RESULT_CASILLA: Decimal("2")})


def test_uncodified_modelo_returns_none_not_a_guess() -> None:
    """A modelo without a codified spec returns None so the caller applies a
    documented fallback rather than a guessed disposition."""
    assert derive_result_disposition("390", _values(_M303_RESULT_CASILLA, "-1000.00")) is None
    assert result_disposition_casilla_ids("303") == (_M303_RESULT_CASILLA,)
    assert modelo_has_codified_disposition("303") is True
    assert modelo_has_codified_disposition("200") is True
    assert modelo_has_codified_disposition("202") is True
    assert modelo_has_codified_disposition("390") is False


@pytest.mark.parametrize(
    ("modelo", "casilla_id", "amount"),
    (
        pytest.param("303", _M303_RESULT_CASILLA, "210", id="m303-compensation-vs-ingreso"),
        pytest.param("130", _M130_RESULT_CASILLA, "50", id="m130-deducir-vs-ingreso"),
    ),
)
def test_credit_and_debit_diverge_per_modelo(modelo: str, casilla_id: CasillaId, amount: str) -> None:
    """Anti-regression: a debit and a credit of equal magnitude never share a code."""
    assert derive_result_disposition(modelo, _values(casilla_id, amount)) is not derive_result_disposition(
        modelo,
        _values(casilla_id, f"-{amount}"),
    )
