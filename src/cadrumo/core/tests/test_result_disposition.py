"""Unit tests for the codified per-modelo result-disposition mapping.

Expected disposition codes are taken from the bundled official AEAT Diseños de
Registros "Tipo de declaración" notes (an external authority, not a re-run of the
function under test):

- M303: C/D/G/I/N/V/U/X — credit → C.
- M130/M131: I/U/G/N/B — credit → B (resultado a deducir).
- M111/M115/M123: I/U/G/N — no credit code; non-positive → N.
- M200: I/U/N/D/R/G/V/X — credit → D by canonical DP200014B:00599.
- M202: I/U/G/N — active modality result casilla → I/N.
- M210: I/N/D — signed cuota diferencial → ingreso/cuota cero/devolución.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest

from ..casilla_id import CasillaId, validated_casilla_id
from ..errors.hierarchy import CoreValidationError
from ..result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_M303_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("71", surface="test result-disposition casilla id")
_M130_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("19", surface="test result-disposition casilla id")
_M131_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("15", surface="test result-disposition casilla id")
_M111_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("30", surface="test result-disposition casilla id")
_M115_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("05", surface="test result-disposition casilla id")
_M123_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("14", surface="test result-disposition casilla id")
_M123_2019_2023_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id(
    "08", surface="test result-disposition casilla id"
)
_M200_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id(
    "DP200014B:00599", surface="test result-disposition casilla id"
)
_M202_402_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("03", surface="test result-disposition casilla id")
_M202_403_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("34", surface="test result-disposition casilla id")
_M210_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id(
    "cuota_diferencial", surface="test result-disposition casilla id"
)


def _values(casilla_id: CasillaId, amount: str) -> dict[CasillaId, Decimal]:
    return {casilla_id: Decimal(amount)}


def test_disposition_codes_match_the_official_diseno_letters() -> None:
    """Each member value is the single-character code AEAT's fichero expects."""
    for case_id, disposition, expected_code in (
        ("compensacion", ResultDisposition.COMPENSACION, "C"),
        ("devolucion", ResultDisposition.DEVOLUCION, "D"),
        ("cuenta-corriente-ingreso", ResultDisposition.CUENTA_CORRIENTE_INGRESO, "G"),
        ("ingreso", ResultDisposition.INGRESO, "I"),
        ("negativa", ResultDisposition.NEGATIVA, "N"),
        ("cuenta-corriente-devolucion", ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION, "V"),
        ("domiciliacion", ResultDisposition.DOMICILIACION, "U"),
        ("devolucion-extranjero", ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO, "X"),
        ("resultado-a-deducir", ResultDisposition.RESULTADO_A_DEDUCIR, "B"),
        ("renuncia-devolucion", ResultDisposition.RENUNCIA_DEVOLUCION, "R"),
    ):
        assert disposition.value == expected_code, case_id


def test_codified_result_disposition_cases() -> None:
    """Codified modelo cases pin the official disposition letter semantics."""
    for case_id, modelo, values, expected in (
        ("m303-credit", "303", _values(_M303_RESULT_CASILLA, "-210.00"), ResultDisposition.COMPENSACION),
        ("m303-positive", "303", _values(_M303_RESULT_CASILLA, "357.00"), ResultDisposition.INGRESO),
        ("m303-zero", "303", _values(_M303_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA),
        (
            "m130-credit",
            "130",
            _values(_M130_RESULT_CASILLA, "-50.00"),
            ResultDisposition.RESULTADO_A_DEDUCIR,
        ),
        ("m130-positive", "130", _values(_M130_RESULT_CASILLA, "120.00"), ResultDisposition.INGRESO),
        ("m130-zero", "130", _values(_M130_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA),
        (
            "m131-credit",
            "131",
            _values(_M131_RESULT_CASILLA, "-50.00"),
            ResultDisposition.RESULTADO_A_DEDUCIR,
        ),
        ("m111-positive", "111", _values(_M111_RESULT_CASILLA, "500.00"), ResultDisposition.INGRESO),
        ("m111-zero", "111", _values(_M111_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA),
        ("m115-zero", "115", _values(_M115_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA),
        ("m123-current", "123", _values(_M123_RESULT_CASILLA, "12.00"), ResultDisposition.INGRESO),
        (
            "m123-2019-2023",
            "123",
            _values(_M123_2019_2023_RESULT_CASILLA, "12.00"),
            ResultDisposition.INGRESO,
        ),
        ("m200-credit", "200", _values(_M200_RESULT_CASILLA, "-1000.00"), ResultDisposition.DEVOLUCION),
        ("m200-positive", "200", _values(_M200_RESULT_CASILLA, "5000.00"), ResultDisposition.INGRESO),
        ("m200-zero", "200", _values(_M200_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA),
        ("m202-403", "202", _values(_M202_403_RESULT_CASILLA, "900.00"), ResultDisposition.INGRESO),
        ("m202-402", "202", _values(_M202_402_RESULT_CASILLA, "750.00"), ResultDisposition.INGRESO),
        (
            "m202-zero",
            "202",
            {
                _M202_402_RESULT_CASILLA: Decimal("0"),
                _M202_403_RESULT_CASILLA: Decimal("0"),
            },
            ResultDisposition.NEGATIVA,
        ),
        ("m210-positive", "210", _values(_M210_RESULT_CASILLA, "1"), ResultDisposition.INGRESO),
        ("m210-zero", "210", _values(_M210_RESULT_CASILLA, "0"), ResultDisposition.NEGATIVA),
        ("m210-refund", "210", _values(_M210_RESULT_CASILLA, "-1"), ResultDisposition.DEVOLUCION),
    ):
        assert derive_result_disposition(modelo, values) is expected, case_id


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
